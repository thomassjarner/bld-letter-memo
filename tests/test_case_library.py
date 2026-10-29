"""Case identity, exact alg effects, persistence and library UI regressions."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import flet as ft
import pytest

from core.algorithms import algorithm_states, apply_move, inverse_moves, inverse_state, normalized_state, parse_algorithm
from core.corner_cases import BUFFER, SUBSETS, TARGETS, case_id, corner_cases, identify_case, subset_for
from core.cube_definitions import CORNER_PIECES, find_piece_for_sticker
from core.tracer import ScrambleTracer, _at, _solved
from data.models import AppData, CaseAlgorithm, CornerCaseRecord, CURRENT_VERSION
from data.shared_preferences_repository import SharedPreferencesAppDataRepository
from test_navigation import click_nav, mount, no_client_mount, walk
from test_progressive_memo import letter_scheme
from ui.components.cube_projection import project_cube


def open_library():
    page, repo = mount()
    scheme = letter_scheme()
    repo.data.schemes = {scheme.name: scheme}
    repo.data.active_scheme = scheme.name
    hub = click_nav(page, 'Practice')
    view = click_nav(page, 'Method Library')
    assert view.mode == 'overview' and view._cases is None
    view._set_mode('library')
    return page, repo, hub, view


def test_all_378_cases_have_correct_subsets_and_starters_verified_by_the_original_tracer():
    cases = corner_cases()
    expected = {a + ':' + b for a in TARGETS for b in TARGETS
                if find_piece_for_sticker(a, CORNER_PIECES) != find_piece_for_sticker(b, CORNER_PIECES)}
    assert len(cases) == 378 and set(cases) == expected
    assert {s: sum(c.subset == s for c in cases.values()) for s in SUBSETS} == {'U/U': 54, 'U/D': 108, 'D/U': 108, 'D/D': 108}
    assert subset_for('FUL', 'RDF') == 'U/D'  # classify the piece, not its visible face
    scheme = letter_scheme()
    scheme.corners.buffer_piece = scheme.corners.buffer_sticker = BUFFER
    for case in cases.values():
        algorithm = parse_algorithm(case.starter)
        assert identify_case(algorithm) == case.id
        trace = ScrambleTracer().trace(' '.join(inverse_moves(algorithm.moves)), scheme)
        assert trace.corner_targets == [case.first, case.second]
        assert not trace.edge_targets and not trace.edge_orientation and not trace.corner_orientation
        assert not trace.corner_cycle_breaks
        assert len(algorithm.moves) <= 16


def test_custom_alternatives_preferences_progress_notes_and_backups_preserve_other_data():
    _, repo, _, view = open_library()
    before = deepcopy(repo.data.to_dict())
    key = view.selected_case
    case = corner_cases()[key]
    state = view.state
    first = state.save_case_algorithm(key, 'My comm', case.starter)
    second = state.save_case_algorithm(key, 'Alternative', case.starter + " M M' x x'")
    assert len(state.data.corner_case_library[key].algorithms) == 2
    state.save_case_algorithm(key, 'Updated', case.starter + " R R'", first)
    state.update_corner_case(key, preferred=first, status='learning', notes='Use the left index.', favorite=True)
    record = state.data.corner_case_library[key]
    assert record.preferred_algorithm == first and record.algorithms[0].name == 'Updated'
    loaded = AppData.from_dict(json.loads(json.dumps(repo.data.to_dict())))
    assert loaded.corner_case_library[key].to_dict() == record.to_dict()
    for name, value in before.items():
        if name != 'corner_case_library':
            assert loaded.to_dict()[name] == value
    state.delete_case_algorithm(key, first)
    assert record.preferred_algorithm == '' and [a.id for a in record.algorithms] == [second]
    assert record.notes == 'Use the left index.' and record.status == 'learning'


def test_wrong_case_invalid_alg_and_missing_update_id_never_save_or_create_empty_records():
    _, repo, _, view = open_library()
    case = view.cases[view.selected_case]
    before = deepcopy(repo.data.to_dict())
    inverse = ' '.join(inverse_moves(parse_algorithm(case.starter).moves))
    with patch.object(repo, 'save') as save:
        for source in ('R', inverse, '(R U)99999'):
            with pytest.raises(ValueError):
                view.state.save_case_algorithm(case.id, 'Bad', source)
        with pytest.raises(ValueError):
            view.state.save_case_algorithm(case.id, 'Bad', case.starter, 'missing-id')
        save.assert_not_called()
    assert repo.data.to_dict() == before


def test_imported_invalid_alg_is_retained_but_cannot_become_preferred():
    _, repo, _, view = open_library()
    key = view.selected_case
    repo.data.corner_case_library[key] = CornerCaseRecord(algorithms=[CaseAlgorithm('bad', 'Imported', 'R')])
    before = deepcopy(repo.data.to_dict())
    with patch.object(repo, 'save') as save:
        view._set_record(key, preferred='bad')
        assert view.error.value
        save.assert_not_called()
    assert repo.data.to_dict() == before


def test_old_backups_migrate_without_changing_old_fields_and_recovery_counts_case_data():
    old = AppData().to_dict()
    old.pop('corner_case_library')
    old['version'] = 15
    old['global_words'] = {'AB': 'example'}
    migrated = AppData.from_dict(old)
    assert CURRENT_VERSION == 16 and migrated.corner_case_library == {}
    for name, value in old.items():
        if name != 'version': assert migrated.to_dict()[name] == value
    key = next(iter(corner_cases()))
    rich = deepcopy(migrated)
    rich.corner_case_library[key] = CornerCaseRecord(
        algorithms=[CaseAlgorithm('a', 'Mine', corner_cases()[key].starter)], notes='Remember this.')
    assert SharedPreferencesAppDataRepository._richness(rich) > SharedPreferencesAppDataRepository._richness(migrated)
    imported = CornerCaseRecord.from_dict({'status': 'invalid', 'algorithms': [
        {'id': 'imported-2', 'alg': 'R'}, {'id': 'x', 'alg': 'U'}, {'id': 'x', 'alg': 'F'}]})
    assert len({a.id for a in imported.algorithms}) == 3 and imported.status == 'new'


def test_library_buffer_is_local_and_letter_scheme_changes_do_not_move_case_records():
    _, repo, _, view = open_library()
    before = deepcopy(repo.data.schemes['gold'].to_dict())
    key = view.selected_case
    view.state.update_corner_case(key, notes='Fixed case identity', status='learned')
    another = deepcopy(repo.data.schemes['gold'])
    another.name = 'Different letters'
    another.corners.stickers = {s: 'Z' for s in another.corners.stickers}
    repo.data.schemes[another.name] = another
    view.scheme_picker.value = another.name
    view._choose_scheme(SimpleNamespace(control=view.scheme_picker))
    assert repo.data.active_scheme == 'gold'
    assert repo.data.schemes['gold'].to_dict() == before
    assert repo.data.corner_case_library[key].notes == 'Fixed case identity'
    assert BUFFER == 'UFR' and repo.data.schemes['gold'].corners.buffer_sticker == 'LUB'


def test_filters_pagination_custom_save_drafts_and_delayed_note_blur_are_case_scoped():
    _, repo, _, view = open_library()
    assert len(view.case_list.controls) == 50
    view._more()
    assert len(view.case_list.controls) == 100
    view.subset.value = 'U/U'
    view._filter_changed()
    assert len(view.filtered_cases()) == 54
    case = view.filtered_cases()[0]
    view.select_case(case.id)
    old_notes = view.notes_field
    draft = case.starter + " R R'"
    view.algorithm_field.value = draft
    view._preview_editor()
    view._set_record(case.id, favorite=True)
    view._hide()
    assert view.algorithm_field.value == draft
    assert view.viewer.algorithm.source == draft
    assert not view.viewer.move_text.visible
    view.name_field.value = 'My variant'
    view._save_algorithm(False)
    assert view.record().algorithms[0].alg == draft and view.record().preferred_algorithm
    other = view.filtered_cases()[1]
    view.select_case(other.id)
    old_notes.value = 'Late blur on the first case'
    old_notes.on_blur(SimpleNamespace(control=old_notes))
    assert view.record(case.id).notes == 'Late blur on the first case'
    assert view.record(other.id).notes == ''
    view.favorites.value = True
    view._filter_changed()
    assert [c.id for c in view.filtered_cases()] == [case.id]


def test_explorer_lesson_and_navigation_leave_timer_and_scheme_behavior_intact():
    page, repo, hub, view = open_library()
    timer = click_nav(page, 'Timer')
    click_nav(page, 'Method Library')
    before = deepcopy(repo.data.to_dict())
    view._set_mode('explorer')
    assert view._identified in view.cases
    view._open_identified()
    assert view.mode == 'library' and not view.error.value
    view._set_mode('lesson')
    assert [s.label for s in view.viewer.algorithm.stages] == ['A', 'B', 'Undo A', 'Undo B']
    view.viewer.playing = True
    token = view.viewer._token
    click_nav(page, 'Timer')
    assert not view.viewer.playing and view.viewer._token > token
    assert click_nav(page, 'Timer') is timer
    assert repo.data.to_dict() == before


@pytest.mark.parametrize('width,height', [(1400, 760), (1000, 430), (900, 650), (366, 570), (280, 380)])
def test_responsive_layout_keeps_case_list_and_all_details_scrollable(width, height):
    _, repo, _, view = open_library()
    before = deepcopy(repo.data.to_dict())
    viewer = view.viewer
    view.set_viewport(width, height)
    assert view.viewer is viewer
    assert view.body.height <= height - 96
    if width >= 980:
        row = view.body.controls[0]
        assert isinstance(row, ft.Row)
        assert sum(c.width for c in row.controls) + row.spacing <= width
        assert all(isinstance(panel.content, ft.ListView) for panel in row.controls)
        assert all(panel.content.height < panel.height for panel in row.controls)
    else:
        assert isinstance(view.body.controls[0], ft.ListView)
        assert isinstance(view.body.controls[0].controls[0], ft.ExpansionTile)
    assert viewer.canvas.width <= width - 28
    assert repo.data.to_dict() == before


@pytest.mark.parametrize('dark', [False, True])
def test_new_controls_and_dynamic_playback_text_use_contrasting_theme_colors(dark):
    _, repo, _, view = open_library()
    repo.data.dark_mode = dark
    view.refresh()
    view.viewer.seek(1)
    expected = '#F0F4F3' if dark else '#182B25'
    for control in walk(view):
        if isinstance(control, (ft.TextField, ft.Dropdown)):
            assert control.color == expected
    for span in view.viewer.move_text.spans:
        assert isinstance(span.style.color, str) and span.style.color.startswith('#')


def test_projection_stays_in_bounds_and_keeps_centers_blank_in_both_views():
    state = _solved()
    before = deepcopy(state)
    for mode in ('3D', '2D'):
        for width, height in ((240, 220), (600, 350)):
            for fraction in (0, .5, 1):
                tiles = project_cube(state, width, height, mode=mode, moving='Rw', fraction=fraction,
                                     targets=('UBL', 'DFR'))
                assert tiles
                assert all(-1 <= x <= width + 1 and -1 <= y <= height + 1 for tile in tiles for x, y in tile.points)
                if mode == '2D':
                    assert len(tiles) == 54 and sum(not tile.label for tile in tiles) == 6
    assert state == before


@pytest.mark.parametrize('move', ['R', 'Rw', 'Fw', "Fw'", 'M', 'x', "F'", 'U2'])
def test_animated_turn_ends_at_the_exact_next_cube_geometry(move):
    state = algorithm_states(parse_algorithm("R U' L' U"))[-1]
    def signature(tiles):
        return sorted((t.color, t.label, tuple(sorted((round(x, 5), round(y, 5)) for x, y in t.points))) for t in tiles)
    animated = project_cube(state, 460, 300, moving=move, fraction=1)
    final = project_cube(apply_move(state, move), 460, 300)
    assert signature(animated) == signature(final)


def test_search_filters_keep_the_search_field_and_mobile_browser_mounted():
    _, _, _, view = open_library()
    view.set_viewport(366, 570)
    body, browser, search = view.body.controls[0], view.body.controls[0].controls[0], view.search
    for text in ('U', 'UB', 'UBL'):
        view.search.value = text
        view._filter_changed()
        assert view.search is search
        assert view.body.controls[0] is body and body.controls[0] is browser
        assert view.filtered_cases()


def test_random_matching_case_supports_a_single_case_filter_and_reports_empty_filters():
    _, repo, _, view = open_library()
    before = deepcopy(repo.data.to_dict())
    view.search.value = view.selected_case
    view._filter_changed()
    assert len(view.filtered_cases()) == 1
    view.viewer.seek(len(view.viewer.states) - 1)
    view._random_case()
    assert view.viewer.index == 0 and view.hidden
    view.search.value = 'no-such-sticker'
    view._filter_changed()
    view._random_case()
    assert 'No cases match' in view.notice.value
    assert repo.data.to_dict() == before


def test_playback_cancellation_keeps_an_exact_state_and_stops_old_frames():
    _, _, _, view = open_library()
    cube = view.viewer
    cube.load(parse_algorithm("[R, U' L' U]"))
    cube.playing = True
    token = cube._token
    with patch('ui.components.algorithm_cube.asyncio.sleep', new=AsyncMock()):
        asyncio.run(cube._play(token, len(cube.states) - 1))
    assert cube.index == 8 and not cube.playing
    assert cube.states[cube.index] == algorithm_states(cube.algorithm)[-1]
    cube.seek(0)
    original = cube._redraw
    calls = []
    def redraw(update=True):
        calls.append(cube._fraction)
        if len(calls) == 2:
            cube.stop(update=False)
        original(update=False)
    with patch.object(cube, '_redraw', redraw), patch('ui.components.algorithm_cube.asyncio.sleep', new=AsyncMock()):
        asyncio.run(cube._play(cube._token, 8))
    assert cube.index == 0 and cube._moving is None
