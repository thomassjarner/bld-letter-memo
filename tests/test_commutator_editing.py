"""Real editing sequences, caret offsets, conversion and non-destructive save behavior."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
import msgpack
import pytest
from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import configure_encode_object_for_msgpack
from flet.utils.object_model import patch_dataclass

from core.algorithms import algorithm_states, parse_algorithm
from test_case_library import open_library
from test_navigation import no_client_mount
from ui.commutator_editing import CommutatorEditor, index_to_utf16, utf16_to_index
from ui.components.algorithm_converter import AlgorithmConverter


class Typist:
    """Model the pinned client's selection-property update before on_change."""
    def __init__(self, converter=None):
        self.converter = converter or AlgorithmConverter()
        self.field = self.converter.commutator
        self.select(1)

    def select(self, start, end=None):
        end = start if end is None else end
        self.field.selection = ft.TextSelection(index_to_utf16(self.field.value, start),
                                               index_to_utf16(self.field.value, end))

    @property
    def caret(self):
        return utf16_to_index(self.field.value, self.field.selection.extent_offset)

    def insert(self, text):
        value = self.field.value
        a = utf16_to_index(value, self.field.selection.base_offset)
        b = utf16_to_index(value, self.field.selection.extent_offset)
        a, b = min(a, b), max(a, b)
        raw = value[:a] + text + value[b:]
        self.field.value = raw
        self.field.selection = ft.TextSelection(index_to_utf16(raw, a + len(text)),
                                               index_to_utf16(raw, a + len(text)))
        self.field.on_selection_change(SimpleNamespace(selection=self.field.selection))
        self.field.on_change(SimpleNamespace(control=self.field, data=raw))

    def type(self, text):
        for char in text:
            self.insert(char)

    def backspace(self):
        point = self.caret
        self.select(max(0, point - 1), point)
        self.insert('')

    def delete(self):
        point = self.caret
        self.select(point, min(len(self.field.value), point + 1))
        self.insert('')


class ClientTypist:
    """Model real property patches and the pinned client's controller rebuild.

    A formatted value resets the controller to the end, whose listener changes
    the client's selection property before the build reads it. Feed that event
    back, rather than trusting the Python field's intended selection alone.
    """
    def __init__(self, converter=None):
        self.converter = converter or AlgorithmConverter()
        self.field = self.converter.commutator
        self.converter._page = Mock(return_value=SimpleNamespace(run_task=Mock()))
        self.converter.update = Mock()
        self.field.update = Mock()
        self.encoder = configure_encode_object_for_msgpack(ft.Control)
        self.client = msgpack.unpackb(msgpack.packb(self.field, default=self.encoder), raw=False)
        self.text = self.field.value
        self.offset = 1
        self._delta()  # Clear initial configuration's dirty properties.

    def _delta(self):
        delta = ObjectPatch.from_diff(self.field, self.field, control_cls=BaseControl)[0]
        return msgpack.unpackb(msgpack.packb(delta.patch, default=self.encoder), raw=False)

    def _event(self, point):
        selection = {'base_offset': point, 'extent_offset': point}
        patch_dataclass(self.field, {'selection': selection})
        self.field.on_selection_change(SimpleNamespace(selection=ft.TextSelection(point, point), selected_text=''))

    def _apply(self, operations):
        for op in operations:
            path = op['path']; parent = self.client
            for key in path[:-1]:
                parent = parent.setdefault(key, {})
            if op['op'] == 'remove': parent.pop(path[-1], None)
            else: parent[path[-1]] = op['value']
        changed = self.client['value'] != self.text
        if changed:
            self.text = self.client['value']
            self.offset = index_to_utf16(self.text, len(self.text))
            self.client['selection'] = {'base_offset': self.offset, 'extent_offset': self.offset}
            if self.acknowledge:
                self._event(self.offset)  # The controller listener during build.
        selected = self.client.get('selection')
        if selected is not None and selected['extent_offset'] != self.offset:
            self.offset = selected['extent_offset']
            self._event(self.offset)

    def insert(self, value, *, acknowledge=True):
        self.acknowledge = acknowledge
        index = utf16_to_index(self.text, self.offset)
        raw = self.text[:index] + value + self.text[index:]
        self.offset = index_to_utf16(raw, index + len(value))
        self.text = raw
        self.client['value'] = raw
        self.client['selection'] = {'base_offset': self.offset, 'extent_offset': self.offset}
        self._event(self.offset)  # Selection event precedes the value event.
        patch_dataclass(self.field, {'value': raw})
        self.field.on_change(SimpleNamespace(data=raw, control=self.field))
        for _ in range(8):
            operations = self._delta()
            if not operations: break
            self._apply(operations)
        else: raise AssertionError('Caret update did not settle')

    def type(self, value):
        for char in value: self.insert(char)

    @property
    def caret(self):
        return utf16_to_index(self.text, self.offset)


