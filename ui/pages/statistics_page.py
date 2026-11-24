"""Read-only statistics, scoped to the activity which owns the saved history."""
from dataclasses import field

import flet as ft

from core.ao5_statistics import HALF_LIFE, MIN_TIMED_SOLVES, parse_goal, session_records, timer_insights
from core.session_overview import Ao5History, TimeProfile, duration_label, memo_split, timer_elapsed
from core.training_statistics import (WINDOWS, format_time, memo_attempts, select_range,
                                      summarize, timer_attempts)
from ui.components.trend_chart import TrendChart
from ui.components.time_distribution import TimeDistribution
from ui.design import panel
from ui.theme_colors import ThemeAwarePage


def pct(value):
    return "—" if value is None else f"{value:.1f}%"


def odds_label(probability):
    if probability is None:
        return "—"
    v = 100 * probability
    if v <= 0 or v >= 100:
        return "0%" if v <= 0 else "100%"
    if v < .01:
        return "<0.01%"
    if v > 99.95:
        return ">99.9%"
    return f"{v:.2f}%" if v < 10 else f"{v:.1f}%"


def clock(value):
    return "—" if value is None else "DNF" if value == "DNF" else format_time(value)


def count(n, noun, plural=None):
    return f"{n} {noun if n == 1 else plural or noun+'s'}"


def choice(value):
    return "all" if value is None else str(value)


def selected_limit(value):
    return None if value == "all" else int(value)


