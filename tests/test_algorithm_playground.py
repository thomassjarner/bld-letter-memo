"""Linked fields, buffer-independent effects and saved playground algorithms."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
import pytest

from core.algorithm_analysis import analyze_algorithm
from core.algorithms import algorithm_states, parse_algorithm
from core.cube_definitions import EDGE_PIECES
from data.models import AppData, CURRENT_VERSION, PlaygroundAlgorithm
from data.shared_preferences_repository import SharedPreferencesAppDataRepository
from test_case_library import open_library
from test_navigation import MemoryRepository, click_nav, mount, no_client_mount, walk
from ui.components.algorithm_converter import AlgorithmConverter
from ui.state import AppState


def enter(converter, direction, value):
    control = converter.commutator if direction == 'commutator' else converter.final_alg
    control.value = value
    control.on_change(None)


@pytest.mark.parametrize('notation', ['[R,U]', "[Fw: [R2,E]]", "f:[U2,R' D' R]", "[z R D': [Rw2,S]]"])
def test_commutator_input_immediately_populates_clean_final_moves(notation):
    converter = AlgorithmConverter()
    enter(converter, 'commutator', notation)
    assert converter.algorithm is not None and not converter.commutator.error_text
    assert converter.source == notation
    assert converter.final_alg.value and '[' not in converter.final_alg.value
    assert algorithm_states(parse_algorithm(converter.final_alg.value))[-1] == algorithm_states(parse_algorithm(notation))[-1]


@pytest.mark.parametrize('notation', ['[R,U]', '[M,U2]', "[Fw: [R2,E]]", "[R, U' L' U]"])
def test_final_moves_input_immediately_populates_a_verified_commutator(notation):
    source = parse_algorithm(notation).expanded
    converter = AlgorithmConverter()
    enter(converter, 'final', source)
    assert converter.final_alg.value == source and converter.source == source
    assert converter.commutator.value
    assert algorithm_states(parse_algorithm(converter.commutator.value))[-1] == algorithm_states(parse_algorithm(source))[-1]


def test_last_edited_field_drives_conversion_and_partial_input_never_leaves_stale_output():
    converter = AlgorithmConverter()
    enter(converter, 'commutator', '[R,U]')
    enter(converter, 'final', "M U2 M' U2")
    assert converter.last_input == 'final' and 'M' in converter.commutator.value
    enter(converter, 'commutator', '[F,D]')
    assert converter.source == '[F,D]' and converter.final_alg.value == "F D F' D'"
    enter(converter, 'commutator', '[F,')
    assert converter.algorithm is None and converter.commutator.error_text and not converter.final_alg.value
    enter(converter, 'final', 'R')
    assert converter.algorithm is not None and not converter.commutator.value
    assert 'usable' in converter.status.value
    enter(converter, 'final', '')
    assert converter.algorithm is None and not converter.commutator.value


def test_loading_preserves_saved_notation_and_programmatic_edits_can_be_synchronized():
    source = "[R: [R' D':[R' D R,U2]]]"
    converter = AlgorithmConverter()
    converter.load(source)
    assert converter.source == source
    assert converter.final_alg.value == "D' R' D R U2 R' D' R U2 D"
    converter.final_alg.value = "R U R' U'"
    converter.sync()
    assert converter.source == "R U R' U'" and converter.commutator.value


def test_late_debounced_search_cannot_replace_a_newer_commutator_or_cleared_field():
    converter = AlgorithmConverter()
    page = SimpleNamespace(run_task=Mock())
    with patch.object(converter, '_page', return_value=page), patch.object(converter, 'update'):
        enter(converter, 'final', "R U R' U'")
        callback, revision, source = page.run_task.call_args.args
        assert converter.pending and not converter.commutator.value
        enter(converter, 'commutator', '[F,D]')
        with patch('ui.components.algorithm_converter.asyncio.sleep', new=AsyncMock()):
            asyncio.run(callback(revision, source))
        assert converter.commutator.value == '[F,D]' and converter.final_alg.value == "F D F' D'"
        enter(converter, 'final', "M U2 M' U2")
        callback, revision, source = page.run_task.call_args.args
        converter.cancel_pending()
        with patch('ui.components.algorithm_converter.asyncio.sleep', new=AsyncMock()):
            asyncio.run(callback(revision, source))
        assert not converter.commutator.value


def test_general_effect_analysis_reports_permutation_orientation_and_cube_reorientation():
    right = analyze_algorithm('R')
    assert right.corner_cycles == (('UBR', 'DBR', 'DFR', 'UFR'),)
    assert right.edge_cycles == (('UR', 'BR', 'DR', 'FR'),)
    assert len(right.affected_corners) == len(right.affected_edges) == 4 and right.ufr_case is None
    edge = analyze_algorithm('[M,U2]')
    assert not edge.affected_corners and len(edge.affected_edges) == 3 and edge.edge_cycles
    flips = analyze_algorithm("M' U M' U M' U2 M U M U M U2")
    assert set(flips.flipped_in_place) == {'UB', 'UF'} and not flips.edge_cycles
    twists = analyze_algorithm("(R' D' R D)2")
    assert 'UFR' in twists.twisted_in_place
    rotation = analyze_algorithm('x')
    assert rotation.reorients_cube and not rotation.affected_corners and not rotation.affected_edges
    assert not analyze_algorithm("R R'").sticker_changes
    case = analyze_algorithm("[R, U' L' U]")
    assert case.ufr_case == 'BUR:BUL'


def test_cancelled_reverse_conversion_is_completed_when_the_draft_is_reopened():
    converter = AlgorithmConverter()
    page = SimpleNamespace(run_task=Mock())
    with patch.object(converter, '_page', return_value=page), patch.object(converter, 'update'):
        enter(converter, 'final', "M U2 M' U2")
        converter.cancel_pending()
        assert not converter.commutator.value
        converter.sync()
        assert converter.commutator.value and not converter.pending


def test_unsaved_case_draft_and_its_preview_survive_a_playground_visit():
    _, repo, _, view = open_library()
    before = deepcopy(repo.data.to_dict())
    draft = view.cases[view.selected_case].starter + " R R'"
    enter(view.case_converter, 'final', draft)
    assert view.viewer.algorithm.source == draft
    view._set_mode('explorer')
    view._set_mode('library')
    assert view.case_converter.source == draft and view.viewer.algorithm.source == draft
    assert repo.data.to_dict() == before


def test_new_general_collection_migrates_old_backups_and_roundtrips_without_other_field_changes():
    old = AppData().to_dict()
    old.pop('playground_algorithms')
    old['version'] = 16
    old['global_words'] = {'AB': 'Word'}
    old['pair_aliases'] = {'AB': 'ØB'}
    migrated = AppData.from_dict(old)
    assert CURRENT_VERSION == 17 and migrated.playground_algorithms == []
    for name, value in old.items():
        if name != 'version': assert migrated.to_dict()[name] == value
    migrated.playground_algorithms = [PlaygroundAlgorithm('one', 'Right turn', 'R', 'No fixed case')]
    restored = AppData.from_dict(json.loads(json.dumps(migrated.to_dict())))
    assert restored.to_dict() == migrated.to_dict()
    assert SharedPreferencesAppDataRepository._richness(restored) > SharedPreferencesAppDataRepository._richness(AppData.from_dict(old))
    repaired = PlaygroundAlgorithm.load_many([{'id': 'x', 'alg': 'R'}, {'id': 'x', 'alg': 'invalid'}, {}, None])
    assert len(repaired) == 3 and len({a.id for a in repaired}) == 3 and repaired[1].alg == 'invalid'
    assert PlaygroundAlgorithm.load_many('bad') == []


def test_any_valid_algorithm_can_be_saved_updated_copied_and_deleted_with_atomic_validation():
    repo = MemoryRepository()
    state = AppState(repo)
    before = deepcopy(repo.data.to_dict())
    first = state.save_playground_algorithm('R turn', 'R', 'General, no UFR case')
    state.save_playground_algorithm('Updated', 'Rw', 'Wide', first)
    second = state.save_playground_algorithm('Copy', 'Rw', 'Copy note')
    assert first != second and len(state.data.playground_algorithms) == 2
    assert state.data.playground_algorithms[0].alg == 'Rw'
    unchanged = deepcopy(state.data.to_dict())
    with patch.object(repo, 'save') as save:
        for source, identifier in (('R + U', None), ('R', 'missing')):
            with pytest.raises(ValueError): state.save_playground_algorithm('Bad', source, algorithm_id=identifier)
        save.assert_not_called()
    assert state.data.to_dict() == unchanged
    state.delete_playground_algorithm(first)
    assert [a.id for a in state.data.playground_algorithms] == [second]
    for name, value in before.items():
        if name != 'playground_algorithms': assert state.data.to_dict()[name] == value


def test_playground_starts_independently_and_saves_non_case_algorithms_without_a_scheme():
    page, repo = mount()
    view = click_nav(page, 'Method Library')
    view._set_mode('explorer')
    assert view._analysis is None and view.playground_save.disabled and view._cases is None
    before = deepcopy(repo.data.to_dict())
    enter(view.playground_converter, 'final', 'R')
    assert view._analysis and view._identified is None and not view.playground_save.disabled
    assert view.open_case_button.disabled and not view.viewer.play_button.disabled
    assert repo.data.to_dict() == before
    view.playground_name.value, view.playground_notes.value = 'Right turn', 'An unrestricted alg'
    view.playground_save.on_click(None)
    saved = repo.data.playground_algorithms[0]
    assert saved.name == 'Right turn' and saved.alg == 'R' and saved.notes == 'An unrestricted alg'
    assert not repo.data.corner_case_library
    view._new_playground()
    assert not view.playground_converter.source and view._analysis is None
    view.playground_saved.value = saved.id
    view._choose_playground(SimpleNamespace(control=view.playground_saved))
    assert view.playground_converter.source == 'R' and view.playground_notes.value == saved.notes
    enter(view.playground_converter, 'final', 'Rw')
    view._save_playground()
    assert len(repo.data.playground_algorithms) == 1 and repo.data.playground_algorithms[0].id == saved.id
    assert saved.alg == 'Rw'
    view._save_playground(as_new=True)
    assert len(repo.data.playground_algorithms) == 2
    view._delete_playground()
    assert len(repo.data.playground_algorithms) == 1 and view.playground_converter.source == 'Rw'


def test_invalid_input_clears_stale_analysis_and_saved_import_errors_can_be_repaired():
    _, repo, _, view = open_library()
    view._set_mode('explorer')
    enter(view.playground_converter, 'final', 'R')
    enter(view.playground_converter, 'final', 'R +')
    assert view._analysis is None and view.playground_save.disabled and view.open_case_button.disabled
    assert not view.viewer.algorithm.moves and view.viewer.play_button.disabled
    repo.data.playground_algorithms = [PlaygroundAlgorithm('bad', 'Imported', 'invalid', 'Keep my notes')]
    view.playground_saved.value = 'bad'
    view._choose_playground(SimpleNamespace(control=view.playground_saved))
    assert view.playground_save.disabled and view.playground_converter.final_alg.error_text
    assert repo.data.playground_algorithms[0].alg == 'invalid'
    enter(view.playground_converter, 'commutator', '[M,U2]')
    view._save_playground()
    assert repo.data.playground_algorithms[0].alg == '[M,U2]' and repo.data.playground_algorithms[0].notes == 'Keep my notes'


def test_matching_case_is_an_optional_explicit_route_and_navigation_restores_each_algorithm():
    page, repo, _, view = open_library()
    case_source = view.case_converter.source
    view._set_mode('explorer')
    source = "[R, U' L' U]"
    enter(view.playground_converter, 'commutator', source)
    assert view._identified == 'BUR:BUL' and not view.open_case_button.disabled
    before = deepcopy(repo.data.to_dict())
    view._open_identified()
    assert view.mode == 'library' and view.algorithm_editor.visible and view.case_converter.source == source
    assert repo.data.to_dict() == before
    view._set_mode('explorer')
    assert view.playground_converter.source == source and view.viewer.algorithm.source == source
    enter(view.playground_converter, 'final', 'R')
    view._set_mode('library')
    assert not view.viewer.play_button.disabled
    view._set_mode('explorer')
    assert view.viewer.algorithm.source == 'R' and view._analysis.ufr_case is None
    click_nav(page, 'Timer')
    assert not view.viewer.playing
    assert repo.data.to_dict() == before


@pytest.mark.parametrize('width,height', [(1400, 760), (1000, 430), (900, 650), (366, 570), (280, 380)])
def test_playground_scrolling_and_linked_fields_fit_wide_and_narrow_viewports(width, height):
    _, repo, _, view = open_library()
    view._set_mode('explorer')
    enter(view.playground_converter, 'final', 'R')
    before = deepcopy(repo.data.to_dict())
    view.set_viewport(width, height)
    assert view.header.height + view.spacing + view.body.height <= height
    if width >= 980:
        row = view.body.controls[1]
        assert sum(c.width for c in row.controls) + row.spacing <= width
        assert all(isinstance(c.content, ft.ListView) and c.content.height < c.height for c in row.controls)
    else: assert isinstance(view.body.controls[0], ft.ListView)
    assert len([c for c in walk(view.playground_converter) if isinstance(c, ft.TextField)]) == 2
    assert repo.data.to_dict() == before
