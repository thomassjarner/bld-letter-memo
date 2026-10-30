"""Two linked editable fields: commutator notation and final moves."""
import asyncio

import flet as ft

from core.algorithms import parse_algorithm, simplified_algorithm
from core.commutator_finder import find_commutator, has_commutator_structure


@ft.control
class AlgorithmConverter(ft.Column):
    on_result = None

    def init(self):
        self.spacing = 8
        self._revision = 0
        self._source = ''
        self._comm_snapshot = self._final_snapshot = ''
        self.algorithm = None
        self.pending = False
        self._needs_reverse = False
        self.last_input = 'final'
        self.commutator = self._field('Commutator', '[A, B] or [setup: [A, B]]',
            lambda e: self._input('commutator', self.commutator.value or ''))
        self.final_alg = self._field('Final alg', "R U R' U' · wide/slice moves also work",
            lambda e: self._input('final', self.final_alg.value or ''))
        self.status = ft.Text('Paste in either field; the other updates automatically.', size=11,
                              color=ft.Colors.ON_SURFACE_VARIANT)
        self.controls = [self.commutator, self.final_alg, self.status]

    def _field(self, label, hint, callback):
        return ft.TextField(label=label, hint_text=hint, multiline=True, min_lines=2, max_lines=5,
            text_size=13, color=ft.Colors.ON_SURFACE,
            label_style=ft.TextStyle(size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            hint_style=ft.TextStyle(size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            on_change=callback, on_submit=lambda e: self.sync())

    def _page(self):
        try: return self.page
        except RuntimeError: return None

    @property
    def source(self):
        # Also handle programmatic edits, imports and tests before on_change.
        if (self.final_alg.value or '') != self._final_snapshot: return self.final_alg.value or ''
        if (self.commutator.value or '') != self._comm_snapshot: return self.commutator.value or ''
        return self._source

    def _snapshots(self):
        self._comm_snapshot = self.commutator.value or ''
        self._final_snapshot = self.final_alg.value or ''

    def cancel_pending(self):
        self._revision += 1
        self.pending = False

    def _publish(self, notify=True):
        if notify and self.on_result is not None: self.on_result(self)
        if self._page() is not None: self.update()

    def load(self, source, *, notify=False):
        self.cancel_pending()
        self._needs_reverse = False
        self._source = source or ''
        self.algorithm = None
        self.commutator.error_text = self.final_alg.error_text = None
        self.commutator.value = self.final_alg.value = ''
        if not self._source.strip():
            self.status.value = 'Paste in either field; the other updates automatically.'
        else:
            try:
                self.algorithm = parse_algorithm(self._source)
                self.final_alg.value = simplified_algorithm(self.algorithm).expanded
                self.last_input = 'commutator' if has_commutator_structure(self._source) else 'final'
                if self.last_input == 'commutator':
                    self.commutator.value = self._source
                    self._set_status(True)
                else:
                    result = find_commutator(self._source)
                    self.commutator.value = result.expression if result is not None else ''
                    self._set_status(result is not None)
            except ValueError as ex:
                self.final_alg.value = self._source
                self.final_alg.error_text = str(ex)
                self.status.value = 'Edit the algorithm to preview it.'
        self._snapshots()
        self._publish(notify)

    def _set_status(self, found):
        count = len(simplified_algorithm(self.algorithm).moves)
        self.status.value = f'{count} moves' + (' · fields linked' if found else ' · no short commutator found; final alg is usable.')

    def _input(self, direction, source, *, debounce=True, notify=True):
        self.cancel_pending()
        self._needs_reverse = False
        self.last_input, self._source, self.algorithm = direction, source, None
        self.commutator.error_text = self.final_alg.error_text = None
        target = self.commutator if direction == 'commutator' else self.final_alg
        output = self.final_alg if direction == 'commutator' else self.commutator
        target.value, output.value = source, ''
        try:
            if not source.strip():
                self.status.value = 'Paste in either field; the other updates automatically.'
            else:
                algorithm = parse_algorithm(source)
                if direction == 'commutator' and not has_commutator_structure(source):
                    raise ValueError('Use [A, B] or [setup: [A, B]], or put plain moves in Final alg.')
                self.algorithm = algorithm
                if direction == 'commutator':
                    output.value = simplified_algorithm(algorithm).expanded
                    self._set_status(True)
                elif debounce and self._page() is not None:
                    self.pending = True
                    self._needs_reverse = True
                    self.status.value = 'Finding commutator…'
                else:
                    result = find_commutator(source)
                    output.value = result.expression if result is not None else ''
                    self._set_status(result is not None)
        except ValueError as ex:
            target.error_text = str(ex)
            self.status.value = 'Finish the notation to preview it.'
        self._snapshots()
        self._publish(notify)
        if self.pending:
            self._page().run_task(self._find_later, self._revision, source)

    async def _find_later(self, revision, source):
        await asyncio.sleep(.25)
        if revision != self._revision or source != self._source: return
        result = find_commutator(source)
        if revision != self._revision or source != self._source: return
        self.pending = False
        self._needs_reverse = False
        self.commutator.value = result.expression if result is not None else ''
        self._set_status(result is not None)
        self._snapshots()
        self._publish()

    def sync(self, *, notify=True):
        if (self.final_alg.value or '') != self._final_snapshot:
            self._input('final', self.final_alg.value or '', debounce=False, notify=notify)
        elif (self.commutator.value or '') != self._comm_snapshot:
            self._input('commutator', self.commutator.value or '', debounce=False, notify=notify)
        elif self.pending or self._needs_reverse:
            self._input(self.last_input, self._source, debounce=False, notify=notify)
        return self.algorithm
