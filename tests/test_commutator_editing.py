"""Real editing sequences, caret offsets, conversion and non-destructive save behavior."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
import pytest

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


def same_execution(converter, notation):
    assert converter.algorithm is not None
    expected = algorithm_states(parse_algorithm(notation))[-1]
    assert algorithm_states(converter.algorithm)[-1] == expected
    assert algorithm_states(parse_algorithm(converter.final_alg.value))[-1] == expected


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


def test_cursor_stays_in_the_new_inner_pair_and_can_over_type_both_existing_closers():
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
    assert typist.field.value == original and typist.caret == len(original)
    typist.insert("'")
    assert typist.field.value == original + "'"
    same_execution(typist.converter, original + "'")


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
