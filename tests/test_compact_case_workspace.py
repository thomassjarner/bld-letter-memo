"""Cube-first case layout, safe notation cleanup and original stage playback."""
import asyncio
from copy import deepcopy
import random
from unittest.mock import AsyncMock, patch

import flet as ft
import pytest

from core.algorithms import algorithm_states, parse_algorithm, simplify_moves, simplified_algorithm
from core.corner_algorithms import supplied_case_algorithms
from test_case_library import open_library
from test_navigation import no_client_mount, walk
from ui.components.algorithm_cube import AlgorithmCube


@pytest.mark.parametrize('source,expected', [
    ("R R'", ''), ("R2 R'", 'R'), ('U U U', "U'"),
    ("R U U' R'", ''), ("Fw Fw'", ''), ('f f', 'Fw2'),
    ("R L R'", 'L'), ("x Rw M x' Rw'", 'M'),
    ("D U2 D'", 'U2'), ('R L2 R', 'R2 L2'),
    ("R U R' U'", "R U R' U'"), ("Rw R'", "Rw R'"),
])
def test_move_cleanup_combines_turns_and_cancels_without_reordering_unrelated_moves(source, expected):
    original = parse_algorithm(source)
    clean = simplified_algorithm(original)
    assert clean.expanded == expected
    assert clean.source == original.source and original.moves == parse_algorithm(source).moves
    assert algorithm_states(clean)[-1] == algorithm_states(original)[-1]
    assert simplify_moves(clean.moves) == clean.moves


def test_screenshot_case_shows_only_the_actual_clean_execution():
    source = "[R: [R' D':[R' D R,U2]]]"
    original = parse_algorithm(source)
    clean = simplified_algorithm(original)
    assert clean.expanded == "D' R' D R U2 R' D' R U2 D"
    assert original.source == source and len(original.moves) == 14 and len(clean.moves) == 10
    cube = AlgorithmCube()
    cube.load(original)
    assert cube.algorithm.moves == clean.moves
    assert ''.join(s.text for s in cube.move_text.spans).strip() == clean.expanded
    assert cube.counter.value == '0 / 10'


def test_cleanup_keeps_exact_full_cube_effects_for_all_supplied_options_and_mixed_notation():
    sources = [a.alg for group in supplied_case_algorithms().values() for a in group]
    rng = random.Random(2300)
    moves = tuple(face + wide + suffix for face in 'URFDLB' for wide in ('', 'w') for suffix in ('', "'", '2'))
    moves += tuple(face + suffix for face in 'MESxyz' for suffix in ('', "'", '2'))
    sources += [' '.join(rng.choices(moves, k=60)) for _ in range(40)]
    shortened = 0
    for source in sources:
        original = parse_algorithm(source)
        clean = simplified_algorithm(original)
        assert algorithm_states(clean)[-1] == algorithm_states(original)[-1]
        assert len(clean.moves) <= len(original.moves)
        shortened += len(clean.moves) < len(original.moves)
    assert shortened >= 564


def test_original_commutator_stages_remain_available_and_switching_cancels_playback():
    cube = AlgorithmCube()
    original = parse_algorithm("[R: [R, U]]")
    cube.load(original)
    assert not cube.structure_switch.value and cube.algorithm.moves != original.moves
    clean_final = cube.states[-1]
    cube.playing = True
    token = cube._token
    cube.structure_switch.value = True
    cube._change_structure()
    assert cube.algorithm is original and cube.index == 0
    assert not cube.playing and cube._token > token and cube.states[-1] == clean_final
    assert [s.label for s in cube.algorithm.stages] == ['Setup', 'A', 'B', 'Undo A', 'Undo B', 'Undo setup']
    cube.load(original)
    assert not cube.structure_switch.value and cube.algorithm.moves != original.moves


