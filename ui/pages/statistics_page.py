"""Training statistics for existing histories. Filters never change the training setup."""
import flet as ft

from core.training_statistics import WINDOWS, PLOT_LIMIT, format_time, memo_attempts, summarize, timer_attempts
from ui.components.trend_chart import trend_chart
from ui.design import panel
from ui.navigation_motion import route_switcher
from ui.theme_colors import ThemeAwarePage


def pct(value):
    return "—" if value is None else f"{value:.1f}%"


def clock(value):
    return "—" if value is None else format_time(value)


def metric(label, value, detail):
    return panel(ft.Column([
        ft.Text(label, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
        ft.Text(value, size=22, weight=ft.FontWeight.W_600),
        ft.Text(detail, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
    ], spacing=3, tight=True), padding=12, col={"xs":6,"lg":3})


def delta_note(summary, window, accuracy):
    if summary.recent is None or summary.previous is None:
        return f"Two sets of {window} attempts are needed for a comparison."
    last, prev = summary.recent, summary.previous
    curr, old = (last.accuracy, prev.accuracy) if accuracy else (last.median, prev.median)
    if curr is None or old is None:
        return f"No comparison: one of the two sets of {window} has no scored letters." if accuracy else (
            f"No comparison: one of the two sets of {window} has no successful times.")
    diff = curr - old
    if accuracy:
        change = f"{abs(diff):.1f} percentage points {'higher' if diff > 0 else 'lower'}"
    else:
        change = f"{abs(diff)/100:.2f} s {'slower' if diff > 0 else 'faster'}"
    return ("Unchanged" if not diff else change) + f" vs the previous {window} attempts."


@ft.control
class StatisticsPage(ThemeAwarePage, ft.Column):
    back_callback = None

    def init(self):
        self.expand = True
        self.spacing = 12
        self.scroll = ft.ScrollMode.AUTO
        self.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        self.source = "timer"
        self.session = None
        self.scheme = None
        self.window = 12
        self.phase = "total"
        self.back_label = "Back to Practice"
        self.result_views = {k:ft.Column(key=f"statistics_{k}",spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH) for k in ("timer","memo")}
        self.chart_switcher = route_switcher(self.result_views["timer"])
        self.source_picker = ft.SegmentedButton(
            segments=[ft.Segment(value="timer",label="Blind Timer"), ft.Segment(value="memo",label="Progressive Memo")],
            selected=["timer"], show_selected_icon=False, on_change=self._change_source)
        self.filter_picker = ft.Dropdown(width=190, dense=True, on_select=self._change_filter)
        self.window_picker = ft.Dropdown(width=167, dense=True, label="Rolling window",
            options=[ft.DropdownOption(str(w), f"{w} attempts") for w in WINDOWS],
            value=str(self.window), on_select=self._change_window)
        self.phase_picker = ft.Dropdown(width=155, dense=True, label="Time trend",
            options=[ft.DropdownOption(k, v) for k,v in
                     (("total","Total time"),("memo","Memo time"),("recall","Recall time"))],
            value="total", on_select=self._change_phase)

    def select(self, source, *, session=None, scheme=None):
        self.source = source
        if session is not None:
            self.session = session
        if source == "memo":
            self.scheme = scheme

    def _change_source(self, e):
        self.source = e.control.selected[0]
        self.refresh()

    def _change_window(self, e):
        self.window = int(e.control.value)
        self.refresh()

    def _change_filter(self, e):
        if self.source == "timer":
            self.session = e.control.value
        else:
            key = e.control.value
            self.scheme = None if key == "*" else key[1:]
        self.refresh()

    def _change_phase(self, e):
        self.phase = e.control.value
        self.refresh()

    def refresh(self, update=True):
        state, data = self.data, self.data.data
        timer = self.source == "timer"
        self.source_picker.selected = [self.source]
        if timer:
            labels = state.practice_session_labels
            if self.session not in data.practice_sessions:
                self.session = data.active_practice_session
            self.filter_picker.label = "Timer session"
            self.filter_picker.options = [ft.DropdownOption(k, labels.get(k,k)) for k in data.practice_sessions]
            self.filter_picker.value = self.session
            attempts = timer_attempts(data.practice_sessions.get(self.session, ()))
        else:
            names = sorted({a.scheme_name for a in data.progressive_memo_history}, key=str.casefold)
            if self.scheme not in names:
                self.scheme = None
            self.filter_picker.label = "Saved letter scheme"
            self.filter_picker.options = [ft.DropdownOption("*","All schemes")] + [
                ft.DropdownOption(":"+k, k or "Unnamed scheme") for k in names]
            self.filter_picker.value = "*" if self.scheme is None else ":"+self.scheme
            attempts = memo_attempts(data.progressive_memo_history, self.scheme, self.phase)
        self.window_picker.value, self.phase_picker.value = str(self.window), self.phase
        controls = [
            ft.Row([ft.IconButton(ft.Icons.ARROW_BACK, tooltip=self.back_label, on_click=lambda e:self.back_callback()),
                    ft.Text("Training statistics", size=24, weight=ft.FontWeight.W_600, expand=True)], spacing=6),
            ft.Row([self.source_picker], wrap=True),
            ft.Row([self.filter_picker, self.window_picker] + ([] if timer else [self.phase_picker]),
                   spacing=12, run_spacing=12, wrap=True),
        ]
        results = []
        if not attempts:
            results.append(panel(ft.Column([
                ft.Icon(ft.Icons.INSIGHTS, color=ft.Colors.PRIMARY, size=28),
                ft.Text("No saved solves in this session yet." if timer else "No saved memo attempts in this selection yet.",
                        size=17, weight=ft.FontWeight.W_600),
                ft.Text("Your first saved attempt will appear here. The rolling line starts once a full window is available.", size=14),
            ], spacing=8), padding=18))
        else:
            s = summarize(attempts, self.window)
            overall, recent = s.overall, s.recent
            if timer:
                cards = [metric("Solve success rate", pct(overall.accuracy),
                                f"{overall.correct} successes · {overall.attempts-overall.correct} DNFs"),
                         metric("Typical solve", clock(overall.median), "Median of successful times"),
                         metric("Best single", clock(s.best), "Fastest successful time"),
                         metric("Attempts", str(overall.attempts), "This timer session")]
            else:
                cards = [metric("Letter accuracy", pct(overall.accuracy), f"{overall.correct} / {overall.scored} scored letters"),
                         metric("Typical memo", clock(s.memo_median), "Median memorization time"),
                         metric("Typical recall", clock(s.recall_median), "Median typed recall time"),
                         metric("Perfect rounds", str(s.perfect), f"Out of {overall.attempts} attempts")]
            results.append(ft.ResponsiveRow(cards, spacing=8, run_spacing=8))
            timing = "solve time" if timer else {"total":"total time","memo":"memo time","recall":"recall time"}[self.phase]
            wait = f"{overall.attempts} / {self.window} attempts"
            head_acc = pct(recent.accuracy) if recent else wait
            head_time = (clock(recent.median) if recent and recent.median is not None
                         else "No successful times" if recent else wait)
            sample = (f"{recent.correct}/{recent.scored} "+("successful solves. " if timer else "scored letters correct. ")) if recent else ""
            time_sample = f"{recent.timed} timed "+("solve" if recent.timed==1 else "solves")+". " if recent and timer else ""
            results.append(ft.ResponsiveRow([
                trend_chart("Rolling success rate" if timer else "Rolling letter accuracy", head_acc,
                            sample+delta_note(s,self.window,True), s.points, True, timer,self.window,state),
                trend_chart("Rolling median " + timing, head_time, time_sample+delta_note(s,self.window,False),
                            s.points,False,timer,self.window,state),
            ], spacing=12, run_spacing=12))
            scope = f"Showing the latest {PLOT_LIMIT} of {len(attempts)} attempts." if len(attempts)>PLOT_LIMIT else (
                f"Showing all {len(attempts)} attempts.")
            results.append(ft.Text(scope+" Summary cards use the whole selection. "+
                ("A +2 counts as a success with two seconds added; DNFs count against accuracy and have no time in the trend."
                 if timer else "Accuracy counts letters, so longer rounds contribute more. Times include all completed rounds."),
                 size=13, color=ft.Colors.ON_SURFACE_VARIANT))
            rows = []
            for p in reversed(s.points[-12:]):
                a = p.attempt
                result = ("DNF" if a.time is None else clock(a.time)+(" (+2)" if a.plus2 else "")) if timer else (
                    f"{a.correct}/{a.scored} letters · {clock(a.time)}")
                rolling = pct(p.rolling.accuracy) if p.rolling else "—"
                rows.append(ft.Row([ft.Text(f"#{p.number}", width=52), ft.Text(result,expand=True),
                                    ft.Text(rolling, width=66, text_align=ft.TextAlign.RIGHT)], spacing=8))
            results.append(ft.ExpansionTile(title="Recent attempts", subtitle="Result and rolling accuracy · newest first",
                expanded=False, dense=True, controls=[ft.Column(rows, spacing=8)], controls_padding=12))
        result_view = self.result_views[self.source]
        result_view.controls = results
        self.chart_switcher.content = result_view
        self.controls = [*controls, self.chart_switcher]
        if update and self.page is not None:
            self.update()
