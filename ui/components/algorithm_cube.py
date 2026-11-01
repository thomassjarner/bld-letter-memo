"""Portable 3D/2D algorithm playback using Flet's native Canvas."""
import asyncio
import math
import time

import flet as ft
import flet.canvas as cv

from core.algorithms import Algorithm, Stage, algorithm_states, changed_stickers, normalized_state, parse_algorithm, simplified_algorithm
from core.algorithm_playback import playback_steps
from core.commutator_playback import align_notation, commutator_study
from core.tracer import _key, _orient, _solved
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
        self._preserve_stages = False
        self._stage_targets = {}
        self._stage_focus = {}
        self._boundary_stage = None
        self._boundary_component = None
        self._studies = {}
        self._notation_views = []
        self._components = []
        self._requested_component_mode = False
        self.pause_after_stage = False
        self._initial = None
        self.states = [_solved()]
        self.index = 0
        self.scheme = None
        self.dark_mode = False
        self.targets = ()
        self.buffer = 'UFR'
        self.edge_colors = True
        self.affected = None
        self.yaw, self.pitch = -.62, .45
        self.playing = False
        self._token = 0
        self._caption_key = None
        self._moving, self._fraction = None, 0
        self._drag_revision = 0
        self._drag_pending = False
        self._drag_dirty = False
        self._drag_position = None
        self._drag_active = False
        self._drag_last_paint = float('-inf')
        self._viewport = (460, 300)
        self.mode_picker = ft.Dropdown(value='3D', width=94, height=36, dense=True,
            color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT),
            options=[ft.DropdownOption('3D'), ft.DropdownOption('2D')],
            on_select=self._change_view_mode)
        self.letter_switch = ft.Switch(label='Show letters', value=True,
            label_text_style=ft.TextStyle(size=11), on_change=lambda e: self._redraw())
        self.focus_switch = ft.Switch(label='Highlight pieces', value=True,
            label_text_style=ft.TextStyle(size=11), on_change=lambda e: self._redraw())
        self.display_switches = ft.Row([self.letter_switch, self.focus_switch], spacing=12, run_spacing=0, wrap=True)
        self.structure_switch = ft.Checkbox(label='Original commutator stages', value=False,
            visual_density=ft.VisualDensity.COMPACT, label_style=ft.TextStyle(size=11),
            tooltip='Study the original setup and A/B stages. Clean execution is the default.', on_change=self._change_structure)
        self.canvas = cv.Canvas(width=460, height=300)
        self.drag_area = ft.Container(width=460, height=300, bgcolor=ft.Colors.TRANSPARENT)
        self.canvas.content = ft.GestureDetector(content=self.drag_area,
            on_pan_start=self._drag_start, on_pan_update=self._drag,
            on_pan_end=self._drag_end, on_pan_cancel=self._drag_end, drag_interval=16)
        def icon_button(icon, tooltip, callback):
            return ft.IconButton(icon, tooltip=tooltip, on_click=callback,
                                 icon_size=18, width=32, height=32, padding=4)
        self.play_button = icon_button(ft.Icons.PLAY_ARROW, 'Play / pause', self._toggle)
        self.counter = ft.Text('0 / 0', size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.speed = ft.Dropdown(value='.6', width=108, height=36, dense=True, text_size=12,
            tooltip='Playback speed',
            color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT),
            options=[ft.DropdownOption('.3', 'Fast'), ft.DropdownOption('.6', 'Normal'), ft.DropdownOption('1.2', 'Slow')])
        self.playback_mode = ft.Dropdown(value='full', width=145, height=36, dense=True, text_size=12,
            color=ft.Colors.ON_SURFACE, visible=False,
            options=[ft.DropdownOption('full', 'Full alg'), ft.DropdownOption('components', 'Components')],
            tooltip='Components pauses after each written commutator part. Switching mode restarts the current alg.',
            on_select=self._change_playback_mode)
        self.move_text = ft.Text('', size=13, font_family='monospace', color=ft.Colors.ON_SURFACE)
        self.notation_text = ft.Text('', size=13, font_family='monospace', selectable=True,
                                    color=ft.Colors.ON_SURFACE, visible=False)
        self.component_status = ft.Text('', size=11, color=ft.Colors.ON_SURFACE_VARIANT, visible=False)
        self.stage_buttons = ft.Row(spacing=2, wrap=True)
        self.stage_text = ft.Text('', size=11, color=ft.Colors.ON_SURFACE_VARIANT)
        self.current_stage = ft.Text('', size=12, weight=ft.FontWeight.W_600,
                                     color=ft.Colors.PRIMARY, visible=False, max_lines=2)
        self.continue_button = ft.FilledTonalButton('Continue to next alg',
            icon=ft.Icons.PLAY_ARROW, visible=False, on_click=self._toggle,
            style=ft.ButtonStyle(color=ft.Colors.ON_PRIMARY_CONTAINER, bgcolor=ft.Colors.PRIMARY_CONTAINER))
        self.stage_status = ft.Row([self.current_stage, self.continue_button],
                                   spacing=8, run_spacing=4, wrap=True, visible=False)
        self.view_options = ft.ExpansionTile(title=ft.Text('View options & stages', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            dense=True, min_tile_height=34, tile_padding=0, controls_padding=ft.Padding.only(bottom=4),
            maintain_state=True, expanded_cross_axis_alignment=ft.CrossAxisAlignment.START,
            controls=[ft.Row([self.mode_picker,
                    icon_button(ft.Icons.RESTART_ALT, 'Reset camera', self._reset_camera)], spacing=4, wrap=True),
                      ft.Text('Drag the 3D cube to rotate the view.', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                      ft.Row([self.structure_switch], tight=True), self.stage_text, self.stage_buttons])
        self.controls = [
            self.canvas,
            self.display_switches,
            self.stage_status,
            ft.Row([icon_button(ft.Icons.FIRST_PAGE, 'First move', lambda e: self.seek(0)),
                    icon_button(ft.Icons.CHEVRON_LEFT, 'Previous move', lambda e: self._step(-1)),
                    self.play_button,
                    icon_button(ft.Icons.CHEVRON_RIGHT, 'Next move', lambda e: self._step(1)),
                    icon_button(ft.Icons.LAST_PAGE, 'Last move', lambda e: self.seek(len(self.states) - 1)),
                    self.counter, self.speed, self.playback_mode], spacing=2, run_spacing=2, wrap=True),
            self.move_text, self.notation_text, self.component_status, self.view_options,
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
        apply_palette(self.current_stage, self.dark_mode)
        apply_palette(self.notation_text, self.dark_mode)
        apply_palette(self.component_status, self.dark_mode)
        apply_palette(self.continue_button, self.dark_mode)
        if self._page() is not None:
            self.update()

    def load(self, algorithm, *, initial=None, scheme=None, targets=(), preserve_stages=False,
             stage_targets=None, stage_notations=None, buffer='UFR'):
        self.stop(update=False)
        self.original_algorithm = parse_algorithm(algorithm) if isinstance(algorithm, str) else algorithm
        self._initial = dict(initial) if initial is not None else None
        self.structure_switch.value = False
        self._preserve_stages = preserve_stages
        self._stage_targets = stage_targets or {}
        self.buffer = buffer
        self.structure_switch.visible = not preserve_stages
        self.scheme, self.targets = scheme, tuple(targets)
        parents = self.original_algorithm.stages if preserve_stages else (Stage('Algorithm', 0, len(self.original_algorithm.moves)),)
        self._studies = {}
        for parent in parents:
            moves = self.original_algorithm.moves[parent.start:parent.end]
            source = ((stage_notations or {}).get(parent.label) if stage_notations is not None else ' '.join(moves)) if preserve_stages else self.original_algorithm.source
            study = commutator_study(source) if source else None
            self._studies[parent.label] = study if align_notation(study, moves) is not None else None
        available = any(self._studies.values()) and sum(
            len(self._studies[p.label].moves) if self._studies.get(p.label) else p.end - p.start for p in parents) <= 4800
        self.playback_mode.disabled = not available
        self.playback_mode.visible = bool(available)
        self.playback_mode.value = 'components' if available and self._requested_component_mode else 'full'
        self._set_playback_algorithm()

    @property
    def component_mode(self): return self.playback_mode.value == 'components'

    def _rebuild_steps(self):
        grouping = self.algorithm
        if grouping is not None and self.component_mode:
            grouping = Algorithm(grouping.source, grouping.moves,
                                 grouping.stages + tuple(c[0] for c in self._components))
        self._steps = playback_steps(grouping, self.simultaneous_moves) if grouping is not None else ()

    def _set_playback_algorithm(self):
        self.stop(update=False)
        base = self.original_algorithm if self.structure_switch.value or self._preserve_stages else simplified_algorithm(self.original_algorithm)
        parents = base.stages if self._preserve_stages else (Stage('Algorithm', 0, len(base.moves)),)
        self._notation_views, self._components = [], []
        moves, stages = [], []
        for parent in parents:
            study = self._studies.get(parent.label)
            local = study.moves if self.component_mode and study else base.moves[parent.start:parent.end]
            start = len(moves) if self.component_mode else parent.start
            if self.component_mode:
                moves.extend(local)
                stages.append(Stage(parent.label, start, len(moves)))
            view_index = len(self._notation_views)
            self._notation_views.append(dict(label=parent.label, start=start, end=start + len(local),
                                            study=study, tracking=align_notation(study, local)))
            if self.component_mode:
                components = study.components if study else (Stage('Algorithm', 0, len(local)),)
                self._components.extend((Stage(c.label, start + c.start, start + c.end), view_index, i)
                                        for i, c in enumerate(components) if c.end > c.start)
        if self.component_mode:
            self.algorithm = Algorithm(self.original_algorithm.source, tuple(moves),
                tuple(stages) if self._preserve_stages else tuple(c[0] for c in self._components))
        else: self.algorithm = base
        self.structure_switch.visible = not self._preserve_stages and not self.component_mode
        self.states = algorithm_states(self.algorithm, self._initial)
        self._rebuild_steps()
        self._caption_key, self.index = None, 0
        self._boundary_stage = None
        self._boundary_component = None
        self.affected = (set() if self._preserve_stages else
                         {frozenset(s) for s in changed_stickers(normalized_state(self.original_algorithm)) if len(s) > 1})
        self._stage_focus = {}
        if self._preserve_stages:
            for stage in self.algorithm.stages:
                before, after = self.states[stage.start], self.states[stage.end]
                # Highlight the occupants actually moved by this alg. Home
                # identities at the buffer/targets can differ after every pair.
                affected = {frozenset(home) for position, home in before.items()
                            if len(home) > 1 and home != after[position]}
                colors = {}
                for sticker, color in zip((self.buffer, *self._stage_targets.get(stage.label, ())),
                                          ('#80CFC1', '#6DD8C3', '#FFD08A')):
                    piece = frozenset(before[_key(sticker)])
                    if piece in affected: colors[piece] = color
                highlights = {home: colors.get(frozenset(home), '#6DD8C3')
                              for home in before.values() if frozenset(home) in affected}
                self._stage_focus[stage.label] = affected, highlights
        self.stage_buttons.controls = [ft.TextButton(s.label, on_click=lambda e, stage=s: self.play_stage(stage))
                                      for s in self.algorithm.stages] if len(self.algorithm.stages) > 1 else []
        self._redraw(update=False)

    def _change_playback_mode(self, e=None):
        self._requested_component_mode = self.component_mode
        if self.original_algorithm is None: return
        parent = self._active_stage() if self._preserve_stages else None
        label = parent.label if parent else None
        self._set_playback_algorithm()
        if label:
            self.index = next((s.start for s in self.algorithm.stages if s.label == label), 0)
        self._redraw()

    def _change_structure(self, e=None):
        if self.original_algorithm is not None:
            self._set_playback_algorithm()
            self._update()

    def set_simultaneous_moves(self, enabled):
        enabled = bool(enabled)
        if enabled != self.simultaneous_moves:
            self.stop(update=False)
            self.simultaneous_moves = enabled
            self._rebuild_steps()
            self._caption_key = None
            self._redraw(update=False)

    def set_viewport(self, width, height=300):
        width, height = max(180, width), max(140, height)
        self._viewport = (width, height)
        self.width = self.canvas.width = self.drag_area.width = width
        self.canvas.height = self.drag_area.height = height
        self._redraw(update=False)

    def _active_stage(self):
        if self._boundary_stage is not None and self.index == self._boundary_stage.end:
            return self._boundary_stage
        if self.algorithm is None: return None
        return next((s for s in self.algorithm.stages if s.start <= self.index < s.end),
                    self.algorithm.stages[-1] if self.algorithm.stages else None)

    def _redraw(self, update=True):
        highlights = None
        if self._preserve_stages and self.algorithm.stages:
            stage = self._active_stage()
            self.targets = self._stage_targets.get(stage.label, ())
            self.affected, highlights = self._stage_focus[stage.label]
        tiles = project_cube(self.states[self.index], *self._viewport, scheme=self.scheme,
            mode=self.mode_picker.value, yaw=self.yaw, pitch=self.pitch,
            letters=self.letter_switch.value, focus=self.focus_switch.value,
            targets=self.targets, affected=self.affected, moving=self._moving, fraction=self._fraction,
            edge_colors=self.edge_colors, buffer=self.buffer, highlight_stickers=highlights)
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
        caption_key = (id(self.algorithm), self.index, self.simultaneous_moves, self._boundary_stage, self._boundary_component)
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
            self.current_stage.visible = self._preserve_stages and bool(self.algorithm.stages)
            self.current_stage.value = ('Completed · ' + self._boundary_stage.label if self._boundary_stage else
                'Current algorithm · ' + stage if stage != 'Finished' else 'Sequence complete')
            self.continue_button.visible = ((self._boundary_stage is not None or self._boundary_component is not None)
                                            and self.index < len(self.states) - 1)
            self.stage_status.visible = self.current_stage.visible or self.continue_button.visible
            following = next((c[0] for c in self._components if c[0].start == self.index), None)
            self.continue_button.content = ('Continue to next alg' if self._boundary_stage is not None else
                'Continue · ' + following.label if following is not None else 'Continue')
            active_stage = self._active_stage()
            highlight = max(0, self.index - 1) if self._boundary_stage or self._boundary_component or self.index == len(self.states) - 1 else self.index
            self.move_text.spans = [ft.TextSpan(step.caption + ' ', style=ft.TextStyle(
                weight=ft.FontWeight.BOLD if step.start <= highlight < step.end else ft.FontWeight.NORMAL,
                decoration=ft.TextDecoration.UNDERLINE if step.start <= highlight < step.end else None,
                bgcolor=ft.Colors.PRIMARY_CONTAINER if step.start <= highlight < step.end else None,
                color=(ft.Colors.ON_PRIMARY_CONTAINER if step.start <= highlight < step.end else
                       next((ft.Colors.PRIMARY if s.label in ('A', 'Undo A') else
                             ft.Colors.TERTIARY if s.label in ('B', 'Undo B') else
                             ft.Colors.ON_SURFACE_VARIANT if 'setup' in s.label.lower() else ft.Colors.ON_SURFACE
                             for s in self.algorithm.stages if s.start <= step.start < s.end), ft.Colors.ON_SURFACE))))
                for step in self._steps if not self._preserve_stages or active_stage is not None
                and active_stage.start <= step.start < active_stage.end]
            self._render_notation(highlight)

    def _render_notation(self, highlight):
        parent = self._active_stage() if self._preserve_stages else None
        view = (next((v for v in self._notation_views if v['label'] == parent.label), None) if parent else
                self._notation_views[0] if self._notation_views else None)
        study = view['study'] if view else None
        tracking = view['tracking'] if view else None
        self.component_status.color = ft.Colors.ON_SURFACE_VARIANT
        self.notation_text.visible = study is not None
        self.component_status.visible = study is not None or self.component_mode and view is not None
        self.notation_text.spans = []
        if study is None or tracking is None:
            self.component_status.value = 'Algorithm · moves only' if self.component_mode else ''
            return
        if not tracking:
            self.notation_text.spans = [ft.TextSpan(t.text, style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT))
                                        for t in study.tokens]
            self.component_status.value = 'Identity · no moves'
            return
        local = min(max(0, highlight - view['start']), len(tracking) - 1)
        beat = next((s for s in self._steps if s.start <= highlight < s.end), None)
        finish = min(len(tracking), (beat.end - view['start']) if beat else local + 1)
        current = tracking[local:max(local + 1, finish)]
        refs = frozenset().union(*(m.references for m in current))
        owners = frozenset().union(*(m.components for m in current))
        active_refs = frozenset().union(*(m.references for i in owners
            for m in study.tracked[study.components[i].start:study.components[i].end]))
        labels = ' + '.join(study.components[i].label for i in sorted(owners)) or 'Execution move'
        def part_color(label):
            role = label.removeprefix('Undo ').split(' · ')[0]
            return ft.Colors.PRIMARY if role == 'A' else ft.Colors.TERTIARY if role == 'B' else ft.Colors.ON_SURFACE_VARIANT
        colors = {ref: part_color(c.label) for c in study.components
                  for m in study.tracked[c.start:c.end] for ref in m.references}
        if len(owners) == 1: self.component_status.color = part_color(study.components[next(iter(owners))].label)
        completed = self._boundary_component is not None or self._boundary_stage is not None or self.index == len(self.states) - 1
        self.component_status.value = labels + (' complete' if completed else '')
        if self.component_mode and len(owners) == 1 and not completed:
            component = study.components[next(iter(owners))]
            self.component_status.value += f' · {local - component.start + 1}/{component.end - component.start}'
        self.notation_text.spans = [ft.TextSpan(token.text, style=ft.TextStyle(
            weight=ft.FontWeight.BOLD if token.reference in refs else ft.FontWeight.NORMAL,
            decoration=ft.TextDecoration.UNDERLINE if token.reference in refs else None,
            bgcolor=ft.Colors.PRIMARY_CONTAINER if token.reference in refs else None,
            color=ft.Colors.ON_PRIMARY_CONTAINER if token.reference in refs else
                  ft.Colors.ON_SURFACE if token.reference in active_refs and colors.get(token.reference) == ft.Colors.ON_SURFACE_VARIANT else
                  colors.get(token.reference, ft.Colors.ON_SURFACE_VARIANT)))
            for token in study.tokens]

    def _drag_start(self, e):
        self._cancel_drag()
        if self.mode_picker.value == '3D':
            self._drag_active = True
            self._drag_position = getattr(e, 'local_position', None)

    def _drag(self, e):
        if not self._drag_active or self.mode_picker.value != '3D':
            return
        position = getattr(e, 'local_position', None)
        if position is not None and self._drag_position is not None:
            dx, dy = position.x - self._drag_position.x, position.y - self._drag_position.y
        else:
            delta = getattr(e, 'local_delta', None)
            dx, dy = (delta.x, delta.y) if delta is not None else (0, 0)
        self._drag_position = position
        if dx or dy:
            self.yaw += dx * .01
            self.pitch = min(1.2, max(-1.2, self.pitch + dy * .01))
            self._drag_dirty = True
            self._queue_drag_frame()

    def _drag_end(self, e):
        # End events carry the final position even if the last throttled update
        # was omitted. Do not replay a stream of old pointer deltas after release.
        if not self._drag_active:
            return
        if self._drag_position is not None:
            self._drag(e)
        self._drag_active = False
        self._drag_position = None
        if self._drag_dirty:
            self._queue_drag_frame()

    def _queue_drag_frame(self):
        if self._drag_pending or self.playing:
            return  # Playback already paints the latest camera every frame.
        page = self._page()
        if page is None:
            self._drag_dirty = False
            self._redraw(update=False)
            return
        self._drag_pending = True
        try:
            page.run_task(self._draw_drag_frames, self._drag_revision)
        except RuntimeError:
            self._drag_pending = False  # The viewer may have just detached.

    async def _draw_drag_frames(self, revision):
        deadline = self._drag_last_paint + 1 / TARGET_FPS
        try:
            while revision == self._drag_revision and self._drag_dirty:
                await asyncio.sleep(max(0, deadline - time.perf_counter()))
                if revision != self._drag_revision or not self._drag_dirty:
                    return
                page = self._page()
                if page is None or self.mode_picker.value != '3D':
                    return
                started = time.perf_counter()
                self._drag_last_paint = started
                self._drag_dirty = False
                self._redraw(update=False)
                if revision != self._drag_revision or self._page() is None:
                    return
                self.canvas.update()
                deadline = started + 1 / TARGET_FPS
        finally:
            if revision == self._drag_revision:
                self._drag_pending = False
                # A native handler can deliver one more event as this task exits.
                if self._drag_dirty and self._page() is not None and self.mode_picker.value == '3D':
                    self._queue_drag_frame()

    def _cancel_drag(self):
        self._drag_revision += 1
        self._drag_pending = self._drag_dirty = False
        self._drag_position = None
        self._drag_active = False
        self._drag_last_paint = float('-inf')

    def _change_view_mode(self, e=None):
        self._cancel_drag()
        self._redraw()

    def _reset_camera(self, e=None):
        self._cancel_drag()
        self.yaw, self.pitch = -.62, .45
        self._redraw()

    def seek(self, index):
        self.stop(update=False)
        self._boundary_stage = None
        self._boundary_component = None
        self.index = max(0, min(index, len(self.states) - 1))
        self._redraw()

    def _step(self, direction):
        if direction > 0:
            index = next((step.end for step in self._steps if step.end > self.index), self.index)
        else:
            index = next((step.start for step in reversed(self._steps) if step.start < self.index), self.index)
        self.seek(index)

    def stop(self, update=True, *, keep_drag=False):
        if not keep_drag:
            self._cancel_drag()
        self._token += 1
        self.playing = False
        self._moving, self._fraction = None, 0
        self.play_button.icon = ft.Icons.PLAY_ARROW
        if update:
            self._redraw()

    def will_unmount(self):
        self.stop(update=False)
        super().will_unmount()

    def _toggle(self, e=None):
        if self.playing:
            self.stop()
            return
        if self.index == len(self.states) - 1:
            self.index = 0
        self.play_to(len(self.states) - 1)

    def play_to(self, end):
        self.stop(update=False)
        self._boundary_stage = None
        self._boundary_component = None
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
        if token != self._token: return
        self._boundary_stage = None
        self._boundary_component = None
        if self.component_mode:
            component = next((c[0] for c in self._components if c[0].start <= self.index < c[0].end), None)
            if component is not None: end = min(end, component.end)
        elif self._preserve_stages and self.pause_after_stage:
            stage = self._active_stage()
            if stage is not None: end = min(end, stage.end)
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
            if self._preserve_stages and finish == end:
                self._boundary_stage = next((s for s in self.algorithm.stages if s.end == finish), None)
            if self.component_mode and finish == end:
                self._boundary_component = next((c for c in self._components if c[0].end == finish), None)
            self._redraw()
        if token == self._token:
            self.stop(keep_drag=True)
