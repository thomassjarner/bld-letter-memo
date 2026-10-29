"""Portable 3D/2D algorithm playback using Flet's native Canvas."""
import asyncio
import math

import flet as ft
import flet.canvas as cv

from core.algorithms import algorithm_states, changed_stickers, normalized_state, parse_algorithm
from core.tracer import _orient, _solved
from ui.components.cube_projection import project_cube
from ui.theme_colors import apply_palette


@ft.control
class AlgorithmCube(ft.Column):
    def init(self):
        self.spacing = 6
        self.algorithm = None
        self.states = [_solved()]
        self.index = 0
        self.scheme = None
        self.dark_mode = False
        self.targets = ()
        self.affected = None
        self.yaw, self.pitch = -.62, .45
        self.playing = False
        self._token = 0
        self._moving, self._fraction = None, 0
        self._viewport = (460, 300)
        self.mode_picker = ft.Dropdown(value='3D', width=94, height=36, dense=True,
            color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT),
            options=[ft.DropdownOption('3D'), ft.DropdownOption('2D')],
            on_select=lambda e: self._redraw())
        self.letter_switch = ft.Switch(label='Letters', value=True, on_change=lambda e: self._redraw())
        self.focus_switch = ft.Switch(label='Focus case', value=True, on_change=lambda e: self._redraw())
        self.canvas = cv.Canvas(width=460, height=300)
        self.drag_area = ft.Container(width=460, height=300, bgcolor=ft.Colors.TRANSPARENT)
        self.canvas.content = ft.GestureDetector(content=self.drag_area, on_pan_update=self._drag, drag_interval=30)
        self.play_button = ft.IconButton(ft.Icons.PLAY_ARROW, tooltip='Play / pause', on_click=self._toggle)
        self.counter = ft.Text('0 / 0', size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.speed = ft.Dropdown(value='.6', width=100, height=36, dense=True,
            color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT),
            options=[ft.DropdownOption('.3', 'Fast'), ft.DropdownOption('.6', 'Normal'), ft.DropdownOption('1.2', 'Slow')])
        self.move_text = ft.Text('', size=13, font_family='monospace', color=ft.Colors.ON_SURFACE)
        self.stage_buttons = ft.Row(spacing=2, wrap=True)
        self.stage_text = ft.Text('Drag the 3D cube to rotate the view.', size=11, color=ft.Colors.ON_SURFACE_VARIANT)
        self.controls = [
            ft.Row([self.mode_picker, self.letter_switch, self.focus_switch,
                    ft.IconButton(ft.Icons.RESTART_ALT, tooltip='Reset camera', on_click=self._reset_camera)],
                   spacing=6, wrap=True),
            self.canvas,
            ft.Row([ft.IconButton(ft.Icons.FIRST_PAGE, tooltip='First move', on_click=lambda e: self.seek(0)),
                    ft.IconButton(ft.Icons.CHEVRON_LEFT, tooltip='Previous move', on_click=lambda e: self.seek(self.index - 1)),
                    self.play_button,
                    ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip='Next move', on_click=lambda e: self.seek(self.index + 1)),
                    ft.IconButton(ft.Icons.LAST_PAGE, tooltip='Last move', on_click=lambda e: self.seek(len(self.states) - 1)),
                    self.counter, self.speed], spacing=0, wrap=True),
            self.stage_text, self.move_text, self.stage_buttons,
        ]
        self._redraw(update=False)

    def _page(self):
        try:
            return self.page
        except RuntimeError:
            return None

    def _update(self):
        # Canvas paints already have concrete colors. Resolve only the text
        # rebuilt during playback, rather than traversing every polygon/frame.
        apply_palette(self.move_text, self.dark_mode)
        apply_palette(self.stage_text, self.dark_mode)
        apply_palette(self.counter, self.dark_mode)
        if self._page() is not None:
            self.update()

    def load(self, algorithm, *, initial=None, scheme=None, targets=()):
        self.stop(update=False)
        self.algorithm = parse_algorithm(algorithm) if isinstance(algorithm, str) else algorithm
        self.states = algorithm_states(self.algorithm, initial)
        self.affected = {frozenset(s) for s in changed_stickers(normalized_state(self.algorithm)) if len(s) > 1}
        self.scheme, self.targets, self.index = scheme, tuple(targets), 0
        self.stage_buttons.controls = [ft.TextButton(s.label, on_click=lambda e, stage=s: self.play_stage(stage))
                                      for s in self.algorithm.stages]
        self._redraw(update=False)

    def set_viewport(self, width, height=300):
        width, height = max(180, width), max(180, height)
        self._viewport = (width, height)
        self.width = self.canvas.width = self.drag_area.width = width
        self.canvas.height = self.drag_area.height = height
        self._redraw(update=False)

    def _redraw(self, update=True):
        tiles = project_cube(self.states[self.index], *self._viewport, scheme=self.scheme,
            mode=self.mode_picker.value, yaw=self.yaw, pitch=self.pitch,
            letters=self.letter_switch.value, focus=self.focus_switch.value,
            targets=self.targets, affected=self.affected, moving=self._moving, fraction=self._fraction)
        shapes = []
        for tile in tiles:
            elements = [cv.Path.MoveTo(*tile.points[0]), *[cv.Path.LineTo(*p) for p in tile.points[1:]], cv.Path.Close()]
            shapes.append(cv.Path(elements=elements, paint=ft.Paint(color=tile.color)))
            shapes.append(cv.Path(elements=elements, paint=ft.Paint(color=tile.outline,
                style=ft.PaintingStyle.STROKE, stroke_width=2 if tile.outline != '#0A0F0D' else .8)))
            if tile.label:
                x = sum(p[0] for p in tile.points) / 4
                y = sum(p[1] for p in tile.points) / 4
                side = min(math.dist(tile.points[i], tile.points[(i + 1) % 4]) for i in range(4))
                shapes.append(cv.Text(x, y, tile.label, alignment=ft.Alignment.CENTER,
                    style=ft.TextStyle(color=tile.foreground, size=max(9, min(20, side * (.38 if len(tile.label) == 1 else .25))),
                                       weight=ft.FontWeight.W_600)))
        self.canvas.shapes = shapes
        self.counter.value = f'{self.index} / {len(self.states) - 1}'
        if self.algorithm:
            stage = next((s.label for s in self.algorithm.stages if s.start <= self.index < s.end), 'Finished')
            self.stage_text.value = f'{stage} · Drag the 3D cube to rotate the view.'
            self.move_text.spans = [ft.TextSpan(move + ' ', style=ft.TextStyle(
                weight=ft.FontWeight.BOLD if i == self.index else ft.FontWeight.NORMAL,
                decoration=ft.TextDecoration.UNDERLINE if i == self.index else None,
                bgcolor=ft.Colors.PRIMARY_CONTAINER if i == self.index else None,
                color=(ft.Colors.ON_PRIMARY_CONTAINER if i == self.index else
                       next((ft.Colors.PRIMARY if s.label in ('A', 'Undo A') else
                             ft.Colors.TERTIARY if s.label in ('B', 'Undo B') else
                             ft.Colors.ON_SURFACE_VARIANT if 'setup' in s.label.lower() else ft.Colors.ON_SURFACE
                             for s in self.algorithm.stages if s.start <= i < s.end), ft.Colors.ON_SURFACE))))
                for i, move in enumerate(self.algorithm.moves)]
        if update:
            self._update()

    def _drag(self, e):
        if self.mode_picker.value != '3D':
            return
        delta = e.local_delta
        if delta:
            self.yaw += delta.x * .01
            self.pitch = min(1.2, max(-1.2, self.pitch + delta.y * .01))
            self._redraw()

    def _reset_camera(self, e=None):
        self.yaw, self.pitch = -.62, .45
        self._redraw()

    def seek(self, index):
        self.stop(update=False)
        self.index = max(0, min(index, len(self.states) - 1))
        self._redraw()

    def stop(self, update=True):
        self._token += 1
        self.playing = False
        self._moving, self._fraction = None, 0
        self.play_button.icon = ft.Icons.PLAY_ARROW
        if update:
            self._redraw()

    def _toggle(self, e=None):
        if self.playing:
            self.stop()
            return
        if self.index == len(self.states) - 1:
            self.index = 0
        self.play_to(len(self.states) - 1)

    def play_to(self, end):
        self.stop(update=False)
        if self._page() is None:
            return
        self.playing = True
        self.play_button.icon = ft.Icons.PAUSE
        self._page().run_task(self._play, self._token, end)

    def play_stage(self, stage):
        self.seek(stage.start)
        self.play_to(stage.end)

    async def _play(self, token, end):
        while self.index < min(end, len(self.states) - 1) and token == self._token:
            self._moving = self.algorithm.moves[self.index]
            duration = float(self.speed.value)
            frames = 8 if self.mode_picker.value == '3D' else 1
            for frame in range(1, frames + 1):
                if token != self._token:
                    return
                self._fraction = frame / frames
                self._redraw()
                await asyncio.sleep(duration / frames)
            if token != self._token:
                return
            self.index += 1
            self._moving, self._fraction = None, 0
            self._redraw()
        if token == self._token:
            self.stop()