def same_execution(converter, notation):
    assert converter.algorithm is not None
    expected = algorithm_states(parse_algorithm(notation))[-1]
    assert algorithm_states(converter.algorithm)[-1] == expected
    assert algorithm_states(parse_algorithm(converter.final_alg.value or "R R'"))[-1] == expected


def test_empty_frame_is_visible_and_focus_is_inside_it_but_it_is_never_an_algorithm():
    converter = AlgorithmConverter()
    assert converter.commutator.value == '[]' and converter.source == ''
    assert 'Auto brackets' in converter.commutator.helper
    assert converter.algorithm is None and converter.final_alg.value == ''
    converter.commutator.on_focus(None)
    assert converter.commutator.selection == ft.TextSelection(1, 1)
    assert converter.sync() is None and converter.source == ''


@pytest.mark.parametrize('typed,expected', [
    ('R,U', '[R,U]'),
    ('[R,U]', '[R,U]'),
    ("R:U,R' D R", "[R:[U,R' D R]]"),
    ("[R:[U,R' D R]]", "[R:[U,R' D R]]"),
    ('R:U:F,D', '[R:[U:[F,D]]]'),
    ('[[R,U],D]', '[[R,U],D]'),
    ('(R U)2,D', '[(R U)2,D]'),
])
def test_typing_bodies_or_explicit_notation_needs_no_duplicate_closing_brackets(typed, expected):
    typist = Typist()
    typist.type(typed)
    assert typist.field.value == expected
    assert not typist.field.error_text and not typist.converter.incomplete
    same_execution(typist.converter, expected)


@pytest.mark.parametrize('paste', ['[R,U]', "f:[U2,R' D' R]", '[R,U] [F,D]', '[Fw: [R2,E]]'])
@pytest.mark.parametrize('replace_all', [False, True])
def test_complete_pastes_into_the_placeholder_preserve_notation_without_extra_outer_brackets(paste, replace_all):
    typist = Typist()
    if replace_all: typist.select(0, len(typist.field.value))
    typist.insert(paste)
    assert typist.field.value == paste and typist.converter.source == paste
    same_execution(typist.converter, paste)


def test_cursor_stays_in_the_new_inner_pair_and_cannot_step_outside_the_root_pair():
    typist = Typist()
    typist.type('R:U,')
    assert typist.field.value == '[R:[U,]]' and typist.caret == 6
    typist.type("R' D R")
    point = typist.caret
    assert typist.field.value[point:point + 2] == ']]'
    original = typist.field.value
    typist.insert(']')
    assert typist.field.value == original and typist.caret == point + 1
    typist.insert(']')
    assert typist.field.value == original and typist.caret == len(original) - 1
    same_execution(typist.converter, original)


@pytest.mark.parametrize('suffix', ['U,D', '[U,D]', "U,R' D R", "[U,R' D R]"])
def test_colon_opens_an_inner_pair_immediately_and_accepts_the_interchange_after_a_comma(suffix):
    typist = Typist();typist.type('R:')
    assert typist.field.value == '[R:[]]' and typist.caret == 4
    typist.type(suffix)
    expected = '[R:[' + suffix.strip('[]') + ']]'
    assert typist.field.value == expected
    assert typist.caret <= len(expected) - 1
    same_execution(typist.converter, expected)


@pytest.mark.parametrize('body', ['R,U', 'R:U,D', "R:[U,R' D R]", 'R:U:F,D', '(R U)2,D', 'R: [U,F]'])
def test_native_round_trip_keeps_typing_inside_every_generated_pair(body):
    typist = ClientTypist();typist.type(body)
    expected = {'R:U,D': '[R:[U,D]]', "R:[U,R' D R]": "[R:[U,R' D R]]",
                'R:U:F,D': '[R:[U:[F,D]]]', 'R: [U,F]': '[R:[ U,F]]'}.get(body, '[' + body + ']')
    assert typist.text == expected
    assert typist.caret < len(typist.text)
    same_execution(typist.converter, expected)


