"""A shuffled, self-rated recall round for the fixed UFR corner library."""
import asyncio

import flet as ft

from core.algorithms import Algorithm
from core.corner_cases import SUBSETS, TARGETS
from core.corner_trainer import CornerRecallSession, STATUSES, TrainerFilters, matching_cases
from ui.components.algorithm_cube import AlgorithmCube
from ui.design import action_button, panel, section_title
from ui.theme_colors import ThemeAwarePage, apply_palette


@ft.control
class CornerTrainer(ThemeAwarePage, ft.Column):
    open_case_callback = None
    session_change_callback = None

    @property
    def state(self):
        return self.data

    def init(self):
        self.spacing = 0
        self.scheme = None
        self.session = None
        self.view = 'filters'
        self.active = False
        self.busy = False
        self.error = ''
        self._token = 0
        self._viewport = (1200, 650)
        self._loaded_card = None
        self.viewer = AlgorithmCube()
        self._viewer_controls = list(self.viewer.controls)
        self.viewer.letter_switch.value = self.viewer.focus_switch.value = False
        self.subsets = {s: ft.Checkbox(label=s, value=True, label_style=ft.TextStyle(size=13),
                       on_change=self._filter_changed) for s in SUBSETS}
        self.statuses = {s: ft.Checkbox(label=s.title(), value=True, label_style=ft.TextStyle(size=13),
                        on_change=self._filter_changed) for s in STATUSES}
        def target(label):
            return ft.Dropdown(label=label, value='all', dense=True, height=42, text_size=13,
                color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT),
                on_select=self._filter_changed, col={'xs':12,'sm':6})
        self.first_target, self.second_target = target('First target'), target('Second target')
        self.favorites = ft.Checkbox(label='Favorites only', value=False, label_style=ft.TextStyle(size=13),
                                    on_change=self._filter_changed)
        self.match_text = ft.Text(size=13, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY)
        self.start_button = action_button('Start session', primary=True, icon=ft.Icons.PLAY_ARROW, on_click=self._start)
        self.listing = ft.ListView(spacing=12, build_controls_on_demand=False, scroll=ft.ScrollMode.AUTO)
        self.controls = [self.listing]
        self._render()

    def _page(self):
        try: return self.page
        except RuntimeError: return None

    def _update(self):
        apply_palette(self, self.state.data.dark_mode, self.state.data.light_theme)
        if self._page() is not None: self.update()

    def filters(self):
        return TrainerFilters(frozenset(s for s,c in self.subsets.items() if c.value),
            self.first_target.value or 'all', self.second_target.value or 'all',
            frozenset(s for s,c in self.statuses.items() if c.value), bool(self.favorites.value))

    def _filter_changed(self, e=None):
        matches = matching_cases(self.filters(), self.state.data.corner_case_library)
        self.match_text.value = f'{len(matches)} matching cases · one shuffled pass, no repeats'
        self.start_button.disabled = not matches
        self._update()

    def refresh(self, scheme, update=True):
        self.scheme = scheme
        for field, name in ((self.first_target, 'first'), (self.second_target, 'second')):
            def label(sticker):
                letter = scheme.corners.stickers.get(sticker, '') if scheme else ''
                return f'{letter} · {sticker}' if letter and letter != 'BUFFER' else sticker
            field.options = [ft.DropdownOption('all', f'Any {name} target')] + [ft.DropdownOption(s, label(s)) for s in TARGETS]
        self.viewer.dark_mode = self.state.data.dark_mode
        self.viewer.set_simultaneous_moves(self.state.data.simultaneous_moves)
        if self.view == 'filters':
            self.match_text.value = f'{len(matching_cases(self.filters(), self.state.data.corner_case_library))} matching cases · one shuffled pass, no repeats'
            self.start_button.disabled = not matching_cases(self.filters(), self.state.data.corner_case_library)
        self._render()
        if update: self._update()

    def _start(self, e=None, cases=None, scheme=None):
        choices = cases if cases is not None else matching_cases(self.filters(), self.state.data.corner_case_library)
        try:
            self.session = CornerRecallSession(choices, scheme if scheme is not None else self.scheme,
                                               self.state.data.corner_case_library)
        except ValueError as ex:
            self.error = str(ex); self._render(); self._update(); return
        self.view = 'recall'
        self._loaded_card = None
        self._prepare()

    def _prepare(self):
        self._token += 1
        token = self._token
        self.busy, self.error = True, ''
        self._render(); self._update()
        if self._page() is not None:
            self._page().run_task(self._prepare_async, token)
        else:
            self._finish_prepare(token)

    async def _prepare_async(self, token):
        # Paint progress before the bundled solver initializes its tables.
        await asyncio.sleep(.03)
        if token == self._token and self.active and self.view == 'recall':
            self._finish_prepare(token)

    def _finish_prepare(self, token):
        if token != self._token or not self.session: return
        try:
            card = self.session.prepare()
            if token != self._token: return
            self._load_card(card)
        except (ValueError, KeyError) as ex:
            if token != self._token: return
            self.error = f'Could not prepare this case: {ex}'
        self.busy = False
        self._render(); self._update()

    def _load_card(self, card):
        if card is self._loaded_card: return
        # A previous reveal may have enabled labels or highlights. Never let
        # those switches give away the next question's targets.
        self.viewer.letter_switch.value = self.viewer.focus_switch.value = False
        self.viewer.scheme = self.session.scheme
        self.viewer.dark_mode = self.state.data.dark_mode
        self.viewer.load(Algorithm(card.source, card.moves, ()), initial=card.initial,
                         scheme=self.session.scheme, targets=(card.first, card.second))
        self._loaded_card = card

    def _show(self, e=None):
        if self.busy or not self.session: return
        if self.session.reveal():
            self._render(); self._update()

    def _grade(self, remembered):
        if self.busy or not self.session or not self.session.grade(remembered): return
        # Reveal after recording the rating, so this doesn't count as a hint.
        self._render(); self._update()

    def _next(self, e=None):
        if not self.session or not self.session.answered: return
        if self.session.complete: return self._summary()
        if self.session.advance():
            self._prepare()

    def _summary(self, e=None):
        self._token += 1
        self.busy = False
        self.viewer.stop(update=False)
        self.view = 'summary'
        self._render(); self._update()

    def _resume(self, e=None):
        self.view = 'recall'
        if self.session.answered: self.session.advance()
        if self.session.card is None: self._prepare()
        else: self._render(); self._update()

    def _new(self, e=None):
        self._token += 1
        self.busy = False
        self.viewer.stop(update=False)
        self.session, self._loaded_card = None, None
        self.view = 'filters'
        self.error = ''
        self.refresh(self.scheme)

    def _retry(self, e=None):
        missed = [r.card.case_id for r in self.session.results if not r.remembered]
        self._start(cases=missed, scheme=self.session.scheme)

    def _open_case(self, card):
        self.viewer.stop(update=False)
        if self.open_case_callback: self.open_case_callback(card.case_id, card.algorithm_id)

    def _solution(self, card):
        controls = [ft.Text(card.letters if '?' not in card.letters else card.first + ' / ' + card.second,
                      size=24, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY, selectable=True),
            ft.Text(f'UFR → {card.first} → {card.second} · {card.subset}', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text('Commutator', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text(card.commutator or 'No commutator found for this algorithm.', size=13, selectable=True,
                    font_family='monospace', color=ft.Colors.ON_SURFACE),
            ft.Text('Full alg', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text(' '.join(card.moves), size=13, selectable=True, font_family='monospace', color=ft.Colors.ON_SURFACE),
            ft.Text(f'{len(card.moves)} moves · {card.name}', size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.TextButton('Open case & edit alg', icon=ft.Icons.OPEN_IN_NEW, height=36,
                          on_click=lambda e,c=card:self._open_case(c))]
        if '?' in card.letters:
            controls.insert(1, ft.Text(f'Letters: {card.letters} · some stickers are unassigned.', size=12,
                                      color=ft.Colors.ON_SURFACE_VARIANT))
        if card.warning: controls.append(ft.Text(card.warning, size=12, color=ft.Colors.TERTIARY))
        return controls

    def _render(self):
        if self.session_change_callback: self.session_change_callback()
        width, height = self._viewport
        self.width, self.height = width, height
        self.listing.width, self.listing.height = width, height
        if self.view == 'filters':
            self.listing.controls = [
                section_title('3-style corner trainer', ft.Icons.PSYCHOLOGY),
                ft.Text('UFR buffer · set up your cube, recall the alg, then rate each case once.', size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                panel(ft.Column([
                    ft.Text('Target layers · choose one or more', size=13, color=ft.Colors.ON_SURFACE),
                    ft.Row(list(self.subsets.values()), wrap=True, spacing=12),
                    ft.ResponsiveRow([self.first_target,self.second_target], spacing=12, run_spacing=10),
                    ft.Text('Learning status · choose one or more', size=13, color=ft.Colors.ON_SURFACE),
                    ft.Row(list(self.statuses.values()), wrap=True, spacing=12), self.favorites,
                    self.match_text,
                    ft.Row([self.start_button], wrap=True),
                ], spacing=12, tight=True)),
                ft.Text('Use a solved cube for each setup. Recall ratings are separate from your saved learning status.',
                        size=12, color=ft.Colors.ON_SURFACE_VARIANT)]
            if self.error: self.listing.controls.append(ft.Text(self.error, color=ft.Colors.ERROR))
            return
        session = self.session
        if self.view == 'summary':
            reviewed = len(session.results)
            self.listing.controls = [section_title('Session summary', ft.Icons.INSIGHTS),
                ft.Text(f'{session.remembered} remembered · {reviewed-session.remembered} missed · '
                        f'{session.recall_rate:.0f}% self-rated recall' if reviewed else 'No cases rated yet.',
                        size=18, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                ft.Text(f'{reviewed} / {len(session.deck)} reviewed · '
                        f'{sum(r.revealed for r in session.results)} reveals before rating · '
                        f'Scheme: {session.scheme.name if session.scheme else "sticker IDs"}', size=12, color=ft.Colors.ON_SURFACE_VARIANT)]
            actions = [action_button('New session', on_click=self._new)]
            if not session.complete: actions.insert(0, action_button('Resume session', primary=True, on_click=self._resume))
            elif any(not r.remembered for r in session.results):
                actions.insert(0, action_button('Retry missed cases', primary=True, on_click=self._retry))
            self.listing.controls.append(ft.Row(actions, wrap=True, spacing=8))
            for remembered, label in ((False,'Missed cases'),(True,'Remembered cases')):
                results = [r for r in session.results if r.remembered == remembered]
                self.listing.controls.append(ft.Text(f'{label} · {len(results)}', size=16, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE))
                for result in results:
                    card = result.card
                    label = card.letters if '?' not in card.letters else card.first + ' / ' + card.second
                    self.listing.controls.append(ft.ExpansionTile(
                        title=ft.Text(label + (' · reveal used' if result.revealed else ''), size=13, color=ft.Colors.ON_SURFACE),
                        subtitle=ft.Text(f'{card.first} → {card.second} · {card.subset}', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        leading=ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE if remembered else ft.Icons.CANCEL_OUTLINED,
                                        color=ft.Colors.PRIMARY if remembered else ft.Colors.ERROR, size=20),
                        dense=True, expanded_cross_axis_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[ft.Column(self._solution(card), spacing=8, tight=True)]))
            return
        progress = ft.Row([
            ft.Text(f'Case {session.position+1} / {len(session.deck)} · '
                    f'{session.remembered} remembered · {len(session.results)-session.remembered} missed',
                    size=13, color=ft.Colors.ON_SURFACE, expand=True),
            ft.TextButton('End session', height=32, on_click=self._summary),
        ], spacing=8)
        self.listing.controls = [progress]
        if self.error:
            self.listing.controls += [ft.Text(self.error,color=ft.Colors.ERROR),
                ft.TextButton('Try again',on_click=lambda e:self._prepare())]
            return
        if self.busy or session.card is None:
            self.listing.controls += [ft.Row([ft.ProgressRing(width=20,height=20),
                ft.Text('Preparing a verified setup…', size=13, color=ft.Colors.ON_SURFACE_VARIANT)], spacing=10)]
            return
        card = session.card
        shown = session.revealed or session.answered
        self.viewer.controls = self._viewer_controls if shown else [self.viewer.canvas]
        self.viewer.dark_mode = self.state.data.dark_mode
        self.viewer.set_viewport(max(180, (width*.56 if width>=980 else width)-28),
                                 min(360 if width>=980 else 260, max(150, height-280)))
        self.listing.controls.append(panel(ft.Column([
            ft.Text('Setup · from a solved cube', size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text(' '.join(card.setup), size=14, selectable=True, font_family='monospace', color=ft.Colors.ON_SURFACE),
            ft.Text(f'UFR buffer · Scheme: {session.scheme.name if session.scheme else "sticker IDs"} · '
                    'hold the cube in your scheme’s U/F orientation.',size=11,color=ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=5, tight=True), padding=12))
        actions = []
        if not session.answered:
            actions = [action_button('Show alg', primary=True, icon=ft.Icons.VISIBILITY_OUTLINED,
                        on_click=self._show, disabled=session.revealed),
                action_button('Remembered', icon=ft.Icons.CHECK, on_click=lambda e:self._grade(True)),
                action_button('Missed', icon=ft.Icons.CLOSE, on_click=lambda e:self._grade(False),
                              style=ft.ButtonStyle(color=ft.Colors.ERROR))]
        else:
            result = session.results[-1]
            actions = [action_button('View summary' if session.complete else 'Next case', primary=True,
                                    icon=ft.Icons.ARROW_FORWARD,on_click=self._next)]
        detail = []
        if session.answered:
            result = session.results[-1]
            detail.append(ft.Text('Recorded · ' + ('Remembered' if result.remembered else 'Missed'),
                size=13, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY if result.remembered else ft.Colors.ERROR))
        detail += [ft.Row(actions, spacing=8, run_spacing=6, wrap=True)]
        if shown:
            detail += self._solution(card)
            detail.append(ft.Text('Solve this case before applying the next setup.', size=12,color=ft.Colors.ON_SURFACE_VARIANT))
        else:
            detail.append(ft.Text('Recall and execute your alg. Show alg reveals the target letters, commutator and full moves.',
                                  size=13,color=ft.Colors.ON_SURFACE_VARIANT))
        if width>=980:
            self.listing.controls.append(ft.Row([
                panel(self.viewer,padding=12,width=width*.56),
                panel(ft.Column(detail,spacing=10,tight=True),padding=12,width=width*.44-12),
            ],spacing=12,vertical_alignment=ft.CrossAxisAlignment.START))
        else:
            self.listing.controls += [panel(self.viewer,padding=12),panel(ft.Column(detail,spacing=10,tight=True),padding=12)]

    def set_viewport(self, width, height):
        self._viewport = (max(240,width),max(100,height))
        self._render()

    def set_active(self, active):
        self.active = bool(active)
        if not active:
            self._token += 1
            self.busy = False
            self.viewer.stop(update=False)
        elif self.session and self.view == 'recall' and self.session.card is None and not self.busy:
            self._prepare()
