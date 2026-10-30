"""Portable 3D/2D algorithm playback using Flet's native Canvas."""
import asyncio
import math
import time

import flet as ft
import flet.canvas as cv

from core.algorithms import algorithm_states, changed_stickers, normalized_state, parse_algorithm, simplified_algorithm
from core.algorithm_playback import playback_steps
from core.tracer import _orient, _solved
from ui.components.cube_projection import project_cube
from ui.theme_colors import apply_palette

TARGET_FPS = 60


@ft.control
class AlgorithmCube(ft.Column):
    def init(self):
        self.spacing = 6
        self.algorithm = None
        self.original_algorithm = None
        self.simultaneous_moves = False
        self._steps = ()
        self._initial = None
        self.states = [_solved()]
        self.index = 0
        self.scheme = None
        self.dark_mode = False
        self.targets = ()
        self.affected = None
        self.yaw, self.pitch = -.62, .45
        self.playing = False
        self._token = 0
        self._caption_key = None
        self._moving, self._fraction = None, 0
        self._viewport = (460, 300)
        self.mode_picker = ft.Dropdown(value='3D', width=94, height=36, dense=True,
            color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT),
            options=[ft.DropdownOption('3D'), ft.DropdownOption('2D')],
            on_select=lambda e: self._redraw())
        self.letter_switch = ft.Switch(label='Show letters', value=True,
            label_text_style=ft.TextStyle(size=11), on_change=lambda e: self._redraw())
        self.focus_switch = ft.Switch(label='Highlight pieces', value=True,
            label_text_style=ft.TextStyle(size=11), on_change=lambda e: self._redraw())
        self.display_switches = ft.Row([self.letter_switch, self.focus_switch], spacing=12, run_spacing=0, wrap=True)
        self.structure_switch = ft.Checkbox(label='Original commutator stages', value=False,
            visual_density=ft.VisualDensity.COMPACT, label_style=ft.TextStyle(size=11),
            tooltip='Study the original setup and A/B stages. Clean execution is the default.', on_change=self._change_structure)
        self.canvas = cv.Canvas(width=460, height=300)
        self.drag_area = ft.Container(width=460, height=300, bgcolor=ft.Colors.TRANSPARENT,
                                      tooltip='Drag the 3D cube to rotate the view.')
        self.canvas.content = ft.GestureDetector(content=self.drag_area, on_pan_update=self._drag, drag_interval=16)
        def icon_button(icon, tooltip, callback):
            return ft.IconButton(icon, tooltip=tooltip, on_click=callback,
                                 icon_size=19, width=32, height=32, padding=4)
        self.play_button = icon_button(ft.Icons.PLAY_ARROW, 'Play / pause', self._toggle)
        self.counter = ft.Text('0 / 0', size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.speed = ft.Dropdown(value='.6', width=88, height=34, dense=True, text_size=12,
            color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT),
            options=[ft.DropdownOption('.3', 'Fast'), ft.DropdownOption('.6', 'Normal'), ft.DropdownOption('1.2', 'Slow')])
        self.move_text = ft.Text('', size=13, font_family='monospace', color=ft.Colors.ON_SURFACE)
        self.stage_buttons = ft.Row(spacing=2, wrap=True)
        self.stage_text = ft.Text('', size=11, color=ft.Colors.ON_SURFACE_VARIANT)
        self.view_options = ft.ExpansionTile(title=ft.Text('View options & stages', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            dense=True, min_tile_height=34, tile_padding=0, controls_padding=ft.Padding.only(bottom=4),
            maintain_state=True, expanded_cross_axis_alignment=ft.CrossAxisAlignment.START,
            controls=[ft.Row([self.mode_picker,
                    icon_button(ft.Icons.RESTART_ALT, 'Reset camera', self._reset_camera)], spacing=4, wrap=True),
                      ft.Row([self.structure_switch], tight=True), self.stage_text, self.stage_buttons])
        self.controls = [
            self.canvas,
            self.display_switches,
            ft.Row([icon_button(ft.Icons.FIRST_PAGE, 'First move', lambda e: self.seek(0)),
                    icon_button(ft.Icons.CHEVRON_LEFT, 'Previous move', lambda e: self._step(-1)),
                    self.play_button,
                    icon_button(ft.Icons.CHEVRON_RIGHT, 'Next move', lambda e: self._step(1)),
                    icon_button(ft.Icons.LAST_PAGE, 'Last move', lambda e: self.seek(len(self.states) - 1)),
                    self.counter, self.speed], spacing=2, run_spacing=2, wrap=True),
            self.move_text, self.view_options,
        ]
        self._redraw(update=False)

    def _page(self):
        try:
            return self.page
        except RuntimeError:
            return None

    def _update(self):
        # During an interpolated turn, publish just the Canvas. The controls,
        # stage labels and move list only change at move boundaries.
        if self.playing and self._moving is not None:
            if self._page() is not None:
                self.canvas.update()
            return
        # Canvas paints already have concrete colors. Resolve only the text
        # rebuilt during playback, rather than traversing every polygon/frame.
        apply_palette(self.move_text, self.dark_mode)
        apply_palette(self.stage_text, self.dark_mode)
        apply_palette(self.counter, self.dark_mode)
        if self._page() is not None:
            self.update()

    def load(self, algorithm, *, initial=None, scheme=None, targets=()):
        self.stop(update=False)
        self.original_algorithm = parse_algorithm(algorithm) if isinstance(algorithm, str) else algorithm
        self._initial = dict(initial) if initial is not None else None
        self.structure_switch.value = False
        self.scheme, self.targets = scheme, tuple(targets)
        self._set_playback_algorithm()

    def _set_playback_algorithm(self):
        self.stop(update=False)
        self.algorithm = self.original_algorithm if self.structure_switch.value else simplified_algorithm(self.original_algorithm)
        self.states = algorithm_states(self.algorithm, self._initial)
        self._steps = playback_steps(self.algorithm, self.simultaneous_moves)
        self._caption_key, self.index = None, 0
        self.affected = {frozenset(s) for s in changed_stickers(normalized_state(self.original_algorithm)) if len(s) > 1}
        self.stage_buttons.controls = [ft.TextButton(s.label, on_click=lambda e, stage=s: self.play_stage(stage))
                                      for s in self.algorithm.stages] if len(self.algorithm.stages) > 1 else []
        self._redraw(update=False)

    def _change_structure(self, e=None):
        if self.original_algorithm is not None:
            self._set_playback_algorithm()
            self._update()

    def set_simultaneous_moves(self, enabled):
        enabled = bool(enabled)
        if enabled != self.simultaneous_moves:
            self.stop(update=False)
            self.simultaneous_moves = enabled
            self._steps = playback_steps(self.algorithm, enabled) if self.algorithm is not None else ()
            self._caption_key = None
            self._redraw(update=False)

    def set_viewport(self, width, height=300):
        width, height = max(180, width), max(140, height)
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
        caption_key = (id(self.algorithm), self.index, self.simultaneous_moves)
        if caption_key != self._caption_key:
            self._caption_key = caption_key
            self._render_caption()
        if update:
            self._update()

    def _render_caption(self):
        self.counter.value = f'{self.index} / {len(self.states) - 1}'
        if self.algorithm:
            stage = next((s.label for s in self.algorithm.stages if s.start <= self.index < s.end), 'Finished')
            self.stage_text.value = stage
            self.move_text.spans = [ft.TextSpan(step.caption + ' ', style=ft.TextStyle(
                weight=ft.FontWeight.BOLD if step.start <= self.index < step.end else ft.FontWeight.NORMAL,
                decoration=ft.TextDecoration.UNDERLINE if step.start <= self.index < step.end else None,
                bgcolor=ft.Colors.PRIMARY_CONTAINER if step.start <= self.index < step.end else None,
                color=(ft.Colors.ON_PRIMARY_CONTAINER if step.start <= self.index < step.end else
                       next((ft.Colors.PRIMARY if s.label in ('A', 'Undo A') else
                             ft.Colors.TERTIARY if s.label in ('B', 'Undo B') else
                             ft.Colors.ON_SURFACE_VARIANT if 'setup' in s.label.lower() else ft.Colors.ON_SURFACE
                             for s in self.algorithm.stages if s.start <= step.start < s.end), ft.Colors.ON_SURFACE))))
                for step in self._steps]

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

    def _step(self, direction):
        if direction > 0:
            index = next((step.end for step in self._steps if step.end > self.index), self.index)
        else:
            index = next((step.start for step in reversed(self._steps) if step.start < self.index), self.index)
        self.seek(index)

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
        self._redraw(update=False)
        self.playing = True
        self.play_button.icon = ft.Icons.PAUSE
        self._update()
        self._page().run_task(self._play, self._token, end)

    def play_stage(self, stage):
        self.seek(stage.start)
        self.play_to(stage.end)

    async def _play(self, token, end):
        while self.index < min(end, len(self.states) - 1) and token == self._token:
            finish = min(end, next(step.end for step in self._steps if step.start <= self.index < step.end))
            moves = self.algorithm.moves[self.index:finish]
            self._moving = moves[0] if len(moves) == 1 else moves
            duration = float(self.speed.value)
            frames = max(2, math.ceil(duration * TARGET_FPS)) if self.mode_picker.value == '3D' else 1
            started = time.perf_counter()
            frame = 1
            while frame <= frames:
                # Schedule against the move's start time so drawing/transport
                # work does not lengthen every frame and slow the whole alg.
                await asyncio.sleep(max(0, started + duration * frame / frames - time.perf_counter()))
                if token != self._token:
                    return
                progress = min(1, max(frame / frames, (time.perf_counter() - started) / duration))
                self._fraction = progress * progress * (3 - 2 * progress)
                self._redraw()
                if progress >= 1:
                    break
                # Skip missed deadlines on busy devices instead of queueing
                # stale frames; seeking and pausing remain cancellable.
                frame = max(frame + 1, math.floor((time.perf_counter() - started) / duration * frames) + 1)
            if token != self._token:
                return
            self.index = finish
            self._moving, self._fraction = None, 0
            self._redraw()
        if token == self._token:
            self.stop()
