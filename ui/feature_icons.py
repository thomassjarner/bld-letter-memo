"""Original line icons, drawn natively and recolored with the site theme.

Semantic paint colors follow the existing palette resolver in all light
themes and dark mode. No image assets or extra dependencies are needed.
"""
import flet as ft
import flet.canvas as cv


FEATURE_NAMES = (
    "home", "schemes", "pairs", "memo", "walkthrough", "library",
    "practice", "timer", "settings", "progressive", "cases", "trainer",
    "playground", "lesson", "delayed", "drill",
)


def feature_icon(name, size=22, *, selected=False, muted=False):
    """A decorative 24-unit glyph; its parent supplies the accessible label."""
    if name not in FEATURE_NAMES:
        raise ValueError(f"Unknown feature icon: {name}")
    scale = size / 24
    foreground = (ft.Colors.ON_SURFACE_VARIANT if muted else
                  ft.Colors.ON_PRIMARY_CONTAINER if selected else ft.Colors.PRIMARY)
    accent = foreground if selected or muted else ft.Colors.TERTIARY
    shapes = []

    def paint(color, filled=False):
        return ft.Paint(color=color, stroke_width=1.75 * scale,
                        style=ft.PaintingStyle.FILL if filled else ft.PaintingStyle.STROKE,
                        stroke_cap=ft.StrokeCap.ROUND, stroke_join=ft.StrokeJoin.ROUND)

    def line(points, color=foreground, closed=False, filled=False):
        elements = [cv.Path.MoveTo(points[0][0] * scale, points[0][1] * scale)]
        elements.extend(cv.Path.LineTo(x * scale, y * scale) for x, y in points[1:])
        if closed:
            elements.append(cv.Path.Close())
        shapes.append(cv.Path(elements, paint=paint(color, filled)))

    def rect(x, y, width, height, color=foreground, radius=1.5, filled=False):
        shapes.append(cv.Rect(x * scale, y * scale, width * scale, height * scale,
                              border_radius=radius * scale, paint=paint(color, filled)))

    def circle(x, y, radius, color=foreground, filled=False):
        shapes.append(cv.Circle(x * scale, y * scale, radius * scale, paint=paint(color, filled)))

    def cube(x=3, y=3, width=18, height=18):
        cx, cy = x + width / 2, y + height / 2
        line([(cx, y), (x + width, y + height / 4), (x + width, y + height * .75),
              (cx, y + height), (x, y + height * .75), (x, y + height / 4)], closed=True)
        line([(x, y + height / 4), (cx, cy), (x + width, y + height / 4)])
        line([(cx, cy), (cx, y + height)])

    if name == "home":
        line([(2.5, 10), (12, 2.5), (21.5, 10)])
        line([(5, 9), (5, 21), (19, 21), (19, 9)])
        rect(9, 13, 6, 8, accent, radius=.8)
    elif name == "schemes":
        rect(3, 3, 18, 18, radius=2)
        for a in (9, 15):
            line([(a, 3), (a, 21)])
            line([(3, a), (21, a)])
        rect(4.8, 4.8, 2.5, 2.5, accent, radius=.4, filled=True)
        rect(16.7, 16.7, 2.5, 2.5, accent, radius=.4, filled=True)
    elif name in {"pairs", "progressive", "drill"}:
        rect(2, 5, 8, 13, radius=1.5)
        rect(14, 5, 8, 13, accent, radius=1.5)
        line([(4.1, 14), (6, 8.5), (8, 14)])
        line([(4.8, 12), (7.2, 12)])
        line([(16.5, 8.5), (16.5, 14), (19, 14), (20, 13), (19, 11.3),
              (16.5, 11.3), (19, 11.3), (19.8, 10), (19, 8.5), (16.5, 8.5)], accent)
        if name == "progressive":
            line([(8, 21), (15, 21)], accent)
            line([(13, 19), (15, 21), (13, 23)], accent)
        elif name == "drill":
            line([(10.5, 2), (13.5, 2), (11, 5), (14, 5)], accent)
        else:
            line([(10, 11.5), (14, 11.5)])
    elif name == "memo":
        line([(5, 4), (17, 4), (17, 12), (7, 12), (7, 20), (19, 20)])
        circle(5, 4, 2, filled=True)
        circle(17, 12, 2, accent, filled=True)
        line([(16, 17), (19, 20), (16, 23)], accent)
    elif name == "walkthrough":
        cube(2, 2, 15, 17)
        circle(17.5, 17.5, 5, accent, filled=True)
        line([(16.2, 14.9), (20, 17.5), (16.2, 20.1)],
             ft.Colors.SURFACE_CONTAINER_LOWEST, closed=True, filled=True)
    elif name == "library":
        line([(12, 6), (8, 3.5), (2.5, 3.5), (2.5, 19), (8, 19), (12, 21),
              (16, 19), (21.5, 19), (21.5, 3.5), (16, 3.5), (12, 6), (12, 21)])
        line([(5.5, 8), (8.5, 8), (8.5, 14)], accent)
        line([(15, 8), (18.5, 8)], accent)
        line([(15, 12), (18.5, 12)], accent)
    elif name == "practice":
        rect(3, 3.5, 13.5, 17, radius=2)
        line([(6.5, 8), (12.5, 8)])
        line([(6.5, 12), (10.5, 12)])
        circle(17, 17, 5, accent)
        line([(14.5, 17), (16.3, 18.8), (20, 15)], accent)
    elif name in {"timer", "delayed"}:
        if name == "delayed":
            line([(5, 3), (19, 3)], accent)
            line([(5, 21), (19, 21)], accent)
            line([(7, 3), (7, 7), (16.5, 17), (16.5, 21)])
            line([(17, 3), (17, 7), (7.5, 17), (7.5, 21)])
        else:
            circle(12, 14, 8.2)
            line([(9, 2), (15, 2)], accent)
            line([(12, 2), (12, 5.5)], accent)
            line([(18.5, 5.5), (21, 8)], accent)
            line([(12, 9), (12, 14), (16, 16)], accent)
    elif name == "settings":
        for x, y in ((5, 8), (12, 16), (19, 8)):
            line([(x, 3), (x, y - 2.5)])
            line([(x, y + 2.5), (x, 21)])
            circle(x, y, 2.5, accent)
    elif name in {"cases", "trainer"}:
        cube(3, 2, 18, 19)
        for x, y in ((12, 2), (3, 16.25), (21, 16.25)):
            circle(x, y, 1.8, accent, filled=True)
        if name == "trainer":
            line([(9, 9.5), (11, 11.5), (15, 7.5)], accent)
    elif name == "playground":
        line([(8, 2.5), (16, 2.5)], accent)
        line([(9, 2.5), (9, 9), (3, 19), (4, 21), (20, 21), (21, 19),
              (15, 9), (15, 2.5)])
        line([(6.5, 15), (17.5, 15)], accent)
        circle(11, 17.5, 1, accent, filled=True)
        circle(14.5, 12, 1, accent, filled=True)
    elif name == "lesson":
        line([(8, 3), (4, 3), (4, 21), (8, 21)])
        line([(16, 3), (20, 3), (20, 21), (16, 21)])
        line([(8.5, 8), (15.5, 8), (13, 5.5)], accent)
        line([(15.5, 16), (8.5, 16), (11, 18.5)], accent)
    return cv.Canvas(shapes, width=size, height=size, key=f"feature_icon_{name}")
