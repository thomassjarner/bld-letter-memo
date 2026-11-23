"""Read-only statistics, scoped to the activity which owns the saved history."""
from dataclasses import field

import flet as ft

from core.ao5_statistics import MIN_TIMED_SOLVES, session_records, timer_insights
from core.training_statistics import (WINDOWS, format_time, memo_attempts, select_range,
                                      summarize, timer_attempts, trimmed_time)
from ui.components.trend_chart import TrendChart
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
        self.view = panel(ft.Column([self.title, self.value, self.detail], spacing=3, tight=True), padding=10, col=col)

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
        self.filter_picker = ft.Dropdown(width=179, dense=True, label="Timer session" if timer else "Letter scheme",
                                         on_select=self._change_filter)
        self.scope_picker = ft.Dropdown(width=166, dense=True, label="Data range", value="all",
            options=[ft.DropdownOption("all", "Entire session" if timer else "All rounds")] +
                    [ft.DropdownOption(str(w), f"Last {w} "+("solves" if timer else "rounds")) for w in WINDOWS],
            on_select=self._change_scope)
        self.window_picker = ft.Dropdown(width=155, height=44, dense=True, label="Chart line", value="all",
            options=[ft.DropdownOption("all","Cumulative")] +
                    [ft.DropdownOption(str(w),f"Rolling {w}") for w in WINDOWS],
            on_select=self._change_window)
        self.phase_picker = ft.Dropdown(width=145, height=44, dense=True, label="Time trend", value=self.phase,
            options=[ft.DropdownOption(k,v) for k,v in (("total","Total time"),("memo","Memo time"),("recall","Recall time"))],
            on_select=self._change_phase)
        self.filters = ft.Row([self.filter_picker, self.scope_picker], wrap=True, spacing=10, run_spacing=6)
        self.empty = panel(ft.Text("No saved solves in this session yet." if timer else
                                   "No saved memo rounds in this selection yet.", size=16), padding=16)
        self.coverage = ft.Text(size=13, weight=ft.FontWeight.W_600)
        labels = (("Solve success rate", "Typical successful solve", "Estimated valid Ao5") if timer else
                  ("Letter accuracy", "Typical memo", "Typical recall", "Perfect rounds"))
        if timer:
            self.metrics = [Metric(k, {"xs":12 if i==2 else 6, "md":4}) for i,k in enumerate(labels)]
        else:
            self.metrics = [Metric(k, {"xs":6,"lg":3}) for k in labels]
        self.accuracy = TrendChart(True, timer, self.data)
        self.timing = TrendChart(False, timer, self.data)
        self.footnote = ft.Text(size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.recent_rows = [ft.Row([ft.Text(width=48), ft.Text(expand=True),
                            ft.Text(width=62,text_align=ft.TextAlign.RIGHT)], spacing=6, visible=False)
                            for _ in range(12)]
        self.recent = ft.ExpansionTile(title="Recent attempts", subtitle="Result and trend accuracy · newest first",
            expanded=False, maintain_state=True, dense=True, controls=[ft.Column(self.recent_rows, spacing=6)], controls_padding=10)
        items = [self.coverage, ft.ResponsiveRow([m.view for m in self.metrics], spacing=8, run_spacing=8)]
        if timer:
            self.odds = NumberList("Odds for the next five", ["Valid Ao5 · at least 4 of 5",
                                                              "4 in a row within 5", "All 5 successful"])
            self.observed = NumberList("Recorded in this range", ["Valid Ao5s / completed windows",
                                                                  "Latest recorded Ao5", "Current / longest success streak"])
            self.odds_note = ft.Text(size=12, color=ft.Colors.ON_SURFACE_VARIANT)
            items.append(panel(ft.Column([ft.ResponsiveRow([self.odds.view,self.observed.view],
                                  spacing=24,run_spacing=12), self.odds_note],spacing=7,tight=True),padding=12))
        items.extend([ft.Row([ft.Text("Trends", size=16,weight=ft.FontWeight.W_600),
                              self.window_picker] + ([] if timer else [self.phase_picker]),
                             wrap=True,spacing=12,run_spacing=6),
                      ft.ResponsiveRow([self.accuracy.view,self.timing.view],spacing=10,run_spacing=10),
                      self.footnote,self.recent])
        if timer:
            self.pb_values = [ft.Text(size=12,color=ft.Colors.ON_SURFACE_VARIANT) for _ in range(3)]
            items.append(ft.Row([ft.Text("Session PBs",size=12,weight=ft.FontWeight.W_600),
                                 *self.pb_values],wrap=True,spacing=14,run_spacing=3,
                                tooltip="Personal bests across this entire timer session."))
        self.report = ft.Column(items, spacing=9, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, visible=False)
        self.scroll_area = ft.Column([self.empty,self.report], expand=True,scroll=ft.ScrollMode.AUTO,
                                     horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.controls = [self.filters,self.scroll_area]

    def set_available_width(self, width):
        compact = width < 360
        self.filter_picker.width = (width-10)*.51 if compact else 179
        self.scope_picker.width = (width-10)*.49 if compact else 166

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

    def _change_window(self,e):
        self.window = selected_limit(e.control.value)
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
        self.refresh()

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
            self._records = session_records([r.time for r in self._history])
        else:
            names = sorted({a.scheme_name for a in data.progressive_memo_history},key=str.casefold)
            if self.scheme not in names:
                self.scheme = None
            options = (("*","All schemes"), *[(":"+k,k or "Unnamed scheme") for k in names])
            value = "*" if self.scheme is None else ":"+self.scheme
            self._history = memo_attempts(data.progressive_memo_history,self.scheme,self.phase)
        if options != self._filter_options:
            self.filter_picker.options = [ft.DropdownOption(k,label) for k,label in options]
            self._filter_options = options
        self.filter_picker.value, self.phase_picker.value = value, self.phase
        self._render(update=update)

    def _render(self, *, charts_only=False, update=True):
        self.scope_picker.value, self.window_picker.value = choice(self.scope), choice(self.window)
        rows, offset = select_range(self._history,self.scope)
        self.empty.visible, self.report.visible = not rows, bool(rows)
        if rows:
            s = summarize(rows,self.window,offset=offset)
            if not charts_only:
                self._display_sample(rows,offset,s)
            self._display_charts(rows,s)
        if update:
            try:
                page = self.page
            except RuntimeError:
                return
            if page is not None and self._i in page.session.index:
                self.update()

    def _display_sample(self,rows,offset,s):
        timer = self.source == "timer"
        total = s.overall
        noun = "solve" if timer else "round"
        self.coverage.value = (("Entire session" if timer else "All rounds") + " · " + count(len(rows),noun)
                               if self.scope is None else
                               f"Latest {len(rows)} of {count(len(self._history),noun)} · #{offset+1}–#{offset+len(rows)}")
        if timer:
            times = [r.time for r in rows]
            insights = timer_insights(times,recorded=self._records.ao5 if not offset else None)
            self.metrics[0].show(pct(total.accuracy),
                f"{count(total.correct,'success','successes')} · {count(total.attempts-total.correct,'DNF')}")
            self.metrics[1].show(clock(total.median), f"Median of {count(total.timed,'successful solve')}")
            needed = MIN_TIMED_SOLVES-total.timed
            self.metrics[2].show(clock(insights.valid_pace), "Expected time if the next five give a valid average."
                if needed <= 0 else f"{count(needed,'more successful solve')} needed for a time estimate.")
            self.metrics[2].view.tooltip = ("Uses the successful times and success rate in this range. "
                "Projects five new attempts and drops the best and worst. A DNF can be the dropped worst result.")
            odds = insights.odds
            self.odds.show(odds_label(odds.valid),odds_label(odds.run_of_four),odds_label(odds.clean))
            recorded = insights.recorded
            latest = trimmed_time(times[-5:]) if len(times)>=5 else None
            self.observed.show(f"{recorded.valid} / {recorded.windows}",clock(latest),
                               f"{insights.current_streak} / {insights.longest_streak}")
            self.odds_note.value = (("Small sample. " if len(rows)<10 else "") +
                f"Estimates assume independent solves at your {pct(total.accuracy)} success rate. Recorded Ao5 windows overlap.")
            for target,label,value in zip(self.pb_values,("Single","Ao5","Ao12"),
                                          (self._records.single,self._records.ao5.best,self._records.ao12.best)):
                target.value = f"{label}  {clock(value)}"
        else:
            for tile,(value,detail) in zip(self.metrics,[
                (pct(total.accuracy),f"{total.correct} / {total.scored} scored letters"),
                (clock(s.memo_median),"Median memorization time"),
                (clock(s.recall_median),"Median recall time"),
                (str(s.perfect),f"Out of {count(total.attempts,'round')}")]):
                tile.show(value,detail)

    def _display_charts(self,rows,s):
        timer = self.source == "timer"
        recent = s.recent
        noun = "solve" if timer else "round"
        timing = "solve time" if timer else self.phase+" time"
        scope = ("since the start of this range" if self.window is None else
                 f"over the latest {count(recent.attempts,noun)}")
        self.accuracy.set_series("Solve success rate over time" if timer else "Letter accuracy over time",
            pct(recent.accuracy), "Successes / attempts "+scope+"." if timer else "Correct / scored letters "+scope+".",
            s.points,self.window)
        self.timing.set_series("Median "+timing+" over time",clock(recent.median),
            ("Successful solves " if timer else "Completed rounds ")+scope+".",s.points,self.window)
        if len(s.points) < len(rows):
            detail = f"All {count(len(rows),noun)} are included in {len(s.points)} chart marks. Each mark shows its group’s rate or median."
            if timer:
                detail += " × marks a group containing a DNF."
        else:
            detail = "Each dot is one "+noun+"."
            if timer:
                detail += " × marks a DNF."
        self.footnote.value = detail + (" Times include +2 penalties." if timer else " Accuracy is weighted by scored letters.")
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