class Metric:
    def __init__(self, title, col):
        self.title = ft.Text(title, size=14, color=ft.Colors.ON_SURFACE_VARIANT)
        self.value = ft.Text("—", size=22, weight=ft.FontWeight.W_600)
        self.detail = ft.Text(size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.view = ft.Column([self.title, self.value, self.detail], spacing=2, tight=True, col=col)

    def show(self, value, detail):
        self.value.value, self.detail.value = value, detail


class NumberList:
    def __init__(self, title, labels):
        self.values = [ft.Text("—", size=14, weight=ft.FontWeight.W_600, font_family="monospace")
                       for _ in labels]
        self.view = ft.Column([ft.Text(title, size=15, weight=ft.FontWeight.W_600)] + [
            ft.Row([ft.Text(label, size=13, expand=True), value], spacing=8)
            for label,value in zip(labels,self.values)], spacing=4, tight=True, col={"xs":12,"md":6})

    def show(self, *values):
        for label, value in zip(self.values,values):
            label.value = value


@ft.control
class StatisticsPage(ThemeAwarePage, ft.Column):
    source: str = field(default="timer", metadata={"skip": True})

    def init(self):
        self.expand = True
        self.spacing = 10
        self.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        timer = self.source == "timer"
        self.session = self.scheme = self._last_context = None
        self.scope = self.window = None  # Full dataset; cumulative line from its first attempt.
        self.phase = "total"
        self._history, self._records, self._filter_options = [], None, None
        self._forecast = self._goal = self._profile = self._ao5 = None
        self._summary = self._summary_window = self._ao5_points = None
        self._memo_rounds = []
        self._memo_splits = {}
        self.metric = "time" if timer else "accuracy"
        self._views = {"time":"all","accuracy":"all"}
        self.filter_picker = ft.Dropdown(width=179, height=48, dense=True, label="Timer session" if timer else "Letter scheme",
                                         on_select=self._change_filter)
        self.scope_picker = ft.Dropdown(width=166, height=48, dense=True, label="Data range", value="all",
            options=[ft.DropdownOption("all", "Entire session" if timer else "All rounds")] +
                    [ft.DropdownOption(str(w), f"Last {w} "+("solves" if timer else "rounds")) for w in WINDOWS],
            on_select=self._change_scope)
        self.metric_picker = ft.SegmentedButton(
            segments=[ft.Segment(value="time",label="Time"),ft.Segment(value="accuracy",label="Accuracy")],
            selected=[self.metric],show_selected_icon=False,height=38,
            style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=12),text_style=ft.TextStyle(size=14)),
            on_change=self._change_metric)
        self._view_options = {
            "time":[ft.DropdownOption("all","Cumulative median"),
                    *([ft.DropdownOption("ao5","Recorded Ao5")] if timer else []),
                    ft.DropdownOption("distribution","Distribution"),
                    *[ft.DropdownOption(str(w),f"Rolling {w} median") for w in WINDOWS]],
            "accuracy":[ft.DropdownOption("all","Cumulative accuracy"),
                        *[ft.DropdownOption(str(w),f"Rolling {w} accuracy") for w in WINDOWS]],
        }
        self.window_picker = ft.Dropdown(width=198,height=44,dense=True,
            label="Chart view",value="all",options=self._view_options[self.metric],on_select=self._change_window)
        self.phase_picker = ft.Dropdown(width=145, height=44, dense=True, label="Phase", value=self.phase,
            options=[ft.DropdownOption(k,v) for k,v in (("total","Total time"),("memo","Memo time"),("recall","Recall time"))],
            visible=False,on_select=self._change_phase)
        self.filters = ft.Row([self.filter_picker, self.scope_picker], height=52, spacing=10)
        self.empty = panel(ft.Column([
            ft.Text("No solves in this session yet" if timer else "No saved memo rounds in this selection",
                    size=17,weight=ft.FontWeight.W_600),
            ft.Text("Record a solve in Timer or choose another session above. Your first Ao5 appears after five attempts."
                    if timer else "Finish a round in Train or change the letter scheme above.",
                    size=14,color=ft.Colors.ON_SURFACE_VARIANT)],spacing=5,tight=True),padding=16)
        self.coverage = ft.Text(size=13, weight=ft.FontWeight.W_600)
        self.elapsed = ft.Text(size=13,color=ft.Colors.ON_SURFACE_VARIANT)
        labels = (("Success rate", "Typical successful solve", "Latest Ao5") if timer else
                  ("Letter accuracy", "Typical memo", "Typical recall", "Perfect rounds"))
        if timer:
            self.metrics = [Metric(k, {"xs":12 if i==1 else 6, "sm":4}) for i,k in enumerate(labels)]
        else:
            self.metrics = [Metric(k, {"xs":6,"md":3}) for k in labels]
        self.accuracy = TrendChart(True, timer, self.data)
        self.timing = TrendChart(False, timer, self.data)
        self.distribution = TimeDistribution()
        self.ao5_wait = ft.Text(size=14)
        self.ao5_wait_panel = panel(self.ao5_wait,padding=18,visible=False)
        self.chart_area = ft.Column([self.timing.view,self.accuracy.view,self.distribution.view,self.ao5_wait_panel],
            spacing=0,tight=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.footnote = ft.Text(size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.recent_rows = [ft.Row([ft.Text(width=48), ft.Text(expand=True),
                            ft.Text(width=62,text_align=ft.TextAlign.RIGHT)], spacing=6, visible=False)
                            for _ in range(12)]
        overview_items = [
            ft.Row([ft.Text("Session overview" if timer else "Memo overview",size=19,weight=ft.FontWeight.W_600),
                    self.coverage,self.elapsed],wrap=True,spacing=14,run_spacing=3),
            ft.ResponsiveRow([self.metrics[i].view for i in ((0,2,1) if timer else (0,1,2,3))],
                             spacing=12,run_spacing=8),
        ]
        if not timer:
            self.edge_note,self.corner_note = [ft.Text(size=14,weight=ft.FontWeight.W_600) for _ in range(2)]
            self.split_note = ft.Text(size=12,color=ft.Colors.ON_SURFACE_VARIANT)
            overview_items.append(ft.Column([
                ft.Row([self.edge_note,self.corner_note],wrap=True,spacing=16,run_spacing=3),
                self.split_note],spacing=3,tight=True))
        self.overview = panel(ft.Column(overview_items,spacing=10,tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH),padding=14)
        self.chart_controls = ft.Row([self.metric_picker,self.window_picker] + ([] if timer else [self.phase_picker]),
                             wrap=True,spacing=10,run_spacing=6)
        items = [self.overview,self.chart_controls,self.chart_area,self.footnote]
        recent_content = []
        if timer:
            self.odds = NumberList("Odds for the next five", ["Valid Ao5 · at least 4 of 5",
                                                              "4 in a row within 5", "All 5 successful"])
            self.observed = NumberList("Recorded in this range", ["Valid Ao5s / completed windows",
                                                                  "Current / longest success streak"])
            self.odds_note = ft.Text(size=12, color=ft.Colors.ON_SURFACE_VARIANT)
            self.goal_field = ft.TextField(label="Time goal", hint_text="1:30.00", width=148, dense=True,
                                          on_submit=self._apply_goal, on_change=self._edit_goal)
            self.goal_button = ft.OutlinedButton("Check goal", on_click=self._apply_goal)
            self.goal_recorded = ft.Text(size=14, selectable=True)
            self.goal_result = ft.Text(size=14, selectable=True)
            self.forecast_caption = ft.Text(size=14,color=ft.Colors.PRIMARY)
            goals = ft.Column([ft.Text("Beat a time",size=15,weight=ft.FontWeight.W_600),
                ft.Row([self.goal_field,self.goal_button],wrap=True,spacing=8,run_spacing=6),
                self.goal_recorded,self.goal_result],tight=True,spacing=5,col={"xs":12,"md":6})
            self.forecasts = ft.ExpansionTile(title="Forecasts & time goal",subtitle=self.forecast_caption,
                expanded=False,maintain_state=True,dense=True,controls_padding=12,controls=[
                    ft.ResponsiveRow([self.odds.view,goals],spacing=20,run_spacing=12),self.odds_note])
            items.append(panel(self.forecasts,padding=0))
            recent_content.append(self.observed.view)
        self.recent = ft.ExpansionTile(title="Recent attempts", subtitle="Results and trend accuracy · newest first",
            expanded=False, maintain_state=True, dense=True, controls=[ft.Column([
                *recent_content,*self.recent_rows],spacing=6,tight=True)],controls_padding=10)
        items.append(self.recent)
        if timer:
            self.pb_values = [ft.Text(size=12,color=ft.Colors.ON_SURFACE_VARIANT) for _ in range(3)]
            items.append(ft.Row([ft.Text("Session PBs",size=12,weight=ft.FontWeight.W_600),
                                 *self.pb_values],wrap=True,spacing=14,run_spacing=3,
                                tooltip="Personal bests across this entire timer session."))
        self.report = ft.Column(items, spacing=9, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                visible=False)
        # One native vertical viewport; content gets its natural height, rather
        # than asking nested expanding Columns to decide what should scroll.
        self.scroll_area = ft.ListView([self.empty,self.report], key="statistics_scroll_"+self.source,
            build_controls_on_demand=False, auto_scroll=False, spacing=0,
            scroll=ft.Scrollbar(thumb_visibility=True,interactive=True,thickness=8),
            padding=ft.Padding.only(right=12,bottom=12))
        self.controls = [self.filters,self.scroll_area]

    def set_viewport(self,width,height):
        self.width,self.height = max(1,width),max(1,height)
        self.scroll_area.width = self.width
        self.scroll_area.height = max(1,self.height-self.filters.height-self.spacing)
        compact = self.width < 360
        free = max(2,self.width-self.filters.spacing)
        self.filter_picker.width = free*.51 if compact else 179
        self.scope_picker.width = free*.49 if compact else 166

    def _edit_goal(self,e):
        self._goal = None
        self.goal_field.error = None
        self.goal_recorded.value = ""
        self.goal_result.value = "Press Enter or Check goal." if (self.goal_field.value or "").strip() else ""
        self._update_goal_controls()

    def _apply_goal(self,e=None):
        self.goal_field.error = None
        try:
            self._goal = parse_goal(self.goal_field.value)
        except ValueError as err:
            self._goal = None
            self.goal_field.error = str(err)
        self._show_goal()
        self._update_goal_controls()

    def _update_goal_controls(self):
        # Input and output are siblings; update them without touching the list.
        ft.context.disable_auto_update()
        try:
            page = self.page
        except RuntimeError:
            return
        if page is not None and self.goal_field._i in page.session.index:
            page.update(self.goal_field,self.goal_recorded,self.goal_result)

    def _show_goal(self):
        if self._goal is None or self._forecast is None:
            self.goal_recorded.value = self.goal_result.value = ""
            return
        single,ao5,sampled = self._forecast.goal_odds(self._goal)
        avg_label = ("Need 3 successful times" if ao5 is None else
                     ("≈" if sampled else "")+odds_label(ao5))
        def observed(profile,noun):
            hits = profile.under(self._goal)
            return f"{hits}/{profile.total} {noun} ({pct(100*hits/profile.total)})"
        actual_ao5 = observed(self._ao5.profile,"Ao5s") if self._ao5.values else "No completed Ao5 yet"
        self.goal_recorded.value = (f"Recorded under {clock(self._goal)}: "+observed(self._profile,"attempts")
                                    +" · "+actual_ao5)
        self.goal_result.value = (f"Next attempts · Single: {odds_label(single)}"
                                  f" · Valid Ao5: {avg_label}")
        self.goal_recorded.tooltip = ("Times must be strictly below the goal. Counts include DNFs as misses. "
                                      "Each recorded Ao5 uses five consecutive attempts inside this range.")
        self.goal_result.tooltip = ("Estimated chance of beating the same goal. DNFs count as misses. "
                                    "The Ao5 is for five new attempts; ≈ denotes a sampling estimate.")

    def open_for(self, context):
        if context != self._last_context:
            self._last_context = context
            if self.source == "timer":
                self.session = context
            else:
                self.scheme = context
        self.refresh(update=False)

    def _change_scope(self,e):
        self.scope = selected_limit(e.control.value)
        self._render()

    def _change_metric(self,e):
        values=e.control.selected
        if values and values[0] in self._views and values[0]!=self.metric:
            self.metric=values[0]
            self.window_picker.options=self._view_options[self.metric]
            self._render(charts_only=True)

    def _change_window(self,e):
        value=e.control.value
        if value in {opt.key for opt in self._view_options[self.metric]}:
            self._views[self.metric]=value
            self._render(charts_only=True)

    def _change_filter(self,e):
        key = e.control.value
        if self.source == "timer":
            self.session = key
        else:
            self.scheme = None if key == "*" else key[1:]
        self.refresh()

    def _change_phase(self,e):
        self.phase = e.control.value
        self._history=memo_attempts(self._memo_rounds,phase=self.phase)
        self._render(charts_only=True,times_changed=True)

    def refresh(self, update=True):
        """Re-read saved data on entry/session changes, including edits or synced solves."""
        data = self.data.data
        if self.source == "timer":
            if self.session not in data.practice_sessions:
                self.session = data.active_practice_session
            labels = self.data.practice_session_labels
            options = tuple((k,labels.get(k,k)) for k in data.practice_sessions)
            value = self.session
            self._history = timer_attempts(data.practice_sessions.get(self.session, ()))
            times=[r.time for r in self._history]
            self._whole_ao5=Ao5History.from_times(times)
            self._records = session_records(times,known_ao5=self._whole_ao5.record)
        else:
            names = sorted({a.scheme_name for a in data.progressive_memo_history},key=str.casefold)
            if self.scheme not in names:
                self.scheme = None
            options = (("*","All schemes"), *[(":"+k,k or "Unnamed scheme") for k in names])
            value = "*" if self.scheme is None else ":"+self.scheme
            self._memo_rounds=[r for r in data.progressive_memo_history
                               if self.scheme is None or r.scheme_name==self.scheme]
            self._history = memo_attempts(self._memo_rounds,phase=self.phase)
            self._memo_splits.clear()
        if options != self._filter_options:
            self.filter_picker.options = [ft.DropdownOption(k,label) for k,label in options]
            self._filter_options = options
        self.filter_picker.value, self.phase_picker.value = value, self.phase
        self._render(update=update)

    def _render(self, *, charts_only=False, times_changed=False, update=True):
        view=self._views[self.metric]
        self.window = int(view) if view.isdecimal() else None
        self.scope_picker.value, self.window_picker.value = choice(self.scope),view
        self.metric_picker.selected=[self.metric]
        self.phase_picker.visible = self.source!="timer" and self.metric=="time"
        rows, offset = select_range(self._history,self.scope)
        self.empty.visible, self.report.visible = not rows, bool(rows)
        if not rows:
            self._forecast = self._summary = self._profile = self._ao5 = None
            for chart in (self.accuracy,self.timing):
                chart.points = ()
                chart.clear_inspection()
            if self.source == "timer":
                self._show_goal()
        if rows:
            new_sample=not charts_only or times_changed or self._summary is None
            if new_sample or self.window!=self._summary_window:
                self._summary=summarize(rows,self.window,offset=offset)
                self._summary_window=self.window
            s=self._summary
            if new_sample:
                times=[r.time for r in rows]
                self._profile=TimeProfile.from_times(times)
                if self.source=="timer":
                    self._ao5=Ao5History.from_times(times) if offset else self._whole_ao5
                    self._ao5_points=None
                self.distribution.set_profile(self._profile,timer=self.source=="timer",phase=self.phase)
            if not charts_only:
                self._display_sample(rows,offset,s,times)
            self._display_charts(rows,offset,s,view)
        if update:
            try:
                page = self.page
            except RuntimeError:
                return
            if page is not None and self._i in page.session.index:
                self.update()

    def _display_sample(self,rows,offset,s,times):
        timer = self.source == "timer"
        total = s.overall
        noun = "solve" if timer else "round"
        self.coverage.value = (("Entire session" if timer else "All rounds") + " · " + count(len(rows),noun)
                               if self.scope is None else
                               f"Latest {len(rows)} of {count(len(self._history),noun)} · #{offset+1}–#{offset+len(rows)}")
        if timer:
            self.elapsed.value=duration_label(timer_elapsed(rows))+" on the timer"
            self.elapsed.tooltip="Actual elapsed time across these attempts, including DNFs. Excludes +2 penalties and breaks."
            insights = timer_insights(times,recorded=self._ao5.record)
            self._forecast = insights.forecast
            self._show_goal()
            self.metrics[0].show(pct(total.accuracy),
                f"{count(total.correct,'success','successes')} · {count(total.attempts-total.correct,'DNF')}")
            spread=self._profile.middle_half
            detail=(f"Middle 50%: {clock(spread[0])} – {clock(spread[1])}" if spread is not None else
                    "One successful time" if total.timed else "No successful times yet")
            self.metrics[1].show(clock(total.median),detail)
            self.metrics[1].view.tooltip="Median and 25th–75th percentiles of successful times. Includes +2 penalties."
            if self._ao5.values:
                latest=self._ao5.values[-1]
                self.metrics[2].show("DNF" if latest is None else clock(latest),
                                     f"Attempts #{offset+len(rows)-4}–{offset+len(rows)}")
            else:
                self.metrics[2].show("—",f"{count(5-len(rows),'more attempt')} for the first Ao5")
            needed = MIN_TIMED_SOLVES-total.timed
            self.forecast_caption.value=("Estimated valid Ao5 · "+clock(insights.valid_pace) if needed<=0 else
                f"Estimated valid Ao5 · {count(needed,'more successful solve')} needed")
            self.forecast_caption.tooltip="Expected time if five new attempts produce a valid average."
            odds = insights.odds
            self.odds.show(odds_label(odds.valid),odds_label(odds.run_of_four),odds_label(odds.clean))
            recorded = insights.recorded
            self.observed.show(f"{recorded.valid} / {recorded.windows}",f"{insights.current_streak} / {insights.longest_streak}")
            self.odds_note.value = (("Small sample. " if len(rows)<10 else "") +
                f"Forecast success rate: {pct(100*self._forecast.success_rate)}. "
                f"Each {HALF_LIFE} attempts back halves a solve’s weight. Next-five odds assume independent attempts.")
            for target,label,value in zip(self.pb_values,("Single","Ao5","Ao12"),
                                          (self._records.single,self._records.ao5.best,self._records.ao12.best)):
                target.value = f"{label}  {clock(value)}"
        else:
            self.elapsed.value=count(total.scored,"scored letter")
            for tile,(value,detail) in zip(self.metrics,[
                (pct(total.accuracy),f"{total.correct} / {total.scored} scored letters"),
                (clock(s.memo_median),"Median memorization time"),
                (clock(s.recall_median),"Median recall time"),
                (str(s.perfect),f"Out of {count(total.attempts,'round')}")]):
                tile.show(value,detail)
            if offset not in self._memo_splits:
                self._memo_splits[offset]=memo_split(self._memo_rounds[offset:])
            split=self._memo_splits[offset]
            for label,name,good,n in ((self.edge_note,"Edges",split.edge_correct,split.edge_scored),
                                      (self.corner_note,"Corners",split.corner_correct,split.corner_scored)):
                label.visible=bool(split.detailed)
                label.value=(f"{name} · {pct(100*good/n)} ({good}/{n})" if n else f"{name} · No scored letters")
            self.split_note.visible=split.detailed!=len(rows)
            self.split_note.value=(f"Edge and corner detail saved for {split.detailed} of {count(len(rows),'round')}."
                                  if split.detailed else "Only overall scores are available for these rounds.")

    def _display_charts(self,rows,offset,s,view):
        timer = self.source == "timer"
        recent = s.recent
        noun = "solve" if timer else "round"
        timing = "solve time" if timer else self.phase+" time"
        scope = ("since the start of this range" if self.window is None else
                 f"over the latest {count(recent.attempts,noun)}")
        accuracy=self.metric=="accuracy"
        ao5=view=="ao5"
        wait=ao5 and not self._ao5.values
        self.accuracy.view.visible=accuracy
        self.timing.view.visible=not accuracy and view!="distribution" and not wait
        self.distribution.view.visible=view=="distribution"
        self.ao5_wait_panel.visible=wait
        self.footnote.visible=view!="distribution" and not wait
        for chart in (self.accuracy,self.timing):
            chart.clear_inspection()
        if wait:
            self.ao5_wait.value=f"Recorded Ao5 starts at attempt five. {len(rows)} of 5 attempts in this range."
        elif ao5:
            if self._ao5_points is None:
                self._ao5_points=self._ao5.points(offset)
            self.timing.set_series("Recorded Ao5","",
                "Each average drops the best and worst of five consecutive attempts.",
                self._ao5_points,ao5=True)
        elif accuracy:
            self.accuracy.set_series("Solve success rate over time" if timer else "Letter accuracy over time",
                pct(recent.accuracy), "Successes / attempts "+scope+"." if timer else "Correct / scored letters "+scope+".",
                s.points,self.window)
        elif view!="distribution":
            self.timing.set_series("Median "+timing+" over time",clock(recent.median),
                ("Successful solves " if timer else "Completed rounds ")+scope+".",s.points,self.window)
        if not wait and ao5:
            grouped=len(self._ao5.values)>len(self._ao5_points)
            self.footnote.value=("Each mark groups consecutive Ao5 results and shows their valid median. × means a DNF in that group."
                                 if grouped else "Each mark ends a five-attempt window. × means that Ao5 was a DNF.")
        elif self.footnote.visible:
            if len(s.points)<len(rows):
                detail=f"All {count(len(rows),noun)} are included in {len(s.points)} marks. Each shows its group’s "+("accuracy." if accuracy else "median.")
            else:
                detail="Each dot is one "+noun+"."
            if timer and not accuracy:
                detail+=" × marks a DNF. Times include +2 penalties."
            elif not timer and accuracy:
                detail+=" Accuracy counts scored letters."
            self.footnote.value=detail
        latest = list(reversed(s.latest))
        for i,row in enumerate(self.recent_rows):
            row.visible = i < len(latest)
            if row.visible:
                point = latest[i]
                a = point.attempt
                result = ("DNF" if a.time is None else clock(a.time)+(" (+2)" if a.plus2 else "")) if timer else (
                    f"{a.correct}/{a.scored} letters · {clock(a.time)}")
                row.controls[0].value,row.controls[1].value,row.controls[2].value = (
                    f"#{point.number}",result,pct(point.rolling.accuracy))
