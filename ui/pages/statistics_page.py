"""Read-only statistics embedded in one activity. Filters never alter training setup."""
from dataclasses import field

import flet as ft

from core.training_statistics import (PLOT_LIMIT, WINDOWS, format_time, memo_attempts,
                                      projected_ao5, summarize, timer_attempts, trimmed_time)
from ui.components.trend_chart import TrendChart
from ui.design import panel
from ui.theme_colors import ThemeAwarePage


def pct(value):
    return "—" if value is None else f"{value:.1f}%"


def clock(value):
    return "—" if value is None else "DNF" if value == "DNF" else format_time(value)


def count(n, noun, plural=None):
    return f"{n} {noun if n == 1 else plural or noun+'s'}"


class Metric:
    def __init__(self, title, col):
        self.value = ft.Text("—", size=22, weight=ft.FontWeight.W_600)
        self.detail = ft.Text(size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.view = panel(ft.Column([ft.Text(title, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                                     self.value, self.detail], spacing=3, tight=True), padding=12, col=col)

    def show(self, value, detail):
        self.value.value, self.detail.value = value, detail


@ft.control
class StatisticsPage(ThemeAwarePage, ft.Column):
    source: str = field(default="timer", metadata={"skip": True})

    def init(self):
        self.expand = True
        self.spacing = 10
        self.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        timer = self.source == "timer"
        self.session = self.scheme = self._last_context = None
        self.window, self.phase = 12, "total"
        self._filter_options = None
        self.filter_picker = ft.Dropdown(width=179, dense=True, label="Timer session" if timer else "Letter scheme",
                                         on_select=self._change_filter)
        self.window_picker = ft.Dropdown(width=146, dense=True, label="Rolling window", value=str(self.window),
            options=[ft.DropdownOption(str(w), f"{w} "+("solves" if timer else "rounds")) for w in WINDOWS],
            on_select=self._change_window)
        self.phase_picker = ft.Dropdown(width=145, dense=True, label="Time trend", value=self.phase,
            options=[ft.DropdownOption(k, v) for k,v in (("total","Total time"),("memo","Memo time"),("recall","Recall time"))],
            on_select=self._change_phase)
        self.filters = ft.Row([self.filter_picker, self.window_picker]+([] if timer else [self.phase_picker]),
                              wrap=True, spacing=10, run_spacing=8)
        self.empty = panel(ft.Text("No saved solves in this session yet." if timer else
                                   "No saved memo rounds in this selection yet.", size=16), padding=16)
        self.coverage = ft.Text(size=13, weight=ft.FontWeight.W_600)
        labels = ("Solve success rate", "Typical solve", "Best single", "Latest Ao5") if timer else (
                  "Letter accuracy", "Typical memo", "Typical recall", "Perfect rounds")
        self.metrics = [Metric(k, {"xs":6,"lg":3}) for k in labels]
        self.accuracy = TrendChart(True, timer, self.data)
        self.timing = TrendChart(False, timer, self.data)
        self.footnote = ft.Text(size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.recent_rows = []
        for _ in range(12):
            self.recent_rows.append(ft.Row([ft.Text(width=44), ft.Text(expand=True),
                ft.Text(width=62, text_align=ft.TextAlign.RIGHT)], spacing=6, visible=False))
        self.recent = ft.ExpansionTile(title="Recent attempts", subtitle="Result and rolling accuracy · newest first",
            expanded=False, maintain_state=True, dense=True, controls=[ft.Column(self.recent_rows, spacing=6)], controls_padding=10)
        summary = ft.ResponsiveRow([m.view for m in self.metrics], spacing=8, run_spacing=8)
        items = [self.coverage, summary]
        if timer:
            self.single = Metric("Projected successful single", {"xs":12,"md":6})
            self.ao5 = Metric("Projected next Ao5", {"xs":12,"md":6})
            items.extend([ft.Text("If your next solve is successful", size=15, weight=ft.FontWeight.W_600),
                          ft.ResponsiveRow([self.single.view, self.ao5.view], spacing=8, run_spacing=8)])
        items.extend([ft.ResponsiveRow([self.accuracy.view, self.timing.view], spacing=12, run_spacing=12),
                      self.footnote, self.recent])
        self.report = ft.Column(items, spacing=9, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        # Filters never move or unmount, even when the selection becomes empty.
        # The report scrolls on its own, leaving the tabs and filters in place.
        self.scroll_area = ft.Column([self.empty, self.report], expand=True, scroll=ft.ScrollMode.AUTO,
                                     horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.report.visible = False
        self.controls = [self.filters, self.scroll_area]

    def open_for(self, context):
        # Start with the activity's context. Reopening the tab preserves an
        # independent statistics filter unless the user changed their training setup.
        if context != self._last_context:
            self._last_context = context
            if self.source == "timer":
                self.session = context
            else:
                self.scheme = context
        self.refresh(update=False)

    def _change_window(self, e):
        self.window = int(e.control.value)
        self.refresh()

    def _change_filter(self, e):
        key = e.control.value
        if self.source == "timer":
            self.session = key
        else:
            self.scheme = None if key == "*" else key[1:]
        self.refresh()

    def _change_phase(self, e):
        self.phase = e.control.value
        self.refresh()

    def _rows(self):
        data = self.data.data
        if self.source == "timer":
            if self.session not in data.practice_sessions:
                self.session = data.active_practice_session
            options = tuple((k, self.data.practice_session_labels.get(k,k)) for k in data.practice_sessions)
            value = self.session
            rows = timer_attempts(data.practice_sessions.get(self.session, ()))
        else:
            names = sorted({a.scheme_name for a in data.progressive_memo_history}, key=str.casefold)
            if self.scheme not in names:
                self.scheme = None
            options = (("*","All schemes"), *[(":"+k,k or "Unnamed scheme") for k in names])
            value = "*" if self.scheme is None else ":"+self.scheme
            rows = memo_attempts(data.progressive_memo_history, self.scheme, self.phase)
        if options != self._filter_options:
            self.filter_picker.options = [ft.DropdownOption(k, label) for k,label in options]
            self._filter_options = options
        self.filter_picker.value = value
        self.window_picker.value, self.phase_picker.value = str(self.window), self.phase
        return rows

    def refresh(self, update=True):
        rows = self._rows()
        self.empty.visible, self.report.visible = not rows, bool(rows)
        if rows:
            self._display(rows)
        if update:
            try:
                page = self.page
            except RuntimeError:  # Late event after leaving the activity.
                return
            if page is not None and self._i in page.session.index:
                self.update()

    def _display(self, rows):
        timer = self.source == "timer"
        s = summarize(rows, self.window)
        total, recent = s.overall, s.recent
        noun = "solve" if timer else "round"
        self.coverage.value = count(total.attempts, noun) + (" in this session" if timer else " in this selection")
        if timer:
            failed = total.attempts - total.correct
            observed = trimmed_time([r.time for r in rows[-5:]]) if len(rows) >= 5 else None
            metrics = [(pct(total.accuracy), f"{count(total.correct,'success','successes')} · {count(failed,'DNF')}"),
                       (clock(total.median), "Median of all successful solves"),
                       (clock(s.best), "Fastest successful solve"),
                       (clock(observed), "Last five recorded solves" if observed is not None else
                        count(5-len(rows), "more solve")+" to record an Ao5")]
            if recent.timed == 0:
                basis = f"No successes in the last {count(recent.attempts, noun)}."
            elif recent.timed == 1:
                basis = f"Only one successful time in the last {count(recent.attempts, noun)}."
            else:
                basis = f"Median of {recent.timed} successes in the last {count(recent.attempts, noun)}."
            self.single.show(clock(recent.median), basis)
            projected = projected_ao5(rows, recent.median)
            if len(rows) < 4:
                why = count(4-len(rows), "more recorded solve")+" needed to project the fifth."
            elif projected == "DNF":
                why = "At least two of the last four solves were DNFs."
            elif projected is None:
                why = "No recent successful time to use for the fifth solve."
            else:
                why = "Last four results + the projected single; best and worst dropped."
            self.ao5.show(clock(projected), why)
        else:
            metrics = [(pct(total.accuracy), f"{total.correct} / {total.scored} scored letters"),
                       (clock(s.memo_median), "Median memorization time"),
                       (clock(s.recall_median), "Median recall time"),
                       (str(s.perfect), f"Out of {count(total.attempts,'round')}")]
        for tile, (value, detail) in zip(self.metrics, metrics):
            tile.show(value, detail)

        sample = count(recent.attempts, noun)
        acc_detail = (f"{recent.correct} of the last {sample} succeeded." if timer else
                      f"{recent.correct} / {recent.scored} letters correct in the last {sample}.")
        self.accuracy.set_series("Rolling success rate" if timer else "Rolling letter accuracy",
                                 pct(recent.accuracy), acc_detail, s.points)
        timing = "solve time" if timer else self.phase+" time"
        time_detail = (f"{count(recent.timed, 'successful time')} in the last {sample}." if timer else
                       f"Median of the last {sample}.")
        self.timing.set_series("Rolling median "+timing, clock(recent.median), time_detail, s.points)
        scope = (f"Chart: latest {PLOT_LIMIT} of {total.attempts} {noun}s." if len(rows)>PLOT_LIMIT else
                 "Chart: all recorded "+noun+"s in this selection.")
        self.footnote.value = scope+" "+("Times include +2 penalties. DNFs count against accuracy and are marked ×."
            if timer else "Letter accuracy uses scored letters. Times include every completed round.")
        latest = list(reversed(s.points[-12:]))
        for i, row in enumerate(self.recent_rows):
            row.visible = i < len(latest)
            if row.visible:
                point, a = latest[i], latest[i].attempt
                result = ("DNF" if a.time is None else clock(a.time)+(" (+2)" if a.plus2 else "")) if timer else (
                    f"{a.correct}/{a.scored} letters · {clock(a.time)}")
                row.controls[0].value, row.controls[1].value, row.controls[2].value = (
                    f"#{point.number}", result, pct(point.rolling.accuracy))
