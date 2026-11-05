"""A bounded corner-solve workspace driven by verified scramble plans."""
import json

import flet as ft

from core.corner_walkthrough import build_corner_plan, target_letter, walkthrough_initial
from core.corner_cases import subset_for
from core.walkthrough_details import move_statistics, step_commutator
from data.models import LetterScheme
from ui.components.algorithm_cube import AlgorithmCube
from ui.design import panel
from ui.theme_colors import ThemeAwarePage, apply_palette


@ft.control
class CornerWalkthrough(ThemeAwarePage, ft.Column):
    @property
    def state(self): return self.data

    def init(self):
        self.spacing = 8
        self.plan = None
        self.scheme_name = self.state.data.active_scheme
        self._fingerprint = None
        self._viewport = (1200, 650)
        self.viewer = AlgorithmCube()
        self.viewer.pause_after_stage = True
        self.open_case_callback = None
        self.scramble = ft.TextField(label='Scramble', hint_text="Paste a real 3×3 scramble",
            multiline=True, min_lines=1, max_lines=3, text_size=13, color=ft.Colors.ON_SURFACE,
            label_style=ft.TextStyle(size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            hint_style=ft.TextStyle(size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            on_change=self._input_changed, on_submit=self.generate)
        self.generate_button = ft.FilledButton('Generate walkthrough', height=36, on_click=self.generate)
        self.play_all_button = ft.FilledButton('Play walkthrough', icon=ft.Icons.PLAY_ARROW,
            height=36,
            tooltip='Restart at the first algorithm. Pause between algs lets you continue at your own pace.',
            disabled=True, on_click=self._play_all)
        self.previous_button = ft.IconButton(ft.Icons.SKIP_PREVIOUS, tooltip='Previous algorithm',
            width=32, height=32, icon_size=20, padding=4, on_click=lambda e: self._jump(-1))
        self.next_button = ft.IconButton(ft.Icons.SKIP_NEXT, tooltip='Next algorithm',
            width=32, height=32, icon_size=20, padding=4, on_click=lambda e: self._jump(1))
        self.restart_button = ft.IconButton(ft.Icons.RESTART_ALT, tooltip='Restart walkthrough',
            width=32, height=32, icon_size=20, padding=4, on_click=lambda e: self.viewer.seek(0))
        self.pause_switch = ft.Switch(label='Pause between algs', value=True,
            label_text_style=ft.TextStyle(size=11), on_change=self._pause_changed,
            tooltip='Stop after each algorithm. Press Continue to next alg when you are ready.')
        self.viewer.display_switches.controls.append(self.pause_switch)
        self.edge_view = ft.Dropdown(label='Edges', value='scrambled', width=220, height=42, dense=True,
            text_size=12, color=ft.Colors.ON_SURFACE,
            label_style=ft.TextStyle(size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            options=[ft.DropdownOption('hidden', 'Hide edge colors'),
                     ft.DropdownOption('solved', 'Show solved edges'),
                     ft.DropdownOption('scrambled', 'Show scrambled edges')], on_select=self._edge_changed,
            tooltip='Solved-edge preview uses UF and your chosen parity helper. Edges move naturally during each alg.')
        self.memo_text = ft.Text('Uses your selected scheme, corner buffer and saved cycle-break preferences.',
                                 size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.status = ft.Text('', size=12, color=ft.Colors.ON_SURFACE)
        self.twist_text = ft.Text('', size=11, color=ft.Colors.ON_SURFACE_VARIANT, visible=False)
        self.detail_notes = ft.Column(spacing=6, tight=True)
        self.summary = ft.Column([self.memo_text, self.status, self.twist_text, self.detail_notes], spacing=6, tight=True)
        self.details = ft.ExpansionTile(title=ft.Text('Walkthrough details', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            expanded=False, maintain_state=True, dense=True, min_tile_height=34, tile_padding=0,
            controls_padding=ft.Padding.only(top=4, bottom=6),
            expanded_cross_axis_alignment=ft.CrossAxisAlignment.START, controls=[self.summary],
            on_change=self._details_changed)
        self.feedback = ft.Text('', size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.actions = ft.Row([self.play_all_button, self.previous_button, self.next_button,
                               self.restart_button, self.edge_view], spacing=6, run_spacing=6, wrap=True)
        self.input_area = ft.Container()
        self.step_controls = []
        self._clear('Paste a scramble to generate a walkthrough.', update=False)
        self.set_viewport(*self._viewport)

    def _page(self):
        try: return self.page
        except RuntimeError: return None

    def _update(self):
        apply_palette(self, self.state.data.dark_mode, self.state.data.light_theme)
        if self._page() is not None: self.update()

    def _current_fingerprint(self):
        scheme = self.state.data.schemes.get(self.scheme_name)
        records = {key: (record.preferred_algorithm, [(a.id, a.name, a.alg) for a in record.algorithms])
                   for key, record in self.state.data.corner_case_library.items()
                   if record.preferred_algorithm or record.algorithms}
        return json.dumps([self.scheme_name, scheme.to_dict() if scheme else None, records],
                          sort_keys=True, ensure_ascii=False)

    def _clear(self, message, *, error=False, update=True):
        self.viewer.stop(update=False)
        self.plan = None
        self.viewer.visible = False
        self.memo_text.value = 'Uses your selected scheme, corner buffer and saved cycle-break preferences.'
        self.memo_text.tooltip = self.memo_text.value
        self.play_all_button.disabled = self.previous_button.disabled = self.next_button.disabled = self.restart_button.disabled = True
        self.status.value, self.status.color = message, ft.Colors.ERROR if error else ft.Colors.ON_SURFACE_VARIANT
        self.feedback.value, self.feedback.color = self.status.value, self.status.color
        self.twist_text.visible = False
        self.step_controls = [self.feedback]
        if hasattr(self, 'input_area'): self.set_viewport(*self._viewport)
        if update: self._update()

    def _input_changed(self, e=None):
        if self.plan and (self.scramble.value or '').strip() != self.plan.scramble:
            self._clear('Scramble changed. Generate a new walkthrough.')

    def generate(self, e=None):
        self.viewer.stop(update=False)
        source = (self.scramble.value or '').strip()
        scheme = self.state.data.schemes.get(self.scheme_name)
        try:
            if len(source) > 8000 or len(source.split()) > 600:
                raise ValueError('Use at most 600 scramble moves.')
            plan = build_corner_plan(source, scheme, self.state.data.corner_case_library)
        except ValueError as ex:
            self._clear(str(ex), error=True)
            return
        self.plan, self._fingerprint = plan, self._current_fingerprint()
        targets = [s for s, twist in zip(plan.trace.corner_targets, plan.trace.corner_orientation_target_flags) if not twist]
        letters = [target_letter(scheme, s) for s in targets]
        self.memo_text.value = 'Corner memo · ' + (' '.join(''.join(letters[i:i + 2]) for i in range(0, len(letters), 2)) or 'No permutation targets')
        self.memo_text.tooltip = self.memo_text.value
        moves, _, rotations = move_statistics(plan.algorithm.moves)
        total = f'{moves} moves' + (f' + {rotations} cube rotations' if rotations else '')
        self.status.value = f'{len(plan.steps)} algorithms · {total} · buffer {plan.buffer}'
        self.status.color = ft.Colors.ON_SURFACE
        self.twist_text.visible = bool(plan.remaining_twists)
        self.twist_text.value = 'Corner twists · ' + ', '.join(plan.remaining_twists)
        self.play_all_button.disabled = self.previous_button.disabled = self.next_button.disabled = self.restart_button.disabled = not bool(plan.algorithm.moves)
        self._build_step_controls()
        self._load_viewer()
        self.set_viewport(*self._viewport)
        self._update()

    def _build_step_controls(self):
        controls = []
        for warning in self.plan.warnings:
            controls.append(ft.Text(warning, size=11, color=ft.Colors.ERROR))
        for i, step in enumerate(self.plan.steps):
            pair = self.state.get_pair_display(step.letters) if '?' not in step.letters else f'{step.first} / {step.second}'
            title = f'{i + 1} · {pair}'
            part = step.parts[0]
            record = self.state.data.corner_case_library.get(part.case_id)
            personal = bool(record and any(a.id == part.algorithm_id for a in record.algorithms))
            moves, quarters, rotations = move_statistics(step.moves)
            stats = [f'{moves} moves', f'{quarters} quarter turns', subset_for(*part.case_id.split(':')) + ' subset']
            if rotations: stats.append(f'{rotations} cube rotations')
            stats.append(('Saved custom' if personal else 'Built-in') + ' · ' + (record.status.title() if record else 'New'))
            notation = step_commutator(step)
            provenance = ' + '.join(part.name for part in step.parts)
            setup = next((part.setup for part in step.parts if part.setup), ())
            if setup: provenance += ' · buffer setup ' + ' '.join(setup)
            controls.append(panel(ft.Column([
                ft.Row([ft.TextButton(title, tooltip='Open this case in the algorithm editor',
                            on_click=lambda e, selected=part: self._open_step_case(selected)),
                        ft.Container(expand=True),
                        ft.IconButton(ft.Icons.SKIP_NEXT, tooltip='Jump to this algorithm on the cube', icon_size=18,
                            width=32, height=32, padding=4, on_click=lambda e, index=i: self._select_step(index)),
                        ft.IconButton(ft.Icons.PLAY_ARROW, tooltip='Play this algorithm', icon_size=20,
                            width=32, height=32, padding=4, on_click=lambda e, index=i: self._select_step(index, play=True))], spacing=4),
                ft.Text(f'{self.plan.buffer} → {step.first} → {step.second}', size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Row([ft.Container(ft.Text(stat, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    padding=ft.Padding.symmetric(horizontal=6, vertical=3), border_radius=5,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST) for stat in stats], spacing=5, run_spacing=5, wrap=True),
                ft.Text('Commutator', size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(notation or 'No short commutator found for this execution.', size=12 if notation else 11,
                    selectable=True, font_family='monospace' if notation else None,
                    color=ft.Colors.PRIMARY if notation else ft.Colors.ON_SURFACE_VARIANT),
                ft.Text('Final alg', size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(' '.join(step.moves), size=12, selectable=True, font_family='monospace', color=ft.Colors.ON_SURFACE,
                    max_lines=4, overflow=ft.TextOverflow.ELLIPSIS, tooltip=' '.join(step.moves)),
                ft.Text(provenance, size=10, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=2, tooltip=provenance),
                ft.TextButton('Open case & edit alg', icon=ft.Icons.OPEN_IN_NEW,
                    on_click=lambda e, selected=part: self._open_step_case(selected)),
            ], spacing=5, tight=True), padding=10))
        if not self.plan.steps:
            controls.append(ft.Text('No paired corner algorithms for this scramble.',
                                    size=14, color=ft.Colors.PRIMARY))
        notes = []
        if self.plan.trace.corner_cycle_breaks:
            choices = ', '.join(info.chosen_sticker for info in self.plan.trace.corner_cycle_breaks)
            notes.append(ft.Text('Cycle breaks · ' + choices, size=11, color=ft.Colors.ON_SURFACE_VARIANT))
        notes.append(ft.Text('Uses your saved preferred algorithms. Built-in recommendations may not be optimal.',
                                size=11, color=ft.Colors.ON_SURFACE_VARIANT))
        self.detail_notes.controls = notes
        controls.append(self.details)
        self.step_controls = controls

    def _load_viewer(self, index=0, boundary=None, component_boundary=None):
        plan = self.plan
        initial = walkthrough_initial(plan, self.edge_view.value)
        self.viewer.edge_colors = self.edge_view.value != 'hidden'
        scheme = LetterScheme.from_dict(plan.scheme_name, plan.scheme_snapshot)
        targets = {stage.label: (step.first, step.second)
                   for stage, step in zip(plan.algorithm.stages, plan.steps)}
        notations = {stage.label: step_commutator(step)
                     for stage, step in zip(plan.algorithm.stages, plan.steps)}
        self.viewer.visible = True
        self.viewer.load(plan.algorithm, initial=initial, scheme=scheme, preserve_stages=True,
                         stage_targets=targets, stage_notations=notations, buffer=plan.buffer)
        self.viewer.index = min(index, len(self.viewer.algorithm.moves))
        self.viewer.dark_mode = self.state.data.dark_mode
        self.viewer.set_simultaneous_moves(self.state.data.simultaneous_moves)
        self.viewer._boundary_stage = boundary
        self.viewer._boundary_component = component_boundary if self.viewer.component_mode else None
        self.viewer.play_button.disabled = not bool(self.viewer.algorithm.moves)
        self.viewer._redraw(update=False)

    def _details_changed(self, e):
        self.details.expanded = e.data is True or str(e.data).lower() == 'true'

    def _open_step_case(self, part):
        self.viewer.stop(update=False)
        if self.open_case_callback: self.open_case_callback(part)

    def _pause_changed(self, e=None):
        self.viewer.stop(update=False)
        self.viewer.pause_after_stage = bool(self.pause_switch.value)
        self._update()

    def _edge_changed(self, e=None):
        if self.plan: self._load_viewer(self.viewer.index, self.viewer._boundary_stage, self.viewer._boundary_component)
        self.set_viewport(*self._viewport)
        self._update()

    def _select_step(self, index, *, play=False):
        if not self.plan: return
        step = self.viewer.algorithm.stages[index]
        self.viewer.seek(step.start)
        if play: self.viewer.play_to(step.end)

    def _play_all(self, e=None):
        if self.plan and self.plan.algorithm.moves:
            self.viewer.seek(0)
            self.viewer.play_to(len(self.viewer.algorithm.moves))

    def _jump(self, direction):
        if not self.plan: return
        if direction > 0:
            index = next((s.start for s in self.viewer.algorithm.stages if s.start > self.viewer.index), len(self.viewer.algorithm.moves))
        else:
            index = next((s.start for s in reversed(self.viewer.algorithm.stages) if s.start < self.viewer.index), 0)
        self.viewer.seek(index)

    def refresh(self, scheme_name, *, update=True):
        self.scheme_name = scheme_name
        self.viewer.dark_mode = self.state.data.dark_mode
        self.viewer.set_simultaneous_moves(self.state.data.simultaneous_moves)
        if self.plan and self._fingerprint != self._current_fingerprint():
            self._clear('Scheme or case algorithms changed. Generate again to use the current choices.', update=False)
        elif self.plan:
            self.viewer._redraw(update=False)
            self._build_step_controls()
            self.set_viewport(*self._viewport)
        if update: self._update()

    def open_scramble(self, source, scheme_name):
        self.scheme_name = scheme_name
        self.scramble.value = source
        self.generate()

    def set_active(self, active):
        if not active: self.viewer.stop(update=False)

    def set_viewport(self, width, height):
        width, height = max(240, width), max(60, height)
        self._viewport = self.width, self.height = width, height
        wide = width >= 980 and height >= 360
        self.scramble.expand = wide
        self.input_area.content = (ft.Row([self.scramble, self.generate_button], spacing=10)
                                   if wide else ft.Column([self.scramble, self.generate_button], spacing=8, tight=True))
        self.input_area.height = 62 if wide else None
        self.edge_view.width = min(220, width - 24)
        if wide:
            available = height - self.input_area.height - 42 - self.spacing * 2
            left_width = round((width - 10) * .54)
            right_width = width - left_width - 10
            self.viewer.set_viewport(left_width - 24, min(360, max(140, round(available * .62))))
            cube_scroll = ft.ListView([self.viewer], spacing=4, height=available - 24, scroll=ft.ScrollMode.AUTO,
                                      build_controls_on_demand=False)
            steps_scroll = ft.ListView(self.step_controls, spacing=8, height=available - 24,
                                       scroll=ft.ScrollMode.AUTO, build_controls_on_demand=False)
            self.actions.height = 42
            self.controls = [self.input_area, self.actions, ft.Row([
                panel(cube_scroll, width=left_width, height=available, padding=12),
                panel(steps_scroll, width=right_width, height=available, padding=12),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START)]
        else:
            self.actions.height = None
            self.viewer.set_viewport(width - 24, min(320, max(160, height * .5)))
            self.controls = [ft.ListView([self.input_area, self.actions, self.viewer,
                ft.Column(self.step_controls, spacing=8, tight=True)], height=height,
                spacing=10, scroll=ft.ScrollMode.AUTO, build_controls_on_demand=False)]
