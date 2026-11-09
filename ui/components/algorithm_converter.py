"""Two linked editable fields: commutator notation and final moves."""
import asyncio

import flet as ft

from core.algorithms import parse_algorithm, simplified_algorithm
from core.commutator_finder import find_commutator, has_commutator_structure
from ui.commutator_editing import (CommutatorEditor, contains_square_bracket, empty_commutator,
                                   index_to_utf16, utf16_to_index)


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
        self.incomplete = False
        self._brackets = CommutatorEditor()
        self.last_input = 'final'
        self.commutator = self._field('Commutator', '[A, B] or [setup: [A, B]]',
            lambda e: self._input('commutator', self.commutator.value or ''))
        self.commutator.value = '[]'
        self.commutator.on_focus = self._commutator_focus
        # The pinned Flet client reports its post-edit caret before on_change
        # only when this listener is registered. No async caret task is needed.
        self.commutator.on_selection_change = lambda e: None
        self.commutator.helper = 'Auto brackets · type A, B or setup: A, B'
        self.commutator.helper_style = ft.TextStyle(size=11, color=ft.Colors.ON_SURFACE_VARIANT)
        self.commutator.helper_max_lines = 2
        self.final_alg = self._field('Final alg', "R U R' U' · wide/slice moves also work",
            lambda e: self._input('final', self.final_alg.value or ''))
        self.status = ft.Text('Paste in either field; the other updates automatically.', size=11,
                              color=ft.Colors.ON_SURFACE_VARIANT)
        self.controls = [self.commutator, self.final_alg, self.status]
        self._snapshots()

    def _field(self, label, hint, callback):
        return ft.TextField(label=label, hint_text=hint, multiline=True, min_lines=2, max_lines=5,
            text_size=13, color=ft.Colors.ON_SURFACE,
            label_style=ft.TextStyle(size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            hint_style=ft.TextStyle(size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            autocorrect=False, enable_suggestions=False,
            on_change=callback, on_submit=lambda e: self.sync())

    def _page(self):
        try: return self.page
        except RuntimeError: return None

    @property
    def source(self):
        # Also handle programmatic edits, imports and tests before on_change.
        if (self.final_alg.value or '') != self._final_snapshot: return self.final_alg.value or ''
        if (self.commutator.value or '') != self._comm_snapshot:
            return '' if empty_commutator(self.commutator.value) else self.commutator.value or ''
        return self._source

    def _commutator_focus(self, e=None):
        if (self.commutator.value or '').strip() == '[]':
            self.commutator.selection = ft.TextSelection(1, 1)
            if self._page() is not None: self.commutator.update()

    def _set_commutator(self, source):
        display = source or '[]'
        if source and not contains_square_bracket(source):
            display = CommutatorEditor().edit(source).text
        self.commutator.value = display
        self.commutator.selection = None
        self._brackets.reset(display)

    def _edit_commutator(self, source):
        native = self.commutator.selection
        selection = None
        if native is not None:
            start = utf16_to_index(source, native.base_offset)
            end = utf16_to_index(source, native.extent_offset)
            if start is not None and end is not None: selection = start, end
        result = self._brackets.edit(source, selection)
        self.commutator.value = result.text
        if result.selection is not None:
            start, end = result.selection
            self.commutator.selection = ft.TextSelection(
                index_to_utf16(result.text, start), index_to_utf16(result.text, end))
        return '' if empty_commutator(result.text) else result.text

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
        self.incomplete = False
        self._source = source or ''
        self.algorithm = None
        self.commutator.error_text = self.final_alg.error_text = None
        self._set_commutator('')
        self.final_alg.value = ''
        if not self._source.strip():
            self.status.value = 'Paste in either field; the other updates automatically.'
        else:
            try:
                self.algorithm = parse_algorithm(self._source)
                self.final_alg.value = simplified_algorithm(self.algorithm).expanded
                self.last_input = 'commutator' if contains_square_bracket(self._source) or has_commutator_structure(self._source) else 'final'
                if self.last_input == 'commutator':
                    self._set_commutator(self._source)
                    self._set_status(True)
                else:
                    result = find_commutator(self._source)
                    self._set_commutator(result.expression if result is not None else '')
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
        self.incomplete = False
        self.last_input, self.algorithm = direction, None
        self.commutator.error_text = self.final_alg.error_text = None
        target = self.commutator if direction == 'commutator' else self.final_alg
        output = self.final_alg if direction == 'commutator' else self.commutator
        if direction == 'commutator':
            source = self._edit_commutator(source)
            self.final_alg.value = ''
        else:
            target.value = source
            self._set_commutator('')
        self._source = source
        try:
            if not source.strip():
                self.incomplete = direction == 'commutator'
                self.status.value = 'Paste in either field; the other updates automatically.'
            else:
                algorithm = parse_algorithm(source)
                if direction == 'commutator' and not contains_square_bracket(source) and not has_commutator_structure(source):
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
                    self._set_commutator(result.expression if result is not None else '')
                    self._set_status(result is not None)
        except ValueError as ex:
            self.incomplete = direction == 'commutator' and str(ex) in (
                'Both parts of a commutator/setup must contain moves.',
                'Both parts of a setup must contain moves.',
                'Use [A, B] or [setup: algorithm].', 'Close every algorithm group.')
            target.error_text = None if self.incomplete else str(ex)
            self.status.value = ('Finish both parts using , or : inside the brackets.'
                                 if self.incomplete else 'Finish the notation to preview it.')
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
        self._set_commutator(result.expression if result is not None else '')
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