def test_native_round_trip_observes_the_cursor_at_the_colon_and_the_comma_not_just_the_final_algorithm():
    typist = ClientTypist();typist.type('R:')
    assert typist.text == '[R:[]]' and typist.caret == 4
    typist.type('U,')
    assert typist.text == '[R:[U,]]' and typist.caret == 6
    typist.type('D')
    assert typist.text == '[R:[U,D]]' and typist.caret == 7


def test_colon_space_and_a_habitual_opening_bracket_reuse_the_same_inner_pair():
    typist = Typist();typist.type('R: [U,F]')
    assert typist.field.value == '[R:[ U,F]]'
    same_execution(typist.converter, '[R:[U,F]]')


def test_a_queued_key_before_the_formatted_caret_reply_still_goes_inside_the_new_pair():
    typist = ClientTypist();typist.type('R');typist.insert(':', acknowledge=False)
    assert typist.text == '[R:[]]' and typist.caret == len(typist.text)
    assert typist.converter._caret_request is not None
    typist.insert('U')
    assert typist.text == '[R:[U]]' and typist.caret == 5
    typist.type(",R' D R")
    same_execution(typist.converter, "[R:[U,R' D R]]")


def test_a_key_already_queued_outside_the_frame_before_the_caret_reply_is_not_misplaced():
    typist = ClientTypist();typist.type('R:')
    # The value acknowledgment arrived, but this key was already entered at
    # the temporary end position before the caret-only reply reached the UI.
    typist.offset = index_to_utf16(typist.text, len(typist.text))
    typist.insert('U')
    assert typist.text == '[R:[U]]' and typist.caret == 5


def test_immediately_typing_after_clear_or_focus_cannot_put_the_first_move_after_the_comma():
    converter = AlgorithmConverter();converter.load('[F,D]')
    typist = Typist(converter);typist.select(0,len(typist.field.value));typist.insert('')
    converter.commutator.on_focus(None)
    native = ClientTypist(converter);native.type("R' B' R:R D R',U'")
    expected = "[R' B' R:[R D R',U']]"
    assert native.text == expected
    same_execution(converter, expected)


@pytest.mark.parametrize('point,inserted,expected', [(0, 'F ', '[F R,U]'), (5, ' D', '[R,U D]')])
def test_typing_before_or_after_the_outer_frame_is_redirected_inside(point, inserted, expected):
    converter = AlgorithmConverter();converter.load('[R,U]')
    typist = Typist(converter);typist.select(point);typist.insert(inserted)
    assert typist.field.value == expected
    assert 1 <= typist.caret <= len(expected) - 1
    same_execution(converter, expected)


@pytest.mark.parametrize('point,expected', [(0, 1), (5, 4)])
def test_home_end_and_click_selection_cannot_leave_the_root_pair(point, expected):
    converter = AlgorithmConverter();converter.load('[R,U]')
    converter.commutator.selection = ft.TextSelection(point, point)
    converter.commutator.on_selection_change(SimpleNamespace(selection=converter.commutator.selection))
    assert converter.commutator.selection == ft.TextSelection(expected, expected)
    assert converter.source == '[R,U]' and converter.final_alg.value == "R U R' U'"


def test_separator_caret_can_be_recovered_without_a_selection_property():
    editor = CommutatorEditor();editor.reset('[R]')
    result = editor.edit('[R:]')
    assert result.text == '[R:[]]' and result.selection == (4, 4)
    editor.reset('[R,U]')
    result = editor.edit('[R,UD]')
    assert result.text == '[R,UD]'  # Never invent a move or erase one.


def test_deleting_empty_pairs_or_the_base_bracket_never_deletes_move_text():
    typist = Typist()
    typist.backspace()
    assert typist.field.value == '[]' and typist.caret == 1
    typist.delete()
    assert typist.field.value == '[]' and typist.caret == 1
    typist.type('R:')
    typist.insert('[')
    assert typist.field.value == '[R:[]]'
    typist.backspace()
    assert typist.field.value == '[R:]' and typist.caret == 3
    typist.type("U,R' D R")
    assert typist.field.value == "[R:[U,R' D R]]"
    original = typist.field.value
    typist.select(1)
    typist.backspace()
    assert typist.field.value == original and typist.caret == 1
    typist.select(0, len(original))
    typist.insert('')
    assert typist.field.value == '[]' and not typist.converter.source
    assert typist.converter.algorithm is None and not typist.converter.final_alg.value


