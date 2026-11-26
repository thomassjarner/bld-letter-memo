"""A responsive chart with a persistent canvas and pointer/touch readout."""
from core.messages import message, compose
from ui.language import present
from bisect import bisect_left

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
    return ft.Text(present(text), size=size, color=ft.Colors.ON_SURFACE_VARIANT)


def legend_mark(label, width, height, color):
    return ft.Row([ft.Container(width=width, height=height, border_radius=3, bgcolor=color),
                   note(label)], spacing=5, tight=True)


class TrendChart:
    def __init__(self, percent, timer, state):
        self.percent, self.timer, self.state = percent, timer, state
        self.width = 220
        self.series = None
        self.ao5 = False
        self.points = self.numbers = ()
        self.selected_index = None
        self.idle = ""
        self.title = ft.Text(size=17, weight=ft.FontWeight.W_600)
        self.headline = ft.Text(size=21, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY)
        self.description = note(size=13)
        self.axis = [ft.Text(left=0, top=y-8, size=11, color=ft.Colors.ON_SURFACE_VARIANT)
                     for y in (TOP, (TOP+BOTTOM)/2, BOTTOM)]
        self.canvas = cv.Canvas(height=PLOT_HEIGHT, on_resize=self._resize, resize_interval=60)
        self.guide = ft.Container(left=0, top=TOP, bottom=PLOT_HEIGHT-MISS_Y, width=1.5,
                                  bgcolor=ft.Colors.PRIMARY, opacity=0, ignore_interactions=True)
        # No scroll or drag recognizer here: a wheel or vertical swipe over the
        # plot belongs to the report. A tap leaves the touch readout on screen.
        self.inspector = ft.GestureDetector(content=ft.Container(bgcolor=ft.Colors.TRANSPARENT),
            mouse_cursor=ft.MouseCursor.PRECISE, hover_interval=32, on_enter=self._inspect,
            on_hover=self._inspect, on_exit=self._leave, on_tap_up=self._inspect)
        plot = ft.Stack([self.canvas,self.guide,self.inspector], fit=ft.StackFit.EXPAND,
                        height=PLOT_HEIGHT, expand=True)
        self.start, self.end = note(), note()
        self.x_axis = ft.Row([self.start, self.end], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        self.observed_key = legend_mark(message('Attempt'), 6, 6, ft.Colors.ON_SURFACE_VARIANT)
        self.line_key = legend_mark(message('Cumulative'), 17, 3, ft.Colors.PRIMARY)
        legend = [self.observed_key, self.line_key]
        if timer and not percent:
            legend.append(ft.Row([ft.Text("×", size=16, color=ft.Colors.ERROR), note(message('DNF'))], spacing=4, tight=True))
        if not percent:
            legend.append(note(message('Lower is faster')))
        self.view = panel(ft.Column([
            self.title, self.headline, ft.Container(self.description,height=52),
            ft.Row([ft.Stack(self.axis, width=56, height=PLOT_HEIGHT), plot], spacing=4, height=PLOT_HEIGHT),
            ft.Container(self.x_axis, padding=ft.Padding.only(left=60)),
            ft.Row(legend, spacing=14, run_spacing=3, wrap=True),
        ], spacing=5, tight=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH), padding=14)

    def set_series(self, title, headline, detail, points, window=None, *, ao5=False):
        self.title.value, self.headline.value = present(title), present(headline)
        self.points = points
        self.ao5 = ao5
        self.idle = detail + message(' Hover or tap for values.')
        self.clear_inspection()
        grouped = any(p.group.attempts > 1 for p in points)
        self.observed_key.controls[1].value = present((message('Group rate') if self.percent else message('Group median')) if grouped else message('Attempt'))
        self.line_key.controls[1].value = present(message('Cumulative') if window is None else message('Rolling {0}', window))
        self.observed_key.visible = not ao5
        if ao5:
            self.line_key.controls[1].value = present(message('Group median Ao5') if grouped else message('Recorded Ao5'))
        # Cumulative endpoint numbers already appear in the summary above.
        self.headline.visible = not ao5 and window is not None
        raw = [None if ao5 else p.group.accuracy if self.percent else p.group.median for p in points]
        trend = [p.rolling.accuracy if self.percent else p.rolling.median for p in points]
        values = [v for v in raw+trend if v is not None]
        lo, hi = chart_bounds(values, self.percent)
        self.numbers = [p.number for p in points]
        self.misses = [i for i,p in enumerate(points) if p.group.timed < p.group.attempts]
        self.series = (raw, trend, lo, hi, bool(values))
        for label, value in zip(self.axis, (hi, (hi+lo)/2, lo)):
            label.visible = bool(values)
            label.value = present(compose('{0:.0f}%', value) if self.percent else format_time(value))
        single = len(points) == 1
        self.start.value = present(message('Attempt {0}', points[0].number) if single else compose('#{0}', points[0].number))
        self.end.value, self.end.visible = present(compose('#{0}', points[-1].number)), not single
        self.x_axis.alignment = ft.MainAxisAlignment.CENTER if single else ft.MainAxisAlignment.SPACE_BETWEEN
        self._draw()

    def clear_inspection(self):
        self.selected_index = None
        self.guide.opacity = 0
        self.description.value = present(self.idle)

    def _x(self, i):
        span = self.numbers[-1] - self.numbers[0]
        return self.width/2 if not span else 5+(self.width-10)*(self.numbers[i]-self.numbers[0])/span

    def _nearest(self, x):
        # Use the same logical pixels and actual attempt numbers as the canvas,
        # including unequal-size bins at the end of a long session.
        first,last = self.numbers[0],self.numbers[-1]
        target = first+(x-5)*(last-first)/(self.width-10)
        right = min(bisect_left(self.numbers,target),len(self.numbers)-1)
        return right-1 if right and target-self.numbers[right-1] <= self.numbers[right]-target else right

    def _readout(self, i):
        p = self.points[i]
        group,a = p.group,p.attempt
        def rate(v): return "—" if v is None else compose('{0:.1f}%', v)
        def time(v): return "—" if v is None else format_time(v)
        if self.ao5:
            if group.attempts == 1:
                result = time(a.time) if a.time is not None else message('DNF')
                return message('Ao5 · {0}\nAttempts #{1}–{2}', result, p.number - 4, p.number)
            return (message('Ao5s ending #{0}–{1} · Median {2}\n{3}/{4} valid averages', p.number - group.attempts + 1, p.number, time(group.median), group.timed, group.attempts))
        if group.attempts > 1:
            label = compose('#{0}–{1}', p.number - group.attempts + 1, p.number)
            value = (compose('{0} · {1}/{2}', rate(group.accuracy), group.correct, group.scored) if self.percent else
                     message('Median {0}', time(group.median)))
            if self.timer and not self.percent and (misses := group.attempts-group.timed):
                value += message(' · {0} DNF', misses) + (message("s") if misses != 1 else "")
        else:
            label = compose('#{0}', p.number)
            if self.timer and a.time is None:
                result = message('DNF') if a.dnf_elapsed is None else f"DNF ({time(a.dnf_elapsed)})"
            else:
                result = time(a.time)
            if a.plus2:
                result += " (+2)"
            if self.percent:
                value = rate(group.accuracy) + " · " + (result if self.timer else message('{0}/{1} letters', a.correct, a.scored))
            else:
                value = result
        trend = rate(p.rolling.accuracy) if self.percent else time(p.rolling.median)
        return compose('{0} · {1}\n{2}: {3}', label, value, self.line_key.controls[1].value, trend)

    def _update_if_mounted(self, *controls):
        try:
            page = self.canvas.page
        except RuntimeError:
            return
        if page is not None and self.canvas._i in page.session.index:
            page.update(*controls)

    def _inspect(self, e):
        ft.context.disable_auto_update()
        if not self.points or e.local_position is None:
            return
        i = self._nearest(e.local_position.x)
        if i != self.selected_index:
            self.selected_index = i
            self.guide.left, self.guide.opacity = self._x(i)-.75, .8
            self.description.value = present(self._readout(i))
            self._update_if_mounted(self.guide,self.description)

    def _leave(self, e):
        ft.context.disable_auto_update()
        if self.selected_index is not None:
            self.clear_inspection()
            self._update_if_mounted(self.guide,self.description)

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
        if self.selected_index is not None:
            self.guide.left = self._x(self.selected_index)-.75
        apply_palette(self.canvas, self.state.data.dark_mode, self.state.data.light_theme)
        page.update(self.canvas,self.guide)

    def _draw(self):
        raw, trend, low, high, has_values = self.series
        width = self.width
        x = self._x
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
