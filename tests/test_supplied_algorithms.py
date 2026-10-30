"""Supplied commutators, exact one-move setups and personal replacements."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import patch

import flet as ft
import pytest

from core.algorithms import inverse_moves, normalized_state, parse_algorithm, simplify_moves
from core.corner_algorithm_seeds import SUPPLIED_ALGORITHMS
from core.corner_algorithms import ALL_SUBMISSIONS, QUALITY_NOTICE, SETUP_MOVES, builtin_algorithms, supplied_case_algorithms, generate_algorithm_registry
from core.corner_cases import corner_cases, identify_case
from core.tracer import ScrambleTracer
from data.models import AppData
from test_case_library import open_library
from test_navigation import no_client_mount, text_values, walk
from test_progressive_memo import letter_scheme


def tracing_moves(moves):
    # The algorithm editor supports slices/rotations; the unchanged scramble
    # tracer accepts outer/wide turns. Expand equivalent legal moves for it.
    replacements = {'M': ("L'", 'Lw'), 'E': ("D'", 'Dw'), 'S': ("F'", 'Fw'),
                    'x': ('Rw', "L'"), 'y': ('Uw', "D'"), 'z': ('Fw', "B'")}
    result = ()
    for move in moves:
        base = move.rstrip("2'")
        if base not in replacements:
            result += (move,)
            continue
        turns = replacements[base]
        result += turns * 2 if move.endswith('2') else inverse_moves(turns) if move.endswith("'") else turns
    return result


def test_all_supplied_algorithms_and_verbatim_commutators_solve_their_stated_cycles():
    assert len(SUPPLIED_ALGORITHMS) == 38
    scheme = letter_scheme()
    for position, source, commutator in SUPPLIED_ALGORITHMS:
        buffer, first, second = position.split('-')
        scheme.corners.buffer_piece = scheme.corners.buffer_sticker = buffer
        algorithm = parse_algorithm(source)
        assert normalized_state(algorithm) == normalized_state(parse_algorithm(commutator))
        trace = ScrambleTracer().trace(' '.join(inverse_moves(algorithm.moves)), scheme)
        assert trace.corner_targets == [first, second]
        assert not trace.edge_targets and not trace.edge_orientation and not trace.corner_orientation


def test_every_supplied_or_derived_ufr_alternative_is_verified_by_the_unchanged_tracer():
    catalog = supplied_case_algorithms()
    assert len(catalog) == 378 and sum(map(len, catalog.values())) == 6508
    scheme = letter_scheme()
    scheme.corners.buffer_piece = scheme.corners.buffer_sticker = 'UFR'
    identifiers, positions = set(), set()
    for key, group in catalog.items():
        for candidate in group:
            assert candidate.id not in identifiers
            identifiers.add(candidate.id)
            positions.add(candidate.position)
            algorithm = parse_algorithm(candidate.alg)
            trace = ScrambleTracer().trace(' '.join(tracing_moves(inverse_moves(algorithm.moves))), scheme)
            assert ':'.join(trace.corner_targets) == key
            assert not trace.edge_targets and not trace.edge_orientation and not trace.corner_orientation
            assert not trace.corner_cycle_breaks
    assert positions == {p for p, _, _ in ALL_SUBMISSIONS}


def test_catalog_covers_all_distinct_one_move_cases_including_wide_setups():
    generated = generate_algorithm_registry()
    expected = {(key, simplify_moves(a.moves)) for key, group in generated.items() for a in group}
    actual = {(key, simplify_moves(a.moves)) for key, group in supplied_case_algorithms().items() for a in group}
    assert actual == expected
    assert {(key, a.id, a.alg) for key, group in generated.items() for a in group} == {
        (key, a.id, a.alg) for key in corner_cases() for a in builtin_algorithms(key) if a.origin != 'generated'}
    wide = [a for group in supplied_case_algorithms().values() for a in group if 'w' in a.setup]
    assert len(wide) >= 366 and {'Fw', "Fw'", 'Fw2'} <= {a.setup for a in wide}
    assert all(len(parse_algorithm(a.setup).moves) == 1 for a in wide)


def test_direct_submissions_take_priority_then_one_move_variants_then_fallbacks():
    direct = {':'.join(position.split('-')[1:]): position
              for position, _, _ in ALL_SUBMISSIONS if position.startswith('UFR-')}
    for key in corner_cases():
        group = builtin_algorithms(key)
        assert group[-1].origin == 'generated' and group[-1].alg == corner_cases()[key].starter
        if key in direct:
            assert group[0].origin == 'supplied' and group[0].position == direct[key]
        elif key in supplied_case_algorithms():
            assert group[0].origin == 'one_move'
        else:
            assert len(group) == 1


def test_second_target_filter_is_optional_independent_and_combines_with_first_target():
    _, repo, _, view = open_library()
    before = deepcopy(repo.data.to_dict())
    assert view.second_target.value == 'all' and len(view.filtered_cases()) == 378
    view.second_target.value = 'LUF'
    view._filter_changed()
    assert len(view.filtered_cases()) == 18 and all(c.second == 'LUF' for c in view.filtered_cases())
    view.first_target.value = 'UBL'
    view._filter_changed()
    assert [c.id for c in view.filtered_cases()] == ['UBL:LUF']
    view.first_target.value = 'UFL'  # same physical piece as LUF
    view._filter_changed()
    assert not view.filtered_cases()
    assert 'No cases match these filters.' in text_values(view)
    view.first_target.value = view.second_target.value = 'all'
    view.subset.value = 'D/D'
    view.subset.on_select(SimpleNamespace(control=view.subset))
    assert view.first_target.value == view.second_target.value == 'all'
    assert len(view.filtered_cases()) == 108
    assert repo.data.to_dict() == before


def test_supplied_defaults_are_editable_with_a_single_save_and_use_action_and_preserve_other_data():
    _, repo, _, view = open_library()
    view.select_case('UBL:LUF')
    before = deepcopy(repo.data.to_dict())
    assert view._variant()[1] == builtin_algorithms('UBL:LUF')[0].alg
    assert QUALITY_NOTICE in text_values(view)
    # Paste the exact user-provided shorthand, with lowercase wide turns.
    source = "f:[U2,R' D' R]"
    view.algorithm_field.value, view.name_field.value = source, 'My favorite'
    button = next(c for c in walk(view) if isinstance(c, ft.FilledButton) and c.content == 'Save & use my alg')
    button.on_click(None)
    record = view.record()
    assert len(record.algorithms) == 1
    personal = record.algorithms[0]
    assert personal.alg == source and personal.id == record.preferred_algorithm == view.selected_algorithm
    assert view._variant() == ('My favorite', source)
    view.algorithm_field.value = source + " R R'"
    button = next(c for c in walk(view) if isinstance(c, ft.FilledButton) and c.content == 'Save changes & use')
    button.on_click(None)
    assert len(record.algorithms) == 1 and record.algorithms[0].id == personal.id
    assert record.algorithms[0].alg == source + " R R'"
    for name, value in before.items():
        if name != 'corner_case_library': assert repo.data.to_dict()[name] == value
    old = deepcopy(repo.data.to_dict())
    view.algorithm_field.value = 'R'
    with patch.object(repo, 'save') as save:
        next(c for c in walk(view) if isinstance(c, ft.FilledButton) and c.content == 'Save changes & use').on_click(None)
        save.assert_not_called()
    assert repo.data.to_dict() == old and view.error.value and not view.notice.value


def test_wide_setup_preference_survives_backup_reload_without_inserting_builtins_into_personal_data():
    _, repo, _, view = open_library()
    key, wide = next((key, a) for key, group in supplied_case_algorithms().items()
                     for a in group if a.setup == "Fw'")
    view.select_case(key)
    view.variant_picker.value = wide.id
    view._choose_variant(SimpleNamespace(control=view.variant_picker))
    next(c for c in walk(view) if isinstance(c, ft.TextButton) and c.content == 'Use selected alg').on_click(None)
    assert view.record().preferred_algorithm == wide.id and not view.record().algorithms
    restored = AppData.from_dict(json.loads(json.dumps(repo.data.to_dict())))
    view.state.data = restored
    view.select_case(key)
    assert view.selected_algorithm == wide.id and view._variant()[1] == wide.alg
    supplied_case_algorithms.cache_clear()
    assert any(a.id == wide.id for a in supplied_case_algorithms()[key])
    # IDs from another case and unknown IDs cannot be set as a preference.
    other_key = next(k for k in supplied_case_algorithms() if k != key)
    before = deepcopy(restored.to_dict())
    with patch.object(repo, 'save') as save:
        with pytest.raises(ValueError): view.state.update_corner_case(other_key, preferred=wide.id)
        with pytest.raises(ValueError): view.state.update_corner_case(key, preferred='builtin:missing')
        save.assert_not_called()
    assert restored.to_dict() == before


def test_saved_personal_preference_stays_selected_over_new_supplied_defaults_and_can_be_copied():
    _, repo, _, view = open_library()
    key = 'UBL:LUF'
    original = corner_cases()[key].starter
    personal_id = view.state.save_case_algorithm(key, 'Existing personal alg', original)
    view.state.update_corner_case(key, status='learned', notes='Keep this', favorite=True)
    before = deepcopy(repo.data.to_dict())
    view.select_case(key)
    view.refresh()
    assert view.selected_algorithm == personal_id and view._variant()[1] == original
    assert repo.data.to_dict() == before
    next(c for c in walk(view) if isinstance(c, ft.TextButton) and c.content == 'Save as another alternative').on_click(None)
    assert len(view.record().algorithms) == 2 and view.selected_algorithm != personal_id
    assert view.record().notes == 'Keep this' and view.record().status == 'learned' and view.record().favorite
    view._set_mode('overview')
    assert QUALITY_NOTICE in text_values(view)


@pytest.mark.parametrize('source,canonical', [
    ("f:[U2,R' D' R]", "[Fw: [U2,R' D' R]]"),
    ("Fw':[U2,R' D' R]", "[Fw': [U2,R' D' R]]"),
    ("U' D':[R D' R',U2]", "[U' D': [R D' R',U2]]"),
    ("[Fw: f:[U2,R' D' R]]", "[Fw: [Fw: [U2,R' D' R]]]"),
])
def test_setup_shorthand_keeps_the_expected_move_expansion_and_stage_playback(source, canonical):
    parsed, expected = parse_algorithm(source), parse_algorithm(canonical)
    assert parsed.moves == expected.moves and parsed.stages == expected.stages
    assert parsed.source == source


@pytest.mark.parametrize('source', [':R', 'R:', '(R)0:U', 'R:' * 18 + 'U'])
def test_setup_shorthand_rejects_empty_or_excessively_nested_input(source):
    with pytest.raises(ValueError): parse_algorithm(source)
