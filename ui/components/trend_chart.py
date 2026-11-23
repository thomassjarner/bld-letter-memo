"""A responsive chart with a persistent canvas, axes and labels."""
import flet as ft
import flet.canvas as cv

from core.training_statistics import format_time
from ui.design import panel
from ui.theme_colors import apply_palette


PLOT_HEIGHT = 146
TOP, BOTTOM, MISS_Y = 8, 119, 138


def chart_bounds(values, percent):
    if percent or not values:
        return 0, 100
    lo, hi = min(values), max(values)
    pad = max(1, (hi - lo) * .07) if lo != hi else max(100, hi * .05)
    return max(0, int(lo - pad)), int(hi + pad) + 1


def note(text="", size=12):
    return ft.Text(text, size=size, color=ft.Colors.ON_SURFACE_VARIANT)


def legend_mark(label, width, height, color):
    return ft.Row([ft.Container(width=width, height=height, border_radius=3, bgcolor=color),
                   note(label)], spacing=5, tight=True)


class TrendChart:
    def __init__(self, percent, timer, state):
        self.percent, self.timer, self.state = percent, timer, state
        self.width = 220
        self.series = None
        self.title = ft.Text(size=17, weight=ft.FontWeight.W_600)
        self.headline = ft.Text(size=21, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY)
        self.description = note(size=13)
        self.axis = [ft.Text(left=0, top=y-8, size=11, color=ft.Colors.ON_SURFACE_VARIANT)
                     for y in (TOP, (TOP+BOTTOM)/2, BOTTOM)]
        self.canvas = cv.Canvas(height=PLOT_HEIGHT, expand=True, on_resize=self._resize, resize_interval=60)
        self.start, self.end = note(), note()
        self.x_axis = ft.Row([self.start, self.end], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        self.observed_key = legend_mark("Attempt", 6, 6, ft.Colors.ON_SURFACE_VARIANT)
        self.line_key = legend_mark("Cumulative", 17, 3, ft.Colors.PRIMARY)
        legend = [self.observed_key, self.line_key]
        if timer and not percent:
            legend.append(ft.Row([ft.Text("×", size=16, color=ft.Colors.ERROR), note("DNF")], spacing=4, tight=True))
        if not percent:
            legend.append(note("Lower is faster"))
        self.view = panel(ft.Column([
            self.title, self.headline, self.description,
            ft.Row([ft.Stack(self.axis, width=56, height=PLOT_HEIGHT), self.canvas], spacing=4, height=PLOT_HEIGHT),
            ft.Container(self.x_axis, padding=ft.Padding.only(left=60)),
            ft.Row(legend, spacing=14, run_spacing=3, wrap=True),
        ], spacing=5, tight=True), col={"xs":12,"lg":6}, padding=14)

    def set_series(self, title, headline, detail, points, window=None):
        self.title.value, self.headline.value, self.description.value = title, headline, detail
        grouped = any(p.group.attempts > 1 for p in points)
        self.observed_key.controls[1].value = ("Group rate" if self.percent else "Group median") if grouped else "Attempt"
        self.line_key.controls[1].value = "Cumulative" if window is None else f"Rolling {window}"
        # Cumulative endpoint numbers already appear in the summary above.
        self.headline.visible = window is not None
        raw = [p.group.accuracy if self.percent else p.group.median for p in points]
        trend = [p.rolling.accuracy if self.percent else p.rolling.median for p in points]
        values = [v for v in raw+trend if v is not None]
        lo, hi = chart_bounds(values, self.percent)
        self.numbers = [p.number for p in points]
        self.misses = [i for i,p in enumerate(points) if p.group.timed < p.group.attempts]
        self.series = (raw, trend, lo, hi, bool(values))
        for label, value in zip(self.axis, (hi, (hi+lo)/2, lo)):
            label.visible = bool(values)
            label.value = f"{value:.0f}%" if self.percent else format_time(value)
        single = len(points) == 1
        self.start.value = f"Attempt {points[0].number}" if single else f"#{points[0].number}"
        self.end.value, self.end.visible = f"#{points[-1].number}", not single
        self.x_axis.alignment = ft.MainAxisAlignment.CENTER if single else ft.MainAxisAlignment.SPACE_BETWEEN
        self._draw()

    def _resize(self, e):
        width = max(12, round(e.width))
        if width == self.width or e.width <= 0:
            return
        self.width = width
        if not self.series:
            return
        # A resize can arrive after a tab change. Never update a detached chart.
        try:
            page = self.canvas.page
        except RuntimeError:
            return
        if page is None or self.canvas._i not in page.session.index:
            return
        self._draw()
        apply_palette(self.canvas, self.state.data.dark_mode, self.state.data.light_theme)
        self.canvas.update()

    def _draw(self):
        raw, trend, low, high, has_values = self.series
        width = self.width
        span = self.numbers[-1] - self.numbers[0]
        def x(i): return width/2 if not span else 5+(width-10)*(self.numbers[i]-self.numbers[0])/span
        def y(v): return BOTTOM-(v-low)/(high-low)*(BOTTOM-TOP)
        def stroke(color, weight):
            return ft.Paint(color=color, stroke_width=weight, style=ft.PaintingStyle.STROKE,
                            stroke_cap=ft.StrokeCap.ROUND, stroke_join=ft.StrokeJoin.ROUND)
        grid = stroke(ft.Colors.OUTLINE_VARIANT, 1)
        shapes = [cv.Line(0, yy, width, yy, paint=grid)
                  for yy in ((TOP,(TOP+BOTTOM)/2,BOTTOM) if has_values else (BOTTOM,))]
        dots = [ft.Offset(x(i), y(v)) for i,v in enumerate(raw) if v is not None]
        if dots:
            shapes.append(cv.Points(dots, paint=stroke(ft.Colors.ON_SURFACE_VARIANT, 3)))
        line, marks = [], []
        previous = None
        for i, v in enumerate(trend):
            if v is not None:
                marks.append(ft.Offset(x(i), y(v)))
                line.append((cv.Path.MoveTo if previous is None else cv.Path.LineTo)(x(i), y(v)))
            previous = v
        if line:
            shapes.extend([cv.Path(line, paint=stroke(ft.Colors.PRIMARY, 2.6)),
                           cv.Points(marks, paint=stroke(ft.Colors.PRIMARY, 3.5))])
        if self.timer and not self.percent:
            crosses = []
            for i in self.misses:
                xx = x(i)
                crosses.extend([cv.Path.MoveTo(xx-2.5,MISS_Y-2.5),cv.Path.LineTo(xx+2.5,MISS_Y+2.5),
                                cv.Path.MoveTo(xx-2.5,MISS_Y+2.5),cv.Path.LineTo(xx+2.5,MISS_Y-2.5)])
            if crosses:
                shapes.append(cv.Path(crosses, paint=stroke(ft.Colors.ERROR, 1.7)))
        self.canvas.shapes = shapes
