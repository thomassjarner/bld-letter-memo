"""Method Library overview, UFR cases, explorer and commutator lesson."""
import random

import flet as ft

from core.algorithms import inverse_state, normalized_state, parse_algorithm
from core.algorithm_analysis import analyze_algorithm
from core.corner_algorithms import QUALITY_NOTICE, builtin_algorithms, display_builtin_algorithms
from core.corner_cases import BASE_ALG, BUFFER, SUBSETS, TARGETS, case_letters, corner_cases, identify_case
from data.models import CornerCaseRecord
from ui.components.algorithm_cube import AlgorithmCube
from ui.components.algorithm_converter import AlgorithmConverter
from ui.design import activity_card, panel
from ui.theme_colors import ThemeAwarePage, apply_palette


def field(**kwargs):
    return ft.TextField(color=ft.Colors.ON_SURFACE,
        label_style=ft.TextStyle(size=11, color=ft.Colors.ON_SURFACE_VARIANT),
        hint_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT), **kwargs)


def dropdown(**kwargs):
    return ft.Dropdown(color=ft.Colors.ON_SURFACE, text_size=12,
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        label_style=ft.TextStyle(size=11, color=ft.Colors.ON_SURFACE_VARIANT), **kwargs)


@ft.control
class CaseLibraryPage(ThemeAwarePage, ft.Column):
    @property
    def state(self):
        return self.data

    def init(self):
        self.expand = True
        self.spacing = 8
        self.mode = 'overview'
        self._cases = None
        self.selected_case = None
        self.selected_algorithm = ''
        self.label_scheme = self.state.data.active_scheme
        self._viewport = (1400, 760)
        self.limit = 50
        self.hidden = False
        self.active = False
        self._loaded_key = None
        self._editor_key = None
        self._identified = None
        self.browser_title = None
        self.mobile_browser = None
        self.notes_open = False
        self._navigation_token = 0
        self.detail_scrolls = []
        self.viewer = AlgorithmCube()
        self.search = field(hint_text='Search letters or stickers', height=36, text_size=12, dense=True,
                            on_change=lambda e: self._filter_changed())
        self.subset = dropdown(label='Subset · target layers', value='all', height=38, dense=True,
            options=[ft.DropdownOption('all', 'All cases · 378')] +
                    [ft.DropdownOption(s, f'{s} · {54 if s == "U/U" else 108} cases') for s in SUBSETS],
            on_select=lambda e: self._filter_changed())
        self.first_target = dropdown(label='First target sticker', value='all', height=38, dense=True,
            options=[ft.DropdownOption('all', 'Any first target')] + [ft.DropdownOption(s) for s in TARGETS],
            on_select=lambda e: self._filter_changed())
        self.second_target = dropdown(label='Second target (optional)', value='all', height=38, dense=True,
            options=[ft.DropdownOption('all', 'Any second target')] + [ft.DropdownOption(s) for s in TARGETS],
            on_select=lambda e: self._filter_changed())
        self.status_filter = dropdown(label='Filter by status', value='all', height=38, dense=True,
            options=[ft.DropdownOption('all', 'Any status')] +
                    [ft.DropdownOption(s, s.title()) for s in ('new', 'learning', 'learned')],
            on_select=lambda e: self._filter_changed())
        self.favorites = ft.Checkbox(label='Favorites only', value=False, visual_density=ft.VisualDensity.COMPACT,
            label_style=ft.TextStyle(size=12), on_change=lambda e: self._filter_changed())
        self.filter_more = ft.ExpansionTile(title=ft.Text('More filters', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            dense=True, min_tile_height=34, tile_padding=0, maintain_state=True,
            expanded_cross_axis_alignment=ft.CrossAxisAlignment.START,
            controls=[self.status_filter, ft.Row([self.favorites], tight=True)],
            on_change=self._filter_expanded)
        self.case_list = ft.ListView(height=320, spacing=2, scroll=ft.ScrollMode.ALWAYS)
        self.list_meta = ft.Text('', size=11, height=16, color=ft.Colors.ON_SURFACE_VARIANT)
        self.more_button = ft.TextButton('More cases', height=32, on_click=self._more)
        self.scheme_picker = dropdown(label='Letter labels', value=self.label_scheme, width=230,
                                      height=42, dense=True, on_select=self._choose_scheme)
        self.error = ft.Text('', color=ft.Colors.ERROR, size=12)
        self.notice = ft.Text('', color=ft.Colors.PRIMARY, size=12)
        self.case_converter = AlgorithmConverter()
        self.playground_converter = AlgorithmConverter()
        self.case_converter.on_result = self._case_input_changed
        self.playground_converter.on_result = self._playground_input_changed
        self.algorithm_field = self.case_converter.final_alg
        self.explorer_field = self.playground_converter.final_alg
        self.name_field = field(label='Algorithm name (optional)', value='My alg', height=38, dense=True)
        self.selected_playground = None
        self._loaded_playground_record = None
        self._playground_analysis_source = None
        self._analysis = None
        self.playground_saved = dropdown(label='Saved playground algorithms', value='', height=38, dense=True,
            options=[ft.DropdownOption('', 'Unsaved playground')], on_select=self._choose_playground)
        self.playground_name = field(label='Name', value='', height=38, dense=True)
        self.playground_notes = field(label='Notes', value='', multiline=True, min_lines=2, max_lines=4)
        self.playground_save = ft.FilledButton('Save algorithm', disabled=True, on_click=self._save_playground)
        self.playground_copy = ft.TextButton('Save as new', disabled=True,
            on_click=lambda e: self._save_playground(e, as_new=True))
        self.playground_delete = ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip='Delete saved playground algorithm',
            disabled=True, on_click=self._delete_playground)
        self.open_case_button = ft.TextButton('Open matching UFR case', disabled=True, on_click=self._open_identified)
        self.effect_area = ft.Column(spacing=6, tight=True)
        self.explorer_effect = ft.Text('', size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.body = ft.Column()
        self.detail_controls = []
        self._make_header()
        self.refresh(update=False)

    @property
    def cases(self):
        # Opening Home or the overview need not generate the algorithm catalog.
        if self._cases is None:
            self._cases = corner_cases()
            self.selected_case = next(iter(self._cases))
        return self._cases

    def _make_header(self):
        self.title = ft.Text('Method Library', size=20, weight=ft.FontWeight.W_600,
                             max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.ON_SURFACE)
        self.header_top = ft.Container()
        self.section_buttons = {
            key: ft.TextButton(label, on_click=lambda e, m=key: self._set_mode(m))
            for key, label in (('overview', 'Overview'), ('library', '3-style corner cases'),
                               ('explorer', 'Playground'), ('lesson', 'Commutator Lesson'))
        }
        self.section_nav = ft.Row(list(self.section_buttons.values()), spacing=2, height=36,
                                  scroll=ft.ScrollMode.AUTO)
        self.header = ft.Column(spacing=4)
        self.controls = [self.header, self.body]

    def _render_overview(self):
        cards = [
            activity_card('3-style corner cases',
                'Find an algorithm for two target stickers, edit it and track your progress. '
                '378 cases with UFR as the buffer; subsets and filters are inside.',
                ft.Icons.GRID_VIEW, 'Open corner cases', lambda e: self._set_mode('library'), 'CASE LIBRARY'),
            activity_card('Algorithm Playground',
                'Paste moves or a commutator, see what happens to the cube and save your alg. '
                'No case or buffer required.',
                ft.Icons.VIEW_IN_AR_OUTLINED, 'Open Playground', lambda e: self._set_mode('explorer'), 'FREE EXPLORATION'),
        ]
        for card in cards:
            card.col = {'xs': 12, 'md': 6}
        records = list(self.state.data.corner_case_library.values())
        self.overview_controls = [
            ft.Column([
                ft.Text('Choose a workspace.', size=23, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                ft.Text('Study a corner case, or test an algorithm of your own. '
                        'Your selected letter scheme supplies the sticker labels.',
                        size=13, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=6),
            ft.ResponsiveRow(cards, spacing=12, run_spacing=12),
            ft.Row([
                ft.Text(f'{sum(r.status == "learned" for r in records)} / 378 learned', size=12, color=ft.Colors.PRIMARY),
                ft.Text(f'{sum(r.status == "learning" for r in records)} learning', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(f'{sum(r.favorite for r in records)} favorites', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(f'{sum(len(r.algorithms) for r in records)} saved algorithms', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=20, wrap=True),
            ft.Text(QUALITY_NOTICE, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
        ]
        self._layout()

    def _page(self):
        try: return self.page
        except RuntimeError: return None

    def _update(self):
        self.error.visible = bool(self.error.value)
        self.notice.visible = bool(self.notice.value)
        self.viewer.dark_mode = self.state.data.dark_mode
        apply_palette(self, self.state.data.dark_mode)
        if self._page() is not None:
            self.update()

    @property
    def scheme(self):
        return self.state.data.schemes.get(self.label_scheme)

    def record(self, key=None):
        return self.state.data.corner_case_library.get(key or self.selected_case, CornerCaseRecord())

    def _label(self, case):
        letters = case_letters(case, self.scheme)
        return self.state.get_pair_display(letters) if '?' not in letters else f'{case.first} / {case.second}'

    def filtered_cases(self):
        search = (self.search.value or '').strip().casefold()
        matches = []
        for case in self.cases.values():
            record = self.record(case.id)
            if self.subset.value != 'all' and case.subset != self.subset.value: continue
            if self.first_target.value != 'all' and case.first != self.first_target.value: continue
            if self.second_target.value != 'all' and case.second != self.second_target.value: continue
            if self.status_filter.value != 'all' and record.status != self.status_filter.value: continue
            if self.favorites.value and not record.favorite: continue
            text = f'{case.id} {case.first} {case.second} {self._label(case)} {case_letters(case, self.scheme)}'.casefold()
            if search and search not in text: continue
            matches.append(case)
        return matches

    def _filter_changed(self):
        self.limit = 50
        self._render_list()
        if self.browser_title is not None:
            self.browser_title.value = f'Browse cases · {len(self.filtered_cases())} matching'
        self._update()

    def _filter_expanded(self, e):
        self.filter_more.expanded = e.data is True or str(e.data).lower() == 'true'
        self._layout()
        self._update()

    def _more(self, e=None):
        self.limit += 50
        self._render_list()
        self._update()

    def _render_list(self):
        matches = self.filtered_cases()
        self.list_meta.value = f'{len(matches)} matching · {sum(self.record(c.id).status == "learned" for c in self.cases.values())} / 378 learned'
        rows = []
        for case in matches[:self.limit]:
            record = self.record(case.id)
            rows.append(ft.Container(ft.TextButton(content=ft.Row([
                ft.Column([
                    ft.Text(self._label(case), size=13, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                    ft.Text(f'{case.first} → {case.second} · {record.status}', size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=1, expand=True),
                ft.Icon(ft.Icons.STAR if record.favorite else ft.Icons.CHECK_CIRCLE if record.status == 'learned' else ft.Icons.CHEVRON_RIGHT,
                        size=16, color=ft.Colors.PRIMARY),
            ], spacing=4), style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=8, vertical=4)),
                on_click=lambda e, key=case.id: self.select_case(key)), height=40,
            bgcolor=ft.Colors.PRIMARY_CONTAINER if case.id == self.selected_case else ft.Colors.TRANSPARENT,
            border_radius=6))
        self.case_list.controls = rows or [ft.Text('No cases match these filters.', color=ft.Colors.ON_SURFACE_VARIANT)]
        self.more_button.visible = len(matches) > self.limit

    def select_case(self, key, *, edit=False):
        self.viewer.stop(update=False)
        self.selected_case = key
        self.selected_algorithm = self.record().preferred_algorithm
        self.hidden = False
        self.notes_open = False
        self.case_converter.cancel_pending()
        self._navigation_token += 1
        if self.mobile_browser is not None:
            self.mobile_browser.expanded = False
        self.error.value = self.notice.value = ''
        self._render_library()
        self.viewer.index = 0
        self.viewer._redraw(update=False)
        self._update()
        if self._page() is not None:
            self._page().run_task(self._reveal_case_editor if edit else self._reset_case_scroll, self._navigation_token)

    async def _reset_case_scroll(self, token):
        for scroll in self.detail_scrolls:
            if token != self._navigation_token:
                return
            try:
                if scroll.page is not None:
                    await scroll.scroll_to(offset=0, duration=0)
            except RuntimeError:
                return  # navigation can detach the old pane before it scrolls

    async def _reveal_case_editor(self, token):
        if token != self._navigation_token or not self.detail_scrolls:
            return
        try:
            scroll = self.detail_scrolls[-1]
            if scroll.page is not None:
                await scroll.scroll_to(scroll_key=self.algorithm_editor.key, duration=0)
                if token == self._navigation_token:
                    await self.algorithm_field.focus()
        except RuntimeError:
            return

    def _remember_tile(self, name, e):
        setattr(self, name, e.data is True or str(e.data).lower() == 'true')

    def _variant(self):
        case, record = self.cases[self.selected_case], self.record()
        algorithm = next((a for a in record.algorithms if a.id == self.selected_algorithm), None)
        if algorithm is None:
            builtins = builtin_algorithms(case.id)
            algorithm = next((a for a in builtins if a.id == self.selected_algorithm), builtins[0])
        return algorithm.name, algorithm.alg

    def _load_viewer(self, source, initial, targets=(), identity=None):
        key = (source, identity)
        if key != self._loaded_key:
            self.viewer.load(parse_algorithm(source), initial=initial, scheme=self.scheme, targets=targets)
            self._loaded_key = key
        self.viewer.scheme = self.scheme
        self.viewer.dark_mode = self.state.data.dark_mode
        self.viewer.play_button.disabled = False
        self.viewer._redraw(update=False)

    def _render_library(self):
        self._render_list()
        case, record = self.cases[self.selected_case], self.record()
        builtins = builtin_algorithms(case.id)
        personal = next((a for a in record.algorithms if a.id == self.selected_algorithm), None)
        if personal is None and not any(a.id == self.selected_algorithm for a in builtins):
            self.selected_algorithm = ''
        name, source = self._variant()
        editor_key = (case.id, self.selected_algorithm, source)
        changed_variant = editor_key != self._editor_key
        if not changed_variant:
            self.case_converter.sync(notify=False)
        preview_source = self.case_converter.source if not changed_variant and self.case_converter.algorithm is not None else source
        parsed = parse_algorithm(case.starter)
        initial = inverse_state(normalized_state(parsed))
        try:
            candidate = parse_algorithm(preview_source)
            if identify_case(candidate) != case.id:
                raise ValueError('Saved algorithm solves another case. Edit it before using it.')
            if changed_variant or self._loaded_key != (preview_source, case.id):
                self._load_viewer(preview_source, initial, (case.first, case.second), case.id)
        except ValueError as ex:
            self.error.value = str(ex) + ' Showing the verified starter.'
            self._load_viewer(case.starter, initial, (case.first, case.second), case.id)
        if changed_variant:
            self.case_converter.load(source)
            self.name_field.value = name if personal else 'My alg'
            self._editor_key = editor_key
        self.viewer.scheme = self.scheme
        self.viewer.dark_mode = self.state.data.dark_mode
        self.viewer._redraw(update=False)
        self.case_converter.visible = not self.hidden
        self.algorithm_field.visible = self.case_converter.commutator.visible = not self.hidden
        self.viewer.move_text.visible = not self.hidden
        recommended = builtins[0]
        recommendation = {'supplied': 'Supplied algorithm', 'one_move': 'One-move setup', 'generated': 'Generated fallback'}[recommended.origin]
        options = [ft.DropdownOption('', f'Recommended · {recommendation}' + (' · preferred' if not record.preferred_algorithm else ''))]
        options += [ft.DropdownOption(a.id, a.name + (' · preferred' if a.id == record.preferred_algorithm else ''))
                    for a in display_builtin_algorithms(case.id, (self.selected_algorithm, record.preferred_algorithm))]
        options += [ft.DropdownOption(a.id, a.name + (' · preferred' if a.id == record.preferred_algorithm else '')) for a in record.algorithms]
        valid_ids = {o.key for o in options}
        self.selected_algorithm = self.selected_algorithm if self.selected_algorithm in valid_ids else ''
        self.variant_picker = dropdown(label='Algorithm alternative', value=self.selected_algorithm,
                                      options=options, on_select=self._choose_variant, height=38, dense=True)
        self.notes_field = field(label='Case notes · saves on leaving this field', value=record.notes,
            multiline=True, min_lines=2, max_lines=4,
            on_blur=lambda e, key=case.id: self._save_notes(key, e.control.value or ''))
        self.status_choices = {
            status: ft.Checkbox(label=status.title(), value=record.status == status,
                visual_density=ft.VisualDensity.COMPACT, label_style=ft.TextStyle(size=12),
                on_change=lambda e, key=case.id, s=status: self._choose_learning_status(key, s, e))
            for status in ('new', 'learning', 'learned')
        }
        self.learning_status = ft.Column([
            ft.Text('Learning status', size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Row(list(self.status_choices.values()), spacing=8, run_spacing=0, wrap=True),
        ], spacing=0, tight=True)
        missing = '?' in case_letters(case, self.scheme)
        selected_builtin = next((a for a in builtins if a.id == self.selected_algorithm), recommended)
        provenance = 'Your saved algorithm' if personal else (
            f'One-move setup {selected_builtin.setup} of {selected_builtin.position}' if selected_builtin.origin == 'one_move' else
            f'Supplied algorithm · {selected_builtin.position}' if selected_builtin.origin == 'supplied' else 'Generated fallback')
        def small_icon(icon, tooltip, callback, disabled=False):
            return ft.IconButton(icon, tooltip=tooltip, on_click=callback,
                icon_size=19, width=32, height=32, padding=4, disabled=disabled)
        self.case_toolbar = ft.Row([
            ft.Column([
                ft.Text(self._label(case), size=20, weight=ft.FontWeight.W_600, max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.ON_SURFACE),
                ft.Text(f'UFR · {case.first} → {case.second} · {case.subset}', size=11,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=0, expand=True,
                tooltip='Unassigned target letters use sticker IDs.' if missing else None),
            small_icon(ft.Icons.STAR if record.favorite else ft.Icons.STAR_BORDER, 'Favorite case',
                lambda e, key=case.id: self._set_record(key, favorite=not self.record(key).favorite)),
            small_icon(ft.Icons.SHUFFLE, 'Random matching case', self._random_case),
            small_icon(ft.Icons.VISIBILITY if self.hidden else ft.Icons.VISIBILITY_OFF,
                       'Reveal algorithm' if self.hidden else 'Hide algorithm', self._hide),
        ], spacing=2, height=42)
        self.algorithm_editor = ft.Column(
            key=ft.ScrollKey('case-algorithm-editor'),
            visible=not self.hidden, spacing=8, tight=True,
            controls=[
                ft.Row([ft.Icon(ft.Icons.EDIT_OUTLINED, size=17, color=ft.Colors.PRIMARY),
                        ft.Text('Edit / replace alg', size=13, color=ft.Colors.ON_SURFACE)], spacing=6),
                self.case_converter, self.name_field,
                ft.Row([ft.FilledButton('Save changes & use' if personal else 'Save & use my alg',
                                       on_click=lambda e, update=bool(personal): self._save_algorithm(update)),
                        ft.TextButton('Preview alg', on_click=lambda e: self._preview_editor())], wrap=True, spacing=4),
                ft.Row([ft.TextButton('Open in Playground', on_click=self._open_playground_draft),
                        ft.TextButton('Save as another alternative', on_click=lambda e: self._save_algorithm(False)),
                        small_icon(ft.Icons.DELETE_OUTLINE, 'Delete selected personal alternative', self._delete_algorithm,
                                   disabled=not bool(personal))],
                       wrap=True, spacing=4),
            ])
        self.notes_tile = ft.ExpansionTile(title=ft.Text('Case notes', size=13, color=ft.Colors.ON_SURFACE),
            expanded=self.notes_open, maintain_state=True, dense=True, min_tile_height=38, tile_padding=0,
            controls_padding=ft.Padding.only(top=6, bottom=8),
            expanded_cross_axis_alignment=ft.CrossAxisAlignment.START,
            on_change=lambda e: self._remember_tile('notes_open', e), controls=[self.notes_field])
        self.case_details = panel(ft.Column([
            self.learning_status, self.notes_tile,
        ], spacing=8, tight=True), padding=12)
        self.tool_controls = [
            self.variant_picker,
            ft.Text(provenance, size=11, color=ft.Colors.PRIMARY, max_lines=2, tooltip=provenance),
            ft.TextButton('Use selected alg', on_click=lambda e: self._set_record(case.id, preferred=self.selected_algorithm)),
            self.algorithm_editor,
            ft.Text(QUALITY_NOTICE, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            self.error, self.notice,
        ]
        self.detail_controls = [self.case_toolbar, self.viewer,
            ft.Column(self.tool_controls, spacing=8, tight=True), self.case_details]
        self.error.visible, self.notice.visible = bool(self.error.value), bool(self.notice.value)
        self._layout()

    def _choose_variant(self, e):
        self.case_converter.cancel_pending()
        self.selected_algorithm = e.control.value or ''
        self.error.value = self.notice.value = ''
        self._render_library()
        self._update()

    def _case_input_changed(self, converter):
        if self.mode == 'library': self._preview_editor(sync=False)

    def _preview_editor(self, *, sync=True):
        case = self.cases[self.selected_case]
        try:
            if sync: self.case_converter.sync(notify=False)
            algorithm = self.case_converter.algorithm
            if algorithm is None:
                raise ValueError(self.algorithm_field.error_text or self.case_converter.commutator.error_text or 'Enter an algorithm to preview it.')
            if identify_case(algorithm) != case.id:
                raise ValueError('This alg solves a different target order/case.')
            self._load_viewer(algorithm.source, inverse_state(normalized_state(parse_algorithm(case.starter))),
                              (case.first, case.second), case.id)
            self.error.value = ''
            self.notice.value = f'Verified · {len(self.viewer.algorithm.moves)} moves · edges restored.'
        except ValueError as ex:
            self.viewer.stop(update=False)
            self.error.value, self.notice.value = str(ex), ''
        self._update()

    def _save_algorithm(self, update):
        self.notice.value = ''
        try:
            self.case_converter.sync(notify=False)
            if self.case_converter.algorithm is None:
                raise ValueError(self.algorithm_field.error_text or self.case_converter.commutator.error_text or 'Enter a valid algorithm before saving.')
            self.selected_algorithm = self.state.save_case_algorithm(self.selected_case,
                self.name_field.value or '', self.case_converter.source,
                self.selected_algorithm if update else None)
            self.error.value, self.notice.value = '', 'Algorithm saved and set as preferred.'
            self._render_library()
        except ValueError as ex:
            self.error.value = str(ex)
        self._update()

    def _delete_algorithm(self, e=None):
        self.state.delete_case_algorithm(self.selected_case, self.selected_algorithm)
        self.selected_algorithm = self.record().preferred_algorithm
        self._render_library()
        self._update()

    def _save_notes(self, key, value):
        self.state.update_corner_case(key, notes=value)

    def _choose_learning_status(self, key, status, e):
        if e.control.value:
            self._set_record(key, status=status)
        else:
            # One status always remains selected; clicking its checkmark again
            # leaves it selected without writing a different or empty status.
            e.control.value = self.record(key).status == status
            self._update()

    def _set_record(self, key, **values):
        try:
            self.state.update_corner_case(key, **values)
            if key == self.selected_case:
                self._render_library()
        except ValueError as ex:
            self.error.value = str(ex)
        self._update()

    def _hide(self, e=None):
        self.hidden = not self.hidden
        self._render_library()
        self._update()

    def _random_case(self, e=None):
        matches = self.filtered_cases()
        if not matches:
            self.notice.value = 'No cases match the current filters.'
            self._update()
            return
        alternatives = [c for c in matches if c.id != self.selected_case] or matches
        self.select_case(random.choice(alternatives).id, edit=True)

    def _playground_input_changed(self, converter):
        if self.mode == 'explorer': self._update_playground_analysis()

    def _analyze(self, e=None):
        self.playground_converter.sync(notify=False)
        self._update_playground_analysis()

    def _update_playground_analysis(self, *, update=True):
        converter = self.playground_converter
        source = converter.source
        if converter.algorithm is None:
            self._analysis = self._identified = None
            self._playground_analysis_source = None
            self._load_viewer("R R'", None, (), 'playground-empty')
            self.viewer.move_text.visible = False
            self.effect_area.controls = [ft.Text('Paste a commutator or final alg to inspect its effect.',
                size=12, color=ft.Colors.ON_SURFACE_VARIANT)]
            self.explorer_effect.value = ''
        else:
            if source != self._playground_analysis_source or self._loaded_key != (source, 'playground'):
                self._analysis = analyze_algorithm(converter.algorithm)
                self._identified = self._analysis.ufr_case
                targets = tuple(self._identified.split(':')) if self._identified else ()
                self._load_viewer(source, None, targets, 'playground')
                self._playground_analysis_source = source
            self.viewer.move_text.visible = True
            self._render_effect()
        valid = converter.algorithm is not None
        self.viewer.play_button.disabled = not valid
        self.playground_save.disabled = self.playground_copy.disabled = not valid
        self.open_case_button.disabled = self._identified is None
        if update: self._update()

    def _sticker_label(self, sticker):
        if self.scheme is None: return sticker
        category = self.scheme.corners if len(sticker) == 3 else self.scheme.edges
        letter = category.stickers.get(sticker, '')
        return f'{sticker} ({letter})' if letter and letter != 'BUFFER' else sticker

    def _render_effect(self):
        effect = self._analysis
        if effect is None: return
        self.explorer_effect.value = (f'{len(effect.moves)} moves · {len(effect.affected_corners)} corners · '
                                     f'{len(effect.affected_edges)} edges affected')
        controls = [ft.Text('Effect from solved', size=14, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                    self.explorer_effect,
                    ft.Text('Arrows show where pieces move. Sticker details include orientation.',
                            size=11, color=ft.Colors.ON_SURFACE_VARIANT)]
        for label, cycles in (('Corner cycles', effect.corner_cycles), ('Edge cycles', effect.edge_cycles)):
            controls.append(ft.Text(label + ': ' + ('; '.join(' → '.join((*cycle, cycle[0])) for cycle in cycles) if cycles else 'None'),
                                    size=12, color=ft.Colors.ON_SURFACE))
        for label, pieces in (('Twists in place', effect.twisted_in_place), ('Flips in place', effect.flipped_in_place)):
            if pieces: controls.append(ft.Text(label + ': ' + ', '.join(pieces), size=12, color=ft.Colors.ON_SURFACE))
        if effect.ufr_case:
            first, second = effect.ufr_case.split(':')
            controls.append(ft.Text(f'UFR case it solves: {self._sticker_label(first)} → {self._sticker_label(second)}',
                                    size=12, color=ft.Colors.PRIMARY))
        if effect.reorients_cube:
            controls.append(ft.Text('Includes a whole-cube reorientation. Piece effects are relative to the centers.',
                                    size=11, color=ft.Colors.ON_SURFACE_VARIANT))
        if effect.sticker_changes:
            controls.append(ft.ExpansionTile(title=ft.Text(f'Sticker mappings · {len(effect.sticker_changes)} changed',
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT), dense=True, min_tile_height=34, tile_padding=0,
                expanded_cross_axis_alignment=ft.CrossAxisAlignment.START,
                controls=[ft.Text(f'{self._sticker_label(a)} → {self._sticker_label(b)}', size=11,
                                  color=ft.Colors.ON_SURFACE) for a, b in effect.sticker_changes]))
        self.effect_area.controls = controls

    def _refresh_playground_saved(self):
        saved = self.state.data.playground_algorithms
        if self.selected_playground not in {a.id for a in saved}: self.selected_playground = None
        self.playground_saved.options = [ft.DropdownOption('', 'Unsaved playground')] + [ft.DropdownOption(a.id, a.name) for a in saved]
        self.playground_saved.value = self.selected_playground or ''
        self.playground_delete.disabled = self.selected_playground is None
        self.playground_save.content = 'Save changes' if self.selected_playground else 'Save algorithm'

    def _render_explorer(self):
        self.playground_converter.sync(notify=False)
        self._refresh_playground_saved()
        self.playground_toolbar = ft.Row([
            ft.Container(self.playground_saved, expand=True),
            ft.TextButton('New', icon=ft.Icons.ADD, on_click=lambda e: self._new_playground()), self.playground_delete,
        ], spacing=6, height=42)
        notes = ft.ExpansionTile(title=ft.Text('Notes', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            dense=True, min_tile_height=34, tile_padding=0, maintain_state=True,
            controls=[self.playground_notes], expanded_cross_axis_alignment=ft.CrossAxisAlignment.START)
        self.playground_tools = [self.playground_converter, self.playground_name, notes,
            ft.Row([self.playground_save, self.playground_copy], wrap=True, spacing=4),
            self.open_case_button, self.error, self.notice]
        self._update_playground_analysis(update=False)
        self._layout()

    def _new_playground(self, source=''):
        self.selected_playground = self._loaded_playground_record = None
        self.playground_name.value = self.playground_notes.value = ''
        self.playground_converter.load(source)
        self._playground_analysis_source = None
        self.error.value = self.notice.value = ''
        self._render_explorer()
        self._update()

    def _choose_playground(self, e):
        identifier = e.control.value or ''
        if not identifier:
            self._new_playground()
            return
        saved = next((a for a in self.state.data.playground_algorithms if a.id == identifier), None)
        if saved is None: return
        self.selected_playground = identifier
        self._loaded_playground_record = (saved.id, saved.name, saved.alg, saved.notes)
        self.playground_name.value, self.playground_notes.value = saved.name, saved.notes
        self.playground_converter.load(saved.alg)
        self._playground_analysis_source = None
        self.error.value = self.notice.value = ''
        self._render_explorer()
        self._update()

    def _save_playground(self, e=None, *, as_new=False):
        self.notice.value = ''
        try:
            self.playground_converter.sync(notify=False)
            if self.playground_converter.algorithm is None:
                raise ValueError('Enter a valid algorithm before saving.')
            self.selected_playground = self.state.save_playground_algorithm(self.playground_name.value or '',
                self.playground_converter.source, self.playground_notes.value or '',
                None if as_new else self.selected_playground)
            saved = next(a for a in self.state.data.playground_algorithms if a.id == self.selected_playground)
            self.playground_name.value = saved.name
            self._loaded_playground_record = (saved.id, saved.name, saved.alg, saved.notes)
            self.error.value, self.notice.value = '', 'Playground algorithm saved.'
            self._refresh_playground_saved()
            self._update_playground_analysis(update=False)
        except ValueError as ex:
            self.error.value = str(ex)
        self._update()

    def _delete_playground(self, e=None):
        self.state.delete_playground_algorithm(self.selected_playground)
        self.selected_playground = self._loaded_playground_record = None
        self.notice.value = 'Removed from saved playground algorithms.'
        self._refresh_playground_saved()
        self._update()

    def _open_playground_draft(self, e=None):
        source = self.case_converter.source
        self._set_mode('explorer')
        self._new_playground(source)

    def _open_identified(self, e=None):
        if self._identified:
            key, source = self._identified, self.playground_converter.source
            name = self.playground_name.value or 'My alg'
            self.mode = 'library'
            self._loaded_key = None
            self.select_case(key, edit=True)
            self.case_converter.load(source)
            self.name_field.value = name
            self._preview_editor(sync=False)

    def _render_lesson(self):
        alg = parse_algorithm(BASE_ALG)
        key = identify_case(alg)
        case = self.cases[key]
        self.viewer.move_text.visible = True
        self._load_viewer(BASE_ALG, inverse_state(normalized_state(alg)), (case.first, case.second), 'lesson')
        self.detail_controls = [
            ft.Text('Your first commutator', size=20, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
            ft.Text(f'UFR buffer · targets {case.first}, {case.second} · {BASE_ALG}', size=13, color=ft.Colors.ON_SURFACE),
            ft.Text('A commutator has four parts: A, B, undo A, undo B. Watch how the intermediate disturbance is restored while three corners cycle.',
                    size=13, color=ft.Colors.ON_SURFACE_VARIANT),
            self.viewer,
        ]
        explanations = {'A': 'A turns R and prepares the interchange.',
                        'B': "B is U' L' U: the insertion sequence.",
                        'Undo A': "R' reverses A while the pieces are in their new positions.",
                        'Undo B': 'Undo the insertion. The other pieces return to their starting positions.'}
        for stage in alg.stages:
            self.detail_controls.append(ft.Column([
                ft.Text(f'{stage.label}: {" ".join(alg.moves[stage.start:stage.end])}',
                        size=14, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                ft.Text(explanations[stage.label], size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.TextButton('Watch this part', on_click=lambda e, s=stage: self._watch_stage(s)),
            ], spacing=4))
        self.detail_controls.append(ft.TextButton('Explore this case in the library', on_click=lambda e: self._lesson_case(key)))
        self._layout()

    def _watch_stage(self, stage):
        self.viewer.seek(stage.start)
        self.viewer.play_to(stage.end)

    def _lesson_case(self, key):
        self.mode = 'library'
        self.select_case(key)

    def _set_mode(self, mode):
        self.case_converter.cancel_pending()
        self.playground_converter.cancel_pending()
        self._navigation_token += 1
        self.viewer.stop(update=False)
        self.mode = mode
        self._loaded_key = None
        self.error.value = self.notice.value = ''
        if mode == 'overview': self._render_overview()
        elif mode == 'library': self._render_library()
        elif mode == 'explorer': self._render_explorer()
        else: self._render_lesson()
        self._update()

    def _choose_scheme(self, e):
        self.label_scheme = e.control.value or None
        self.refresh()

    def _layout(self):
        width, height = self._viewport
        self.title.size = 18 if width < 440 else 20
        self.scheme_picker.width = min(200, max(108, width * .38))
        self.scheme_picker.height = 38
        self.header_top.height = 42
        if width >= 1080:
            self.section_nav.expand = True
            self.header_top.content = ft.Row([self.title, self.section_nav, self.scheme_picker], spacing=12)
            self.header.controls = [self.header_top]
            self.header.height = 42
        else:
            self.section_nav.expand = False
            self.header_top.content = ft.Row([ft.Container(self.title, expand=True), self.scheme_picker], spacing=8)
            self.header.controls = [self.header_top, self.section_nav]
            self.header.height = 82
        for key, button in self.section_buttons.items():
            selected = key == self.mode
            button.style = ft.ButtonStyle(
                color=ft.Colors.ON_PRIMARY_CONTAINER if selected else ft.Colors.ON_SURFACE_VARIANT,
                bgcolor=ft.Colors.PRIMARY_CONTAINER if selected else ft.Colors.TRANSPARENT,
                text_style=ft.TextStyle(size=12), shape=ft.RoundedRectangleBorder(radius=7),
                padding=ft.Padding.symmetric(horizontal=9, vertical=6))
        available = max(60, height - self.header.height - self.spacing)
        self.body.width, self.body.height = width, available
        self.detail_scrolls = []
        if self.mode == 'overview':
            self.body.controls = [ft.ListView(controls=self.overview_controls, spacing=12,
                height=available, scroll=ft.ScrollMode.AUTO)]
            return
        if self.mode == 'library':
            self._layout_library(width, available)
            return
        if self.mode == 'explorer':
            self._layout_playground(width, available)
            return
        self.viewer.set_viewport(max(180, width - 24), min(340, max(160, available - 210)))
        self.body.controls = [ft.ListView(controls=[panel(ft.Column(self.detail_controls, spacing=10, tight=True),
            padding=12, width=width)], height=available, scroll=ft.ScrollMode.AUTO,
            build_controls_on_demand=False)]

    def _layout_playground(self, width, available):
        content_height = max(100, available - 60)
        if width >= 980:
            tools_width = min(460, width * .42)
            viewer_width = width - tools_width - 18
            self.viewer.set_viewport(viewer_width, min(360, max(140, content_height - 170)))
            left = ft.ListView(controls=[self.viewer, self.effect_area], spacing=14,
                height=content_height - 20, build_controls_on_demand=False, scroll=ft.ScrollMode.AUTO)
            right = ft.ListView(controls=self.playground_tools, spacing=10,
                height=content_height - 20, build_controls_on_demand=False, scroll=ft.ScrollMode.AUTO)
            self.body.controls = [self.playground_toolbar, ft.Row([
                panel(left, padding=10, width=viewer_width + 20, height=content_height),
                panel(right, padding=10, width=tools_width - 12, height=content_height),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START)]
        else:
            self.viewer.set_viewport(width - 24, min(280, max(160, available - 260)))
            self.body.controls = [ft.ListView(controls=[self.playground_toolbar,
                self.playground_converter, self.viewer, self.effect_area,
                ft.Column(self.playground_tools[1:], spacing=10, tight=True)],
                height=available, spacing=12, build_controls_on_demand=False, scroll=ft.ScrollMode.AUTO)]

    def _layout_library(self, width, available):
        wide = width >= 980
        sidebar_width, gap, padding = 244, 10, 10
        detail_width = width - sidebar_width - gap if wide else width
        inner_width = detail_width - padding * 2
        self.case_list.height = max(72, available - 294 - (86 if self.filter_more.expanded else 0)) if wide else 180
        sidebar_content = ft.Column([self.search, self.subset, self.first_target, self.second_target,
            self.filter_more, self.list_meta, self.case_list, self.more_button], spacing=6, tight=True)
        if wide and inner_width >= 760:
            # Keep only algorithm work in the wider right pane. Case metadata
            # uses the room under the compact cube in the left pane.
            tools_width = max(360, round(inner_width * .46))
            viewer_width = inner_width - tools_width - gap
            content_height = max(80, available - padding * 2 - self.case_toolbar.height - 8)
            self.viewer.set_viewport(viewer_width, min(310, max(140, content_height * .5)))
            cube_scroll = ft.ListView(controls=[self.viewer, self.case_details], spacing=12, height=content_height,
                build_controls_on_demand=False, scroll=ft.ScrollMode.AUTO)
            tools_scroll = ft.ListView(controls=self.tool_controls, spacing=8, height=max(56, content_height - 24),
                build_controls_on_demand=False, scroll=ft.ScrollMode.AUTO)
            case_content = ft.Column([self.case_toolbar, ft.Row([
                ft.Container(cube_scroll, width=viewer_width),
                panel(tools_scroll, width=tools_width, height=content_height, padding=12),
            ], spacing=gap, vertical_alignment=ft.CrossAxisAlignment.START)], spacing=8)
            self.detail_scrolls = [cube_scroll, tools_scroll]
            self.case_canvas_top = padding + self.case_toolbar.height + 8
            self.split_tools = True
        else:
            before_cube = padding + self.case_toolbar.height + 8 + (46 if not wide else 0)
            self.viewer.set_viewport(inner_width, min(320, max(140, available - before_cube - 130)))
            case_content = ft.ListView(controls=self.detail_controls, spacing=8,
                height=available - padding * 2, build_controls_on_demand=False,
                scroll=ft.ScrollMode.AUTO, key=f'case-{self.selected_case}')
            self.detail_scrolls = [case_content]
            self.case_canvas_top = before_cube
            self.split_tools = False
        case_panel = panel(case_content, padding=padding, width=detail_width, height=available)
        if wide:
            browser_scroll = ft.ListView(controls=sidebar_content.controls, spacing=6,
                height=available - padding * 2, build_controls_on_demand=False, scroll=ft.ScrollMode.AUTO)
            self.body.controls = [ft.Row([
                panel(browser_scroll, padding=padding, width=sidebar_width, height=available), case_panel,
            ], spacing=gap, vertical_alignment=ft.CrossAxisAlignment.START)]
        else:
            if self.mobile_browser is None:
                self.browser_title = ft.Text('', size=12, color=ft.Colors.ON_SURFACE)
                self.mobile_browser = ft.ExpansionTile(title=self.browser_title, dense=True,
                    min_tile_height=38, tile_padding=ft.Padding.symmetric(horizontal=6),
                    expanded_cross_axis_alignment=ft.CrossAxisAlignment.START, maintain_state=True)
            self.browser_title.value = f'Browse cases · {len(self.filtered_cases())} matching'
            self.mobile_browser.controls = [sidebar_content]
            # One outer scroll view avoids nesting another full-height detail
            # viewport below the mobile browser tile.
            case_content.height = None
            case_content = ft.Column(self.detail_controls, spacing=8, tight=True)
            case_panel.content = case_content
            case_panel.height = None
            body_scroll = ft.ListView(controls=[self.mobile_browser, case_panel], spacing=8,
                height=available, scroll=ft.ScrollMode.AUTO, build_controls_on_demand=False,
                key=f'case-mobile-{self.selected_case}')
            self.body.controls = [body_scroll]
            self.detail_scrolls = [body_scroll]

    def set_viewport(self, width, height):
        self._viewport = (max(240, width), max(220, height))
        self.width, self.height = self._viewport
        self._layout()

    def refresh(self, update=True):
        names = self.state.scheme_names
        if self.label_scheme not in names:
            self.label_scheme = self.state.data.active_scheme if self.state.data.active_scheme in names else (names[0] if names else None)
        self.scheme_picker.options = [ft.DropdownOption(name) for name in names]
        self.scheme_picker.value = self.label_scheme
        self.scheme_picker.disabled = not bool(names)
        if self.mode == 'overview': self._render_overview()
        elif self.mode == 'library': self._render_library()
        elif self.mode == 'lesson': self._render_lesson()
        else:
            record = next((a for a in self.state.data.playground_algorithms if a.id == self.selected_playground), None)
            if record is not None and (record.id, record.name, record.alg, record.notes) != self._loaded_playground_record:
                self._loaded_playground_record = (record.id, record.name, record.alg, record.notes)
                self.playground_name.value, self.playground_notes.value = record.name, record.notes
                self.playground_converter.load(record.alg)
                self._playground_analysis_source = None
            self.viewer.scheme = self.scheme
            self.viewer.dark_mode = self.state.data.dark_mode
            self.viewer._redraw(update=False)
            self._render_explorer()
        if update: self._update()

    def set_active(self, active):
        self.active = bool(active)
        if not active:
            self._navigation_token += 1
            self.case_converter.cancel_pending()
            self.playground_converter.cancel_pending()
            self.viewer.stop(update=False)
