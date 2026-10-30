"""Attached algorithm coverage, recovered notation and random-to-editor flow."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import flet as ft
import pytest

from core.algorithms import algorithm_states, parse_algorithm
from core.commutator_finder import execution_signature, find_commutator
from core.corner_algorithm_additions import ADDITIONAL_ALGORITHMS
from core.corner_algorithms import ALL_SUBMISSIONS, builtin_algorithms, display_builtin_algorithms, supplied_case_algorithms
from core.tracer import ScrambleTracer
from data.models import AppData, CornerCaseRecord
from test_case_library import open_library
from test_navigation import no_client_mount, walk
from test_progressive_memo import letter_scheme
from test_supplied_algorithms import tracing_moves


def test_all_332_attached_algorithms_trace_to_their_stated_targets_and_have_recoverable_notation():
    assert len(ADDITIONAL_ALGORITHMS) == 332 and len(ALL_SUBMISSIONS) == 349
    scheme = letter_scheme()
    for position, source, commutator in ADDITIONAL_ALGORITHMS:
        buffer, first, second = position.split('-')
        scheme.corners.buffer_piece = scheme.corners.buffer_sticker = buffer
        original = parse_algorithm(source)
        from core.algorithms import inverse_moves
        converted = tracing_moves(original.moves)
        assert algorithm_states(parse_algorithm(' '.join(converted)))[-1] == algorithm_states(original)[-1]
        trace = ScrambleTracer().trace(' '.join(tracing_moves(inverse_moves(original.moves))), scheme)
        assert trace.corner_targets == [first, second]
        assert not trace.edge_targets and not trace.edge_orientation and not trace.corner_orientation
        result = find_commutator(source)
        assert result is not None, position
        recovered = parse_algorithm(result.expression)
        assert execution_signature(recovered.moves) == execution_signature(original.moves)
        assert algorithm_states(recovered)[-1] == algorithm_states(original)[-1]
        if commutator != 'Not found.':
            assert algorithm_states(parse_algorithm(commutator))[-1] == algorithm_states(original)[-1]


def test_all_765_earlier_builtin_ids_sources_and_explicit_preferences_remain_usable():
    path = Path(__file__).parent / 'fixtures' / 'legacy_case_algorithms_230.json'
    old = json.loads(path.read_text())
    assert len(old) == 765
    assert sha256(json.dumps(sorted(old), ensure_ascii=False).encode()).hexdigest() == 'e19bfc54613ed590b820973067300cab4976d586f90d7e2ab5dc26dfcff54803'
    for key, identifier, source in old:
        assert any(a.id == identifier and a.alg == source for a in builtin_algorithms(key))
    _, repo, _, view = open_library()
    key, identifier, source = next((key, identifier, source) for key, identifier, source in old
        if identifier not in {a.id for a in display_builtin_algorithms(key)})
    repo.data.corner_case_library[key] = CornerCaseRecord(preferred_algorithm=identifier, notes='Keep preference')
    view.select_case(key)
    assert view.selected_algorithm == identifier and view._variant()[1] == source
    assert identifier in {o.key for o in view.variant_picker.options}
    view.state.update_corner_case(key, preferred=identifier)
    restored = AppData.from_dict(json.loads(json.dumps(repo.data.to_dict())))
    assert restored.corner_case_library[key].preferred_algorithm == identifier


@pytest.mark.parametrize('notation', ['[M,U2]', '[Fw: [R2,E]]', "[z R D': [Rw2,S]]", '[R,U]', '[U2: [F,D2]]'])
def test_structural_search_works_for_unknown_moves_and_rotations_without_substituting_another_case_alg(notation):
    source = parse_algorithm(notation).expanded
    result = find_commutator(source)
    assert result is not None
    parsed = parse_algorithm(result.expression)
    assert algorithm_states(parsed)[-1] == algorithm_states(parse_algorithm(source))[-1]
    assert execution_signature(parsed.moves) == execution_signature(parse_algorithm(source).moves)


def test_not_found_rows_support_rotationally_equivalent_wide_notation():
    rows = [(p, a) for p, a, c in ADDITIONAL_ALGORITHMS if c == 'Not found.']
    assert len(rows) == 2
    for _, source in rows:
        assert find_commutator(source) is not None


@pytest.mark.parametrize('source', ['R', 'R U F', "R R'"])
def test_unsuitable_or_identity_sequences_do_not_get_an_invented_commutator(source):
    assert find_commutator(source) is None


def test_search_budget_and_parser_limits_remain_bounded():
    source = parse_algorithm('[M,U2]').expanded
    assert find_commutator(source, max_checks=0) is None
    assert find_commutator(source, max_seconds=0) is None
    for invalid in ('', 'R + U', '(R U)9999'):
        with pytest.raises(ValueError): find_commutator(invalid)


@pytest.mark.parametrize('mode', ['library', 'explorer'])
def test_find_then_use_notation_updates_only_the_editor_and_requires_an_explicit_save(mode):
    _, repo, _, view = open_library()
    if mode == 'library':
        view.select_case('UBL:LUF', edit=True)
        source = "F U2 R' D' R U2 R' D R F'"
        target = view.algorithm_field
    else:
        view._set_mode('explorer')
        source = "M U2 M' U2"
        target = view.explorer_field
    before = deepcopy(repo.data.to_dict())
    target.value = source
    next(c for c in walk(view) if isinstance(c, ft.TextButton) and c.content == 'Find commutator').on_click(None)
    assert view.commutator_panel.visible and view.use_commutator.visible
    assert target.value == source and repo.data.to_dict() == before
    expression = view.commutator_text.value
    view.use_commutator.on_click(None)
    assert target.value == expression and not view.error.value
    assert repo.data.to_dict() == before
    if mode == 'library':
        view._save_algorithm(False)
        assert view.record().algorithms[0].alg == expression
        assert view.record().preferred_algorithm == view.selected_algorithm


def test_stale_notation_and_case_switches_cannot_replace_a_new_draft():
    _, repo, _, view = open_library()
    before = deepcopy(repo.data.to_dict())
    view.select_case('UBL:LUF')
    view.algorithm_field.value = "F U2 R' D' R U2 R' D R F'"
    view._find_commutator()
    view.algorithm_field.value = 'R U'
    view._use_commutator()
    assert view.algorithm_field.value == 'R U' and not view.commutator_panel.visible
    view._find_commutator()
    assert 'No short commutator' in view.commutator_text.value and not view.use_commutator.visible
    view.select_case('UBL:RDF')
    assert view._derived_for is None and not view.commutator_panel.visible
    assert repo.data.to_dict() == before


@pytest.mark.parametrize('width,height', [(1400, 760), (1000, 430), (366, 570)])
def test_random_matching_case_opens_the_normal_editor_with_visible_moves_and_no_data_changes(width, height):
    _, repo, _, view = open_library()
    before = deepcopy(repo.data.to_dict())
    view.set_viewport(width, height)
    view.subset.value = 'U/D'
    view._filter_changed()
    view._random_case()
    assert view.cases[view.selected_case].subset == 'U/D'
    assert view.viewer.index == 0 and not view.hidden and view.viewer.move_text.visible
    assert view.editor_open and view.editor_tile.expanded and view.editor_tile.visible
    assert view.algorithm_field.visible and view.name_field.value
    assert any(isinstance(c, ft.FilledButton) and c.content == 'Save & use my alg' for c in walk(view.editor_tile))
    assert repo.data.to_dict() == before


def test_random_editor_scroll_and_focus_respect_navigation_cancellation():
    _, _, _, view = open_library()
    view._random_case()
    pane = view.detail_scrolls[-1]
    pane.scroll_to = AsyncMock()
    view.algorithm_field.focus = AsyncMock()
    with patch('flet.controls.base_control.BaseControl.page', property(lambda self: object())):
        asyncio.run(view._reveal_case_editor(view._navigation_token))
        pane.scroll_to.assert_awaited_once_with(scroll_key=view.editor_tile.key, duration=0)
        view.algorithm_field.focus.assert_awaited_once()
        asyncio.run(view._reveal_case_editor(view._navigation_token - 1))
        assert pane.scroll_to.await_count == 1 and view.algorithm_field.focus.await_count == 1


def test_regular_browse_still_starts_with_the_cube_and_a_collapsed_editor():
    _, _, _, view = open_library()
    view._random_case()
    view.select_case('UBL:LUF')
    assert not view.editor_open and not view.editor_tile.expanded
    assert view.viewer.controls[0] is view.viewer.canvas
    assert view.case_canvas_top + view.viewer.canvas.height <= view.body.height