def test_middle_selection_replacement_and_parentheses_keep_the_native_caret():
    converter = AlgorithmConverter(); converter.load('[R,U]')
    typist = Typist(converter)
    typist.select(1, 2); typist.insert('Fw2')
    assert typist.field.value == '[Fw2,U]' and typist.caret == 4
    same_execution(converter, '[Fw2,U]')
    typist.select(1); typist.insert('(')
    assert typist.field.value == '[()Fw2,U]' and typist.caret == 2
    typist.type('R U')
    typist.insert(')')
    assert typist.field.value == '[(R U)Fw2,U]' and typist.caret == 6
    same_execution(converter, '[(R U)Fw2,U]')


def test_comments_and_utf16_caret_offsets_do_not_turn_comment_brackets_into_notation():
    typist = Typist()
    typist.select(0, 2)
    raw = 'R,U // 🧠 ['
    typist.insert(raw)
    assert typist.field.value == '[' + raw + '\n]'
    assert typist.field.selection.extent_offset == len(('[' + raw).encode('utf-16-le')) // 2
    same_execution(typist.converter, '[R,U]')


def test_removing_only_generated_inner_brackets_is_not_immediately_re_nested():
    editor = CommutatorEditor()
    assert editor.edit('R: U,D').text == '[R: [U,D]]'
    result = editor.edit('[R: U,D]')
    assert result.text == '[R: U,D]'
    assert editor.edit('[R: U, F]').text == '[R: [U, F]]'


@pytest.mark.parametrize('text', ['R +,U', 'R,U,D', '[R,U)'])
def test_invalid_or_ambiguous_notation_is_not_silently_turned_into_another_algorithm(text):
    typist = Typist();typist.select(0, 2);typist.insert(text)
    assert typist.converter.algorithm is None and typist.field.error_text
    assert not typist.converter.final_alg.value
    assert all(char in typist.field.value for char in text)


def test_raw_final_moves_remain_authoritative_when_no_commutator_is_found():
    converter = AlgorithmConverter()
    converter.final_alg.value = 'R';converter.final_alg.on_change(None)
    assert converter.commutator.value == '[]' and converter.source == 'R'
    converter.commutator.on_focus(None)
    assert converter.source == 'R' and converter.sync().moves == ('R',)
    assert converter.final_alg.value == 'R' and 'usable' in converter.status.value


def test_reverse_search_and_focus_cannot_overwrite_a_new_bracket_assisted_draft():
    converter = AlgorithmConverter();page = SimpleNamespace(run_task=Mock())
    with patch.object(converter, '_page', return_value=page), patch.object(converter, 'update'):
        converter.final_alg.value = "R U R' U'";converter.final_alg.on_change(None)
        callback, revision, source = page.run_task.call_args.args
        assert converter.pending and converter.commutator.value == '[]'
        typist = Typist(converter);typist.type('F,D')
        with patch('ui.components.algorithm_converter.asyncio.sleep', new=AsyncMock()):
            asyncio.run(callback(revision, source))
        assert converter.source == '[F,D]' and converter.final_alg.value == "F D F' D'"


@pytest.mark.parametrize('mode', ['library', 'explorer'])
def test_bracket_assistance_and_placeholder_never_write_saved_data_without_explicit_save(mode):
    _, repo, _, view = open_library()
    if mode == 'explorer': view._set_mode('explorer')
    converter = view.case_converter if mode == 'library' else view.playground_converter
    before = deepcopy(repo.data.to_dict())
    typist = Typist(converter);typist.select(0, len(typist.field.value))
    typist.insert('')
    assert converter.commutator.value == '[]' and converter.algorithm is None
    if mode == 'library':
        with patch.object(repo, 'save') as save: view._save_algorithm(False);save.assert_not_called()
    typist.type("R' B' R:R D R',U'")
    assert converter.commutator.value == "[R' B' R:[R D R',U']]"
    assert not converter.commutator.error_text and converter.algorithm is not None
    assert repo.data.to_dict() == before
