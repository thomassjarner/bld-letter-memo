"""Complete, reproducible BLDDB replacement, popularity order and saved-data safety."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import flet as ft
import pytest

from core.algorithms import inverse_moves, normalized_state, parse_algorithm, simplified_algorithm
from core.commutator_finder import execution_signature
from core.corner_algorithms import (CATALOG_PATH, blddb_case_algorithms, builtin_algorithms,
    case_source_url, catalog_metadata, display_builtin_algorithms)
from core.corner_cases import corner_cases, identify_case
from core.corner_trainer import make_card
from core.corner_walkthrough import build_corner_plan
from core.legacy_corner_algorithms import builtin_algorithms as legacy_builtin_algorithms
from core.tracer import ScrambleTracer
from data.models import AppData, CaseAlgorithm, CornerCaseRecord
from test_case_library import open_library
from test_navigation import no_client_mount, text_values, walk
from test_progressive_memo import letter_scheme
from test_supplied_algorithms import tracing_moves
from tools.import_blddb_corners import FILES, ROOT, UPSTREAM, build_catalog, render_catalog


def test_all_378_cases_and_2423_variants_are_real_pure_cycles_in_the_unchanged_tracer():
    catalog = blddb_case_algorithms()
    assert set(catalog) == set(corner_cases()) and len(catalog) == 378
    assert sum(map(len, catalog.values())) == 2423
    scheme = letter_scheme()
    scheme.corners.buffer_piece = scheme.corners.buffer_sticker = 'UFR'
    identifiers = set()
    for key, group in catalog.items():
        assert group and all(a.origin == 'blddb' for a in group)
        assert [a.source_count for a in group] == sorted((a.source_count for a in group), reverse=True)
        assert display_builtin_algorithms(key, ('builtin:generated',)) == group
        for candidate in group:
            assert candidate.id not in identifiers
            identifiers.add(candidate.id)
            expected_id = 'builtin:blddb:' + sha256((key + '\n' + candidate.raw_alg).encode()).hexdigest()[:24]
            assert candidate.id == expected_id and candidate.source_count == len(candidate.sources)
            raw = parse_algorithm(candidate.raw_alg)
            actual = parse_algorithm(candidate.alg)
            assert identify_case(raw) == identify_case(actual) == key
            assert execution_signature(raw.moves) == execution_signature(actual.moves)
            assert normalized_state(raw) == normalized_state(actual)
            assert normalized_state(simplified_algorithm(actual)) == normalized_state(actual)
            trace = ScrambleTracer().trace(' '.join(tracing_moves(inverse_moves(raw.moves))), scheme)
            assert ':'.join(trace.corner_targets) == key
            assert not (trace.edge_targets or trace.edge_orientation or trace.corner_orientation or trace.corner_cycle_breaks)


def test_catalog_rebuild_is_exact_and_preserves_pinned_source_hashes_and_license():
    data = build_catalog()
    assert render_catalog(data) == CATALOG_PATH.read_text(encoding='utf-8')
    meta = catalog_metadata()
    assert (meta['cases'], meta['groups'], meta['variants']) == (378, 2252, 2423)
    assert meta['buffer'] == 'UFR' and meta['mode'] == 'manmade'
    assert meta['revision'] == 'f555e56d93b2f6ca503aa32ad0f3bd93a6938ce5'
    assert meta['snapshot_date'] == '2026-11-09'
    assert meta['license'] == 'GPL-3.0-or-later'
    for name in FILES:
        assert sha256((UPSTREAM / name).read_bytes()).hexdigest() == meta['input_sha256'][name]
    assert meta['input_sha256']['public/data/cornerManmade.json'] == '5a6f0938be7331f487d5f7b319b8ef8d6632334fe02f9f17ef1f5a63497acbbe'
    assert 'GNU GENERAL PUBLIC LICENSE' in (UPSTREAM / 'LICENSE').read_text()
    assert (ROOT / 'third_party/blddb/NOTICE.md').is_file()


def test_rank_and_variant_order_match_the_live_ufr_ubl_ubr_page():
    # These counts/moves were independently observed on the live page, not
    # inferred from our compiled catalog. The two 23-source groups retain ties.
    group = builtin_algorithms('UBL:UBR')
    assert [(a.rank, a.source_count) for a in group] == [
        (1, 23), (2, 23), (2, 23), (2, 23), (2, 23), (3, 16),
        (4, 9), (5, 4), (6, 1), (7, 1), (8, 1), (9, 1),
    ]
    assert group[0].raw_alg == "R' B' R2 D R' U' R D' R' U R' B R"
    assert [a.raw_alg for a in group[1:5]] == [
        "l' U R' D2 R U' R' D2 R l",
        "x R' U R' D2 R U' R' D2 R2 x'",
        "l' U R' D2 R U' R' D2 R2 x'",
        "R' F R' B2 R F' R' B2 R2",
    ]
    assert [a.variant for a in group[1:5]] == [1, 2, 3, 4]
    assert all(a.variant_count == 4 for a in group[1:5])
    assert group[0].source_url == 'https://v2.blddb.net/corner?position=UFR-UBL-UBR&mode=manmade'


def test_second_independently_observed_case_uses_44_8_5_1_source_order():
    group = builtin_algorithms('LDB:FDL')
    assert [a.source_count for a in group] == [44, 8, 5, 1]
    assert group[0].raw_alg == "D2 R U R' D' R U' R' D'"


@pytest.mark.parametrize('key', ['UBL:UBR', 'LDB:FDL', 'DFR:RDB', 'RUB:LUF'])
def test_case_picker_contains_only_ranked_blddb_choices_and_personal_alternatives(key):
    _, repo, _, view = open_library()
    personal = CaseAlgorithm('mine', 'Keep my alg', builtin_algorithms(key)[0].raw_alg)
    repo.data.corner_case_library[key] = CornerCaseRecord(
        algorithms=[personal], preferred_algorithm='mine', status='learned', notes='Keep notes', favorite=True)
    before = deepcopy(repo.data.to_dict())
    view.select_case(key)
    assert view.selected_algorithm == 'mine' and view._variant() == ('Keep my alg', personal.alg)
    options = view.variant_picker.options
    assert [o.key for o in options] == ['', *[a.id for a in builtin_algorithms(key)], 'mine']
    assert not any(word in str(o.content) for o in options for word in ('Generated fallback', 'One-move setup', 'Supplied algorithm'))
    source_link = next(c for c in walk(view) if isinstance(c, ft.TextButton) and c.content == 'BLDDB')
    assert source_link.url == case_source_url(key)
    candidate = builtin_algorithms(key)[1]
    view._choose_variant(SimpleNamespace(control=SimpleNamespace(value=candidate.id)))
    assert view.selected_algorithm == candidate.id and view._variant()[1] == candidate.alg
    assert 'BLDDB' in ' '.join(text_values(view))
    assert repo.data.to_dict() == before


def test_new_explicit_blddb_preference_round_trips_without_copying_catalog_into_user_data():
    _, repo, _, view = open_library()
    key = 'UBL:UBR'; candidate = builtin_algorithms(key)[3]
    view.select_case(key)
    view._choose_variant(SimpleNamespace(control=SimpleNamespace(value=candidate.id)))
    before = deepcopy(repo.data.to_dict())
    next(c for c in walk(view) if isinstance(c, ft.TextButton) and c.content == 'Use selected alg').on_click(None)
    assert view.record().preferred_algorithm == candidate.id and not view.record().algorithms
    restored = AppData.from_dict(json.loads(json.dumps(repo.data.to_dict())))
    view.state.data = restored
    view.select_case(key)
    assert view.selected_algorithm == candidate.id and view._variant()[1] == candidate.alg
    for name, value in before.items():
        if name != 'corner_case_library': assert restored.to_dict()[name] == value


def test_saved_algorithm_ids_survive_a_change_in_group_popularity():
    from core import corner_algorithms as catalog_module
    key = 'UBL:UBR'
    original = {candidate.raw_alg: candidate for candidate in builtin_algorithms(key)}
    changed = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
    groups = changed['cases'][key]['groups']
    groups[1]['sources'].append('An additional source sheet')
    groups.sort(key=lambda group: -len(group['sources']))
    try:
        with patch.object(catalog_module, '_snapshot', return_value=changed):
            blddb_case_algorithms.cache_clear()
            refreshed = builtin_algorithms(key)
            assert refreshed[0].raw_alg != next(iter(original))
            assert refreshed[0].source_count == 24
            assert all(candidate.id == original[candidate.raw_alg].id for candidate in refreshed)
    finally:
        blddb_case_algorithms.cache_clear()


def test_legacy_builtin_preference_is_not_offered_but_remains_untouched_in_backups():
    _, repo, _, view = open_library()
    key = 'UBL:UBR'; old = legacy_builtin_algorithms(key)[0]
    repo.data.corner_case_library[key] = CornerCaseRecord(
        preferred_algorithm=old.id, status='learning', favorite=True, notes='Still here')
    before = deepcopy(repo.data.to_dict())
    view.select_case(key)
    assert view.selected_algorithm == '' and view._variant()[1] == builtin_algorithms(key)[0].alg
    assert old.id not in {o.key for o in view.variant_picker.options}
    assert repo.data.to_dict() == before
    assert AppData.from_dict(before).to_dict() == before


@pytest.mark.parametrize('preference', ['default', 'blddb', 'personal', 'legacy'])
def test_walkthrough_and_trainer_use_the_same_new_default_or_saved_personal_choice(preference):
    key = 'UBL:UBR'; builtins = builtin_algorithms(key)
    records = {}
    expected_id = builtins[0].id
    if preference == 'blddb':
        expected_id = builtins[1].id
        records[key] = CornerCaseRecord(preferred_algorithm=expected_id)
    elif preference == 'personal':
        expected_id = 'mine'
        records[key] = CornerCaseRecord(algorithms=[CaseAlgorithm('mine', 'My alg', builtins[0].raw_alg)], preferred_algorithm='mine')
    elif preference == 'legacy':
        records[key] = CornerCaseRecord(preferred_algorithm=legacy_builtin_algorithms(key)[0].id)
    before = deepcopy(records)
    scheme = letter_scheme()
    scheme.corners.buffer_piece = scheme.corners.buffer_sticker = 'UFR'
    scramble = ' '.join(tracing_moves(inverse_moves(parse_algorithm(builtins[0].raw_alg).moves)))
    plan = build_corner_plan(scramble, scheme, records)
    assert plan.steps[0].parts[0].algorithm_id == expected_id
    with patch('core.corner_trainer.solve_facelets', return_value=None):
        card = make_card(key, scheme, records)
    assert card.algorithm_id == expected_id
    assert records == before
