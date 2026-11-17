"""Retained Flet drawing primitives for the interactive cube.

Keep a bounded high-water set of paths and labels per viewer. Updating a
coordinate on a mounted path lets the client patch it instead of replacing
hundreds of drawing objects on every pan event.
"""
import math
import flet as ft
import flet.canvas as cv

from ui.components.cube_projection import RIM


class CubePainter:
    def __init__(self, canvas):
        self.canvas = canvas
        self.paths = []
        self.texts = []

    def draw(self, tiles, *, net=False):
        shapes = []
        n_path = n_text = 0
        def polygon(points, color, stroke=0):
            nonlocal n_path
            if n_path == len(self.paths):
                shape = cv.Path(elements=[cv.Path.MoveTo(0, 0), cv.Path.LineTo(0, 0),
                    cv.Path.LineTo(0, 0), cv.Path.LineTo(0, 0), cv.Path.Close()])
                self.paths.append(shape)
            shape = self.paths[n_path]
            n_path += 1
            ink = color, stroke
            if getattr(shape, '_cube_ink', None) != ink:
                shape.paint = ft.Paint(color=color, stroke_width=stroke, style=ft.PaintingStyle.STROKE
                                       if stroke else ft.PaintingStyle.FILL)
                shape._cube_ink = ink
            for element, (x,y) in zip(shape.elements, points):
                element.x, element.y = x, y
            shapes.append(shape)

        for tile in tiles:
            points = tile.points
            polygon(points, tile.color)
            if net or tile.outline != RIM:
                polygon(points, tile.outline, .8 if tile.outline == RIM else 2)
            if not tile.label: continue
            (x0,y0), (x1,y1), (x2,y2), _ = points
            w, h = math.hypot(x1-x0,y1-y0), math.hypot(x2-x1,y2-y1)
            # Foreshortened stickers should not leave floating text at the silhouette.
            area = abs((x1-x0)*(y2-y1) - (y1-y0)*(x2-x1))
            if not net and area / max(w, h, .01) < 8: continue
            if n_text == len(self.texts):
                self.texts.append(cv.Text(0,0,'', alignment=ft.Alignment.CENTER,
                                          style=ft.TextStyle(weight=ft.FontWeight.W_600)))
            shape = self.texts[n_text]
            n_text += 1
            shape.x, shape.y = (x0+x2)/2, (y0+y2)/2
            shape.text = tile.label
            shape.style.color = tile.foreground
            shape.style.size = max(9,min(20,round(min(w,h)*(.38 if len(tile.label)==1 else .25))))
            shapes.append(shape)
        old = self.canvas.shapes
        if len(old) != len(shapes) or any(a is not b for a,b in zip(old,shapes)):
            self.canvas.shapes = shapes
