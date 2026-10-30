"""Method Library overview, UFR cases, explorer and commutator lesson."""
import random

import flet as ft

from core.algorithms import changed_stickers, inverse_state, normalized_state, parse_algorithm
from core.corner_algorithms import QUALITY_NOTICE, builtin_algorithms, display_builtin_algorithms
from core.corner_cases import BASE_ALG, BUFFER, SUBSETS, TARGETS, case_letters, corner_cases, identify_case
from data.models import CornerCaseRecord
from ui.components.algorithm_cube import AlgorithmCube
from ui.design import activity_card, eyebrow, panel
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
        self.editor_open = self.notes_open = False
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
        self.status_filter = dropdown(label='Learning status', value='all', height=38, dense=True,
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
        self._derived_for = None
        self.commutator_text = ft.Text('', size=12, font_family='monospace', selectable=True, color=ft.Colors.ON_SURFACE)
        self.commutator_note = ft.Text('', size=11, color=ft.Colors.ON_SURFACE_VARIANT)
        self.use_commutator = ft.TextButton('Use this notation', on_click=self._use_commutator)
        self.commutator_panel = ft.Column([self.commutator_text, self.commutator_note, self.use_commutator],
                                          spacing=4, tight=True, visible=False)
        self.algorithm_field = field(label='Algorithm · edit or paste your own', multiline=True, min_lines=2, max_lines=5,
            hint_text="Supports Fw, Fw', f, [A,B] and setup:[A,B].",
            value='', text_size=14, on_change=self._clear_commutator, on_submit=lambda e: self._preview_editor())
        self.name_field = field(label='Algorithm name (optional)', value='My alg', height=38, dense=True)
        self.explorer_field = field(label='Algorithm or commutator', value=BASE_ALG, multiline=True,
            min_lines=2, max_lines=5, on_change=self._clear_commutator, on_submit=lambda e: self._analyze())
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
            for key, label in (('overview', 'Overview'), ('library', 'Case Library'),
                               ('explorer', 'Algorithm Explorer'), ('lesson', 'Commutator Lesson'))
        }
        self.section_nav = ft.Row(list(self.section_buttons.values()), spacing=2, height=36,
                                  scroll=ft.ScrollMode.AUTO)
        self.header = ft.Column(spacing=4)
        self.controls = [self.header, self.body]

    def _render_overview(self):
        cards = [
            activity_card('Learn the basics',
                'Start with a short commutator lesson. Watch A, B, undo A and undo B move the corners.',
                ft.Icons.SCHOOL_OUTLINED, 'Start the lesson', lambda e: self._set_mode('lesson'), 'START HERE'),
            activity_card('Browse UFR cases',
                'Find a case by subset, target letters or learning status. Save alternatives, notes and favorites.',
                ft.Icons.GRID_VIEW, 'Open Case Library', lambda e: self._set_mode('library'), '378 CASES'),
            activity_card('Explore an algorithm',
                'Paste an alg or commutator, play it in 3D or 2D, and inspect its effect on the cube.',
                ft.Icons.VIEW_IN_AR_OUTLINED, 'Open Algorithm Explorer', lambda e: self._set_mode('explorer'), 'TRY AN ALG'),
        ]
        for card in cards:
            card.col = {'xs': 12, 'md': 4}
        records = list(self.state.data.corner_case_library.values())
        self.overview_controls = [
            ft.Column([
                eyebrow('Learn / explore / collect'),
                ft.Text('Choose where to begin.', size=23, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                ft.Text('Learn how commutators work, then build your own case collection. '
                        'This library uses UFR as its corner buffer and your selected scheme for letter labels.',
                        size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(QUALITY_NOTICE, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=6),
            ft.ResponsiveRow(cards, spacing=12, run_spacing=12),
            panel(ft.Column([
                ft.Text('Jump to a subset', size=16, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                ft.Text('The two layers describe the first and second target pieces, in memo order.',
                        size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.ResponsiveRow([
                    ft.OutlinedButton(f'{subset} · {54 if subset == "U/U" else 108} cases',
                        col={'xs': 6, 'md': 3}, on_click=lambda e, s=subset: self._open_subset(s))
                    for subset in SUBSETS
                ], spacing=8, run_spacing=8),
            ], spacing=10), padding=16),
            ft.Row([
                ft.Text(f'{sum(r.status == "learned" for r in records)} / 378 learned', size=12, color=ft.Colors.PRIMARY),
                ft.Text(f'{sum(r.status == "learning" for r in records)} learning', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(f'{sum(r.favorite for r in records)} favorites', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(f'{sum(len(r.algorithms) for r in records)} saved algorithms', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=20, wrap=True),
        ]
        self._layout()

    def _open_subset(self, subset):
        self.search.value = ''
        self.subset.value = subset
        self.first_target.value = self.second_target.value = self.status_filter.value = 'all'
        self.favorites.value = False
        self.limit = 50
        self.mode = 'library'
        self._loaded_key = None
        self.select_case(next(c.id for c in self.cases.values() if c.subset == subset))

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
        self.editor_open, self.notes_open = bool(edit), False
        self._clear_commutator(update=False)
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
                await scroll.scroll_to(scroll_key=self.editor_tile.key, duration=0)
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
        parsed = parse_algorithm(case.starter)
        initial = inverse_state(normalized_state(parsed))
        try:
            candidate = parse_algorithm(source)
            if identify_case(candidate) != case.id:
                raise ValueError('Saved algorithm solves another case. Edit it before using it.')
            if changed_variant or not self._loaded_key or self._loaded_key[1] != case.id:
                self._load_viewer(source, initial, (case.first, case.second), case.id)
        except ValueError as ex:
            self.error.value = str(ex) + ' Showing the verified starter.'
            self._load_viewer(case.starter, initial, (case.first, case.second), case.id)
        if changed_variant:
            self.algorithm_field.value, self.name_field.value = source, name if personal else 'My alg'
            self._editor_key = editor_key
        self.viewer.scheme = self.scheme
        self.viewer.dark_mode = self.state.data.dark_mode
        self.viewer._redraw(update=False)
        self.algorithm_field.visible = not self.hidden
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
        status = dropdown(label='Learning status', value=record.status, height=38, dense=True,
            options=[ft.DropdownOption(s, s.title()) for s in ('new', 'learning', 'learned')],
            on_select=lambda e, key=case.id: self._set_record(key, status=e.control.value))
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
        self.editor_tile = ft.ExpansionTile(
            key=ft.ScrollKey('case-algorithm-editor'),
            title=ft.Text('Edit / replace alg', size=13, color=ft.Colors.ON_SURFACE),
            leading=ft.Icon(ft.Icons.EDIT_OUTLINED, size=17, color=ft.Colors.PRIMARY),
            expanded=self.editor_open, visible=not self.hidden, maintain_state=True,
            dense=True, min_tile_height=38, tile_padding=0,
            controls_padding=ft.Padding.only(top=6, bottom=8),
            expanded_cross_axis_alignment=ft.CrossAxisAlignment.START,
            on_change=lambda e: self._remember_tile('editor_open', e),
            controls=[ft.Column([
                ft.Text('Saved notation · paste a replacement, then save to make it preferred.',
                        size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                self.algorithm_field, self.name_field,
                ft.Row([ft.FilledButton('Save changes & use' if personal else 'Save & use my alg',
                                       on_click=lambda e, update=bool(personal): self._save_algorithm(update)),
                        ft.TextButton('Preview alg', on_click=lambda e: self._preview_editor())], wrap=True, spacing=4),
                ft.TextButton('Find commutator', icon=ft.Icons.AUTO_FIX_HIGH, on_click=self._find_commutator),
                self.commutator_panel,
                ft.Row([ft.TextButton('Save as another alternative', on_click=lambda e: self._save_algorithm(False)),
                        small_icon(ft.Icons.DELETE_OUTLINE, 'Delete selected personal alternative', self._delete_algorithm,
                                   disabled=not bool(personal))],
                       wrap=True, spacing=4),
            ], spacing=8, tight=True)])
        self.notes_tile = ft.ExpansionTile(title=ft.Text('Case notes', size=13, color=ft.Colors.ON_SURFACE),
            expanded=self.notes_open, maintain_state=True, dense=True, min_tile_height=38, tile_padding=0,
            controls_padding=ft.Padding.only(top=6, bottom=8),
            expanded_cross_axis_alignment=ft.CrossAxisAlignment.START,
            on_change=lambda e: self._remember_tile('notes_open', e), controls=[self.notes_field])
        self.tool_controls = [
            self.variant_picker,
            ft.Text(provenance, size=11, color=ft.Colors.PRIMARY, max_lines=2, tooltip=provenance),
            ft.TextButton('Use selected alg', on_click=lambda e: self._set_record(case.id, preferred=self.selected_algorithm)),
            self.editor_tile, status, self.notes_tile,
            ft.Text(QUALITY_NOTICE, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            self.error, self.notice,
        ]
        self.detail_controls = [self.case_toolbar, self.viewer, ft.Column(self.tool_controls, spacing=8, tight=True)]
        self.error.visible, self.notice.visible = bool(self.error.value), bool(self.notice.value)
        self._layout()

    def _choose_variant(self, e):
        self._clear_commutator(update=False)
        self.selected_algorithm = e.control.value or ''
        self.error.value = self.notice.value = ''
        self._render_library()
        self._update()

    def _preview_editor(self):
        case = self.cases[self.selected_case]
        try:
            algorithm = parse_algorithm(self.algorithm_field.value or '')
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
            self.selected_algorithm = self.state.save_case_algorithm(self.selected_case,
                self.name_field.value or '', self.algorithm_field.value or '',
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

    def _clear_commutator(self, e=None, *, update=True):
        self._derived_for = None
        self.commutator_panel.visible = False
        if update and self._page() is not None:
            self.commutator_panel.update()

    def _find_commutator(self, e=None):
        from core.commutator_finder import find_commutator
        field = self.algorithm_field if self.mode == 'library' else self.explorer_field
        source = field.value or ''
        self._clear_commutator(update=False)
        self.notice.value = ''
        try:
            result = find_commutator(source)
            self.error.value = ''
            self.commutator_panel.visible = True
            self.use_commutator.visible = result is not None
            if result is not None:
                self._derived_for = (self.mode, source, result)
                self.commutator_text.value = result.expression
                self.commutator_note.value = ('Equivalent commutator · verified against your entered moves. Use it, then save when ready.'
                    if self.mode == 'library' else 'Equivalent commutator · verified against your entered moves. Use it to analyze the notation.')
            else:
                self.commutator_text.value = 'No short commutator form found.'
                self.commutator_note.value = 'Plain moves can still be saved and practised. Other commutator forms may exist.'
        except ValueError as ex:
            self.error.value = str(ex)
        self._update()

    def _use_commutator(self, e=None):
        if self._derived_for is None:
            return
        mode, source, result = self._derived_for
        field = self.algorithm_field if self.mode == 'library' else self.explorer_field
        if mode != self.mode or source != (field.value or ''):
            self._clear_commutator()
            return
        field.value = result.expression
        self.use_commutator.visible = False
        self.commutator_note.value = ('Notation applied to the editor. Save when ready.'
            if self.mode == 'library' else 'Notation applied to Algorithm Explorer.')
        if self.mode == 'library':
            self._preview_editor()
        else:
            self._analyze()

    def _analyze(self, e=None):
        try:
            algorithm = parse_algorithm(self.explorer_field.value or '')
            net = normalized_state(algorithm)
            self._identified = None
            try:
                self._identified = identify_case(algorithm)
            except ValueError:
                pass
            changed = changed_stickers(net)
            corners = {frozenset(s) for s in changed if len(s) == 3}
            edges = {frozenset(s) for s in changed if len(s) == 2}
            self.explorer_effect.value = f'Final effect: {len(corners)} corners, {len(edges)} edges changed (including orientation).'
            if self._identified:
                case = self.cases[self._identified]
                self.explorer_effect.value += f' UFR case: {case.first} → {case.second}.'
            targets = (case.first, case.second) if self._identified else ()
            self._load_viewer(algorithm.source, None, targets, 'explorer')
            self.error.value = ''
            self._render_explorer()
        except ValueError as ex:
            self.viewer.stop(update=False)
            self.error.value = str(ex)
        self._update()

    def _render_explorer(self):
        self.viewer.move_text.visible = True
        self.detail_controls = [
            ft.Text('Algorithm Explorer', size=20, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
            ft.Text("Start solved and inspect an alg’s final effect. Supports wide turns such as Fw / Fw' (or f / f'), "
                    'face/slice turns, rotations, groups, [A, B], [setup: alg] and setup:[A,B].',
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            self.explorer_field, ft.Row([ft.FilledButton('Analyze & load', on_click=self._analyze),
                ft.TextButton('Find commutator', icon=ft.Icons.AUTO_FIX_HIGH, on_click=self._find_commutator)], wrap=True),
            self.commutator_panel, self.error,
            self.explorer_effect, self.viewer,
            ft.Text('Final effects are compared in the original cube orientation. Camera dragging changes only the view.',
                    size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.TextButton('Open matching UFR case', disabled=self._identified is None,
                          on_click=self._open_identified),
        ]
        self._layout()

    def _open_identified(self, e=None):
        if self._identified:
            source = self.explorer_field.value
            self.mode = 'library'
            self.select_case(self._identified)
            self.algorithm_field.value = source
            self.name_field.value = 'My alg'
            self._preview_editor()

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
        self._clear_commutator(update=False)
        self._navigation_token += 1
        self.viewer.stop(update=False)
        self.mode = mode
        self._loaded_key = None
        self.error.value = self.notice.value = ''
        if mode == 'overview': self._render_overview()
        elif mode == 'library': self._render_library()
        elif mode == 'explorer': self._analyze()
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
        self.viewer.set_viewport(max(180, width - 24), min(340, max(160, available - 210)))
        self.body.controls = [ft.ListView(controls=[panel(ft.Column(self.detail_controls, spacing=10, tight=True),
            padding=12, width=width)], height=available, scroll=ft.ScrollMode.AUTO,
            build_controls_on_demand=False)]

    def _layout_library(self, width, available):
        wide = width >= 980
        sidebar_width, gap, padding = 244, 10, 10
        detail_width = width - sidebar_width - gap if wide else width
        inner_width = detail_width - padding * 2
        self.case_list.height = max(72, available - 294 - (86 if self.filter_more.expanded else 0)) if wide else 180
        sidebar_content = ft.Column([self.search, self.subset, self.first_target, self.second_target,
            self.filter_more, self.list_meta, self.case_list, self.more_button], spacing=6, tight=True)
        if wide and inner_width >= 760:
            # The cube and alg tools scroll independently. Opening the editor
            # cannot push the cube below the first view.
            tools_width = min(320, max(280, inner_width * .32))
            viewer_width = inner_width - tools_width - gap
            content_height = max(80, available - padding * 2 - self.case_toolbar.height - 8)
            self.viewer.set_viewport(viewer_width, min(390, max(140, content_height - 130)))
            cube_scroll = ft.ListView(controls=[self.viewer], height=content_height,
                build_controls_on_demand=False, scroll=ft.ScrollMode.AUTO)
            tools_scroll = ft.ListView(controls=self.tool_controls, spacing=8, height=content_height,
                build_controls_on_demand=False, scroll=ft.ScrollMode.AUTO)
            case_content = ft.Column([self.case_toolbar, ft.Row([
                ft.Container(cube_scroll, width=viewer_width),
                ft.Container(tools_scroll, width=tools_width, padding=ft.Padding.only(left=8),
                    border=ft.Border(left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT))),
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
            self.viewer.scheme = self.scheme
            self.viewer.dark_mode = self.state.data.dark_mode
            self.viewer._redraw(update=False)
            self._render_explorer()
        if update: self._update()

    def set_active(self, active):
        self.active = bool(active)
        if not active:
            self._navigation_token += 1
            self.viewer.stop(update=False)
