"""A responsive Flet canvas; charts draw at most 100 attempts in a few paths."""
import flet as ft
import flet.canvas as cv

from core.training_statistics import format_time
from ui.design import panel
from ui.theme_colors import apply_palette


PLOT_HEIGHT = 146
TOP, BOTTOM, MISS_Y = 8, 119, 138


def chart_bounds(values, percent):
    if percent:
        return 0, 100
    if not values:
        return 0, 100
    lo, hi = min(values), max(values)
    pad = max(1, (hi - lo) * .07) if lo != hi else max(100, hi * .05)
    return max(0, int(lo - pad)), int(hi + pad) + 1


def trend_chart(title, headline, description, points, percent, timer, window, state):
    number = lambda v: f"{v:.0f}%" if percent else format_time(v)
    raw = [(100 * p.attempt.correct / p.attempt.scored if p.attempt.scored else None)
           if percent else p.attempt.time for p in points]
    trend = [(p.rolling.accuracy if percent else p.rolling.median) if p.rolling else None for p in points]
    values = [v for v in raw + trend if v is not None]
    low, high = chart_bounds(values, percent)
    misses = [i for i, p in enumerate(points) if timer and not percent and p.attempt.time is None]

    def draw(width):
        def x(i): return width / 2 if len(points) == 1 else 5 + (width-10) * i / (len(points)-1)
        def y(v): return BOTTOM - (v-low)/(high-low) * (BOTTOM-TOP)
        def stroke(color, weight):
            return ft.Paint(color=color, stroke_width=weight, style=ft.PaintingStyle.STROKE,
                            stroke_cap=ft.StrokeCap.ROUND, stroke_join=ft.StrokeJoin.ROUND)
        grid = stroke(ft.Colors.OUTLINE_VARIANT, 1)
        shapes = [cv.Line(0, yy, width, yy, paint=grid)
                  for yy in ((TOP,(TOP+BOTTOM)/2,BOTTOM) if values else (BOTTOM,))]
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
        if misses:
            crosses = []
            for i in misses:
                xx = x(i)
                crosses.extend([cv.Path.MoveTo(xx-2.5,MISS_Y-2.5),cv.Path.LineTo(xx+2.5,MISS_Y+2.5),
                                cv.Path.MoveTo(xx-2.5,MISS_Y+2.5),cv.Path.LineTo(xx+2.5,MISS_Y-2.5)])
            shapes.append(cv.Path(crosses, paint=stroke(ft.Colors.ERROR, 1.7)))
        return shapes

    def resize(e):
        width = max(12, round(e.width))
        if width == canvas._draw_width: return
        canvas._draw_width = width
        canvas.shapes = draw(width)
        apply_palette(canvas, state.data.dark_mode, state.data.light_theme)
        if canvas.parent is not None:
            canvas.update()

    canvas = cv.Canvas(draw(220), height=PLOT_HEIGHT, expand=True, on_resize=resize, resize_interval=50)
    canvas._draw_width = 220
    def axis_text(value, pos):
        return ft.Text(number(value), left=0, top=pos-8, size=11, color=ft.Colors.ON_SURFACE_VARIANT)
    axis = ft.Stack(([axis_text(high, TOP), axis_text((high+low)/2, (TOP+BOTTOM)/2), axis_text(low, BOTTOM)] if values else []),
                    width=56, height=PLOT_HEIGHT)
    if points[0].number == points[-1].number:
        labels = [ft.Text(f"Attempt {points[0].number}", size=12)]
    else:
        labels = [ft.Text(f"#{points[0].number}", size=12), ft.Text(f"#{points[-1].number}", size=12)]
    def legend_mark(label, width, height, color):
        return ft.Row([ft.Container(width=width,height=height,border_radius=3,bgcolor=color),
                       ft.Text(label, size=12, color=ft.Colors.ON_SURFACE_VARIANT)],spacing=5,tight=True)
    legend = [legend_mark("Attempt",6,6,ft.Colors.ON_SURFACE_VARIANT),
              legend_mark(f"Last {window}",17,3,ft.Colors.PRIMARY)]
    if timer and not percent:
        legend.append(ft.Row([ft.Text("×",size=16,color=ft.Colors.ERROR),ft.Text("DNF",size=12)],spacing=4,tight=True))
    if not percent:
        legend.append(ft.Text("Lower is faster",size=12,color=ft.Colors.ON_SURFACE_VARIANT))
    return panel(ft.Column([
        ft.Text(title, size=17, weight=ft.FontWeight.W_600),
        ft.Text(headline, size=21, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
        ft.Text(description, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
        ft.Row([axis, canvas], spacing=4, height=PLOT_HEIGHT),
        ft.Container(ft.Row(labels, alignment=ft.MainAxisAlignment.SPACE_BETWEEN if len(labels)>1
                            else ft.MainAxisAlignment.CENTER), padding=ft.Padding.only(left=60)),
        ft.Row(legend, spacing=14, run_spacing=3, wrap=True),
        *([] if values else [ft.Text("No scored letters in the plotted attempts." if percent else
            "No successful times in the plotted attempts.",size=12,color=ft.Colors.ON_SURFACE_VARIANT)]),
    ], spacing=5, tight=True), col={"xs":12,"lg":6}, padding=14)
