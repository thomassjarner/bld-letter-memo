"""Persistent case-browser controls, visible cube switches and case comparison."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import flet as ft
import flet.canvas as cv
import pytest

from core.algorithms import simplified_algorithm
from core.corner_algorithms import builtin_algorithms
from data.models import CaseAlgorithm, CornerCaseRecord
from test_case_library import open_library
from test_navigation import no_client_mount, text_values, walk
from ui.components.cube_projection import project_cube


@pytest.mark.parametrize('width,height', [(1400, 760), (1000, 600), (366, 570)])
def test_selecting_cases_keeps_the_browser_scroll_ancestors_rows_and_loaded_page(width, height):
    _, repo, _, view = open_library()
    view.set_viewport(width, height)
    view._more()
    view._more()
    before = deepcopy(repo.data.to_dict())
    body, listing = view.body.controls[0], view.case_list
    rows = list(listing.controls)
    browser = view.browser_scroll if width >= 980 else view.mobile_sidebar
    if width < 980: view.mobile_browser.expanded = True
    for index in (95, 110, 88):
        rows[index].content.on_click(None)
        assert view.body.controls[0] is body and view.case_list is listing
        assert len(listing.controls) == 150 and view.limit == 150
        assert all(a is b for a, b in zip(rows, listing.controls))
        assert (view.browser_scroll if width >= 980 else view.mobile_sidebar) is browser
        assert view.selected_case == view.filtered_cases()[index].id
        if width < 980:
            assert view.mobile_browser.expanded
            body.scroll_to = AsyncMock()
            with patch('flet.controls.base_control.BaseControl.page', property(lambda self: object())):
                asyncio.run(view._reset_case_scroll(view._navigation_token))
            body.scroll_to.assert_not_awaited()
    assert repo.data.to_dict() == before


@pytest.mark.parametrize('mode', ['3D', '2D'])
def test_visible_cube_switches_remove_letters_and_all_piece_emphasis_without_changing_the_case(mode):
    _, repo, _, view = open_library()
    before = deepcopy(repo.data.to_dict())
    cube = view.viewer
    cube.mode_picker.value = mode
    assert cube.display_switches in cube.controls
    assert isinstance(cube.letter_switch, ft.Switch) and isinstance(cube.focus_switch, ft.Switch)
    assert not any(c is cube.letter_switch or c is cube.focus_switch for c in walk(cube.view_options))
    cube.letter_switch.value = False
    cube.letter_switch.on_change(None)
    assert not any(isinstance(shape, cv.Text) for shape in cube.canvas.shapes)
    cube.focus_switch.value = False
    cube.focus_switch.on_change(None)
    state = cube.states[cube.index]
    tiles = project_cube(state, 460, 300, mode=mode, letters=False, focus=False, targets=('UBL', 'DFR'))
    assert all(not tile.label and tile.outline == '#0A0F0D' for tile in tiles)
    assert tiles == project_cube(state, 460, 300, mode=mode, letters=False, focus=False)
    view.select_case('UBL:LUF')
    assert not cube.letter_switch.value and not cube.focus_switch.value
    assert repo.data.to_dict() == before


def test_playground_compares_the_saved_preferred_alg_and_uses_scheme_letters_without_overwriting_either_draft():
    _, repo, _, view = open_library()
    key, source = 'BUR:BUL', "[R, U' L' U]"
    personal = source + " R R'"
    identifier = view.state.save_case_algorithm(key, 'My preferred comm', personal)
    view.scheme.corners.stickers['BUR'] = 'Æ'
    view.scheme.corners.stickers['BUL'] = 'Ø'
    before = deepcopy(repo.data.to_dict())
    view._set_mode('explorer')
    view.playground_converter.load(source, notify=True)
    labels = text_values(view.matched_case)
    assert view.matched_case.visible
    assert f'Solves case · {view.state.get_pair_display("ÆØ")}' in labels
    assert 'Current case algorithm · My preferred comm' in labels
    assert any('BUR (Æ) → BUL (Ø)' in value for value in labels)
    assert 'Moves: ' + simplified_algorithm(personal).expanded in labels
    assert not view.view_case_button.disabled
    view.search.value = 'does-not-match'
    view.view_case_button.on_click(None)
    assert view.mode == 'library' and view.selected_case == key
    assert view.selected_algorithm == identifier and view.case_converter.source == personal
    assert any(case.id == key for case in view.filtered_cases()[:view.limit])
    assert repo.data.to_dict() == before
    view._set_mode('explorer')
    assert view.playground_converter.source == source
    view.open_case_button.on_click(None)
    assert view.case_converter.source == source and view.record(key).preferred_algorithm == identifier
    assert repo.data.to_dict() == before


def test_playground_match_refreshes_labels_and_builtin_preference_and_clears_stale_links():
    _, repo, _, view = open_library()
    key, source = 'BUR:BUL', "[R, U' L' U]"
    preferred = builtin_algorithms(key)[-1]
    view.state.update_corner_case(key, preferred=preferred.id)
    before = deepcopy(repo.data.to_dict())
    view._set_mode('explorer')
    view.playground_converter.load(source, notify=True)
    assert 'Current case algorithm · ' + preferred.name in text_values(view.matched_case)
    view.label_scheme = None
    view._render_explorer()
    assert 'Solves case · BUR / BUL' in text_values(view.matched_case)
    view.playground_converter.load('R', notify=True)
    assert 'No matching UFR corner case' in text_values(view.matched_case)
    assert view.view_case_button.disabled and view.open_case_button.disabled
    assert not view.playground_save.disabled
    view.playground_converter.load('R +', notify=True)
    assert not view.matched_case.visible and not view.matched_case.content.controls
    assert view.view_case_button.disabled and view.playground_save.disabled
    assert repo.data.to_dict() == before


def test_playground_retains_an_invalid_imported_preferred_algorithm_for_repair():
    _, repo, _, view = open_library()
    key = 'BUR:BUL'
    repo.data.corner_case_library[key] = CornerCaseRecord(
        algorithms=[CaseAlgorithm('bad', 'Imported choice', 'R +')], preferred_algorithm='bad')
    before = deepcopy(repo.data.to_dict())
    view._set_mode('explorer')
    view.playground_converter.load("[R, U' L' U]", notify=True)
    assert 'Current case algorithm · Imported choice' in text_values(view.matched_case)
    assert 'This saved algorithm needs correction in the case library.' in text_values(view.matched_case)
    assert not view.view_case_button.disabled and not view.playground_save.disabled
    assert repo.data.to_dict() == before