@pytest.mark.parametrize('width,height', [(1800, 960), (1400, 760), (1080, 620), (1000, 430), (900, 650), (366, 570), (280, 380)])
def test_new_cases_keep_the_cube_in_view_and_the_editor_visible_without_expanding(width, height):
    _, repo, _, view = open_library()
    before = deepcopy(repo.data.to_dict())
    view.set_viewport(width, height)
    view.notes_open = True
    if view.mobile_browser is not None: view.mobile_browser.expanded = True
    view.viewer.seek(len(view.viewer.states) - 1)
    view.select_case('UBL:FDR')
    assert view.viewer.index == 0
    assert view.algorithm_editor.visible and not isinstance(view.algorithm_editor, ft.ExpansionTile)
    assert not view.notes_tile.expanded
    assert view.mobile_browser is None or not view.mobile_browser.expanded
    assert view.viewer.controls[0] is view.viewer.canvas
    assert view.detail_controls[:2] == [view.case_toolbar, view.viewer]
    assert view.case_canvas_top + view.viewer.canvas.height <= view.body.height
    assert view.header.height + view.spacing + view.body.height <= height
    assert view.case_converter in view.algorithm_editor.controls
    assert view.case_converter.final_alg is view.algorithm_field
    assert not view.error.visible and not view.notice.visible
    assert view.favorites.height is None and view.favorites.width is None
    assert repo.data.to_dict() == before


def test_wide_layout_keeps_editing_in_a_separate_scroll_pane_and_preserves_drafts():
    _, _, _, view = open_library()
    view.set_viewport(1400, 760)
    assert view.split_tools and len(view.detail_scrolls) == 2
    cube_pane, tools_pane = view.detail_scrolls
    assert cube_pane.controls == [view.viewer, view.case_details]
    assert view.algorithm_editor in tools_pane.controls
    assert not any(c is view.algorithm_editor for c in walk(cube_pane))
    assert view.learning_status in list(walk(view.case_details))
    assert view.notes_field in list(walk(view.case_details))
    assert not any(c in (view.learning_status, view.notes_tile) for c in walk(tools_pane))
    case_row = view.body.controls[0].controls[1].content.controls[1]
    assert case_row.controls[1].width >= 360
    assert sum(c.width for c in case_row.controls) + case_row.spacing <= view.body.controls[0].controls[1].width - 20
    assert view.viewer.canvas.width < view.body.width / 2
    assert view.viewer.canvas.height <= 310
    canvas_height = view.viewer.canvas.height
    draft = view.algorithm_field.value + " R R'"
    view.algorithm_field.value = draft
    view._set_record(view.selected_case, favorite=True)
    assert view.algorithm_editor.visible and view.algorithm_field.value == draft
    assert view.viewer.canvas.height == canvas_height


def test_case_scroll_reset_goes_to_top_and_ignores_stale_navigation():
    _, _, _, view = open_library()
    view.set_viewport(1400, 760)
    calls = [AsyncMock(), AsyncMock()]
    for pane, callback in zip(view.detail_scrolls, calls): pane.scroll_to = callback
    with patch('flet.controls.base_control.BaseControl.page', property(lambda self: object())):
        asyncio.run(view._reset_case_scroll(view._navigation_token))
        for callback in calls: callback.assert_awaited_once_with(offset=0, duration=0)
        asyncio.run(view._reset_case_scroll(view._navigation_token - 1))
        for callback in calls: assert callback.await_count == 1


@pytest.mark.parametrize('dark', [False, True])
def test_compact_fields_and_always_open_editing_keep_readable_theme_colors(dark):
    _, repo, _, view = open_library()
    repo.data.dark_mode = dark
    view.refresh()
    expected = '#F0F4F3' if dark else '#182B25'
    for c in walk(view):
        if isinstance(c, (ft.TextField, ft.Dropdown)): assert c.color == expected
    for c in (view.favorites, view.viewer.letter_switch, view.viewer.focus_switch, *view.status_choices.values()):
        assert c.height is None and c.width is None
        assert c.label_style.color == expected
