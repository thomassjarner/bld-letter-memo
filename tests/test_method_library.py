"""Method Library routes, overview usability and timed animation regressions."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

import flet as ft
import pytest

from core.algorithms import parse_algorithm
from data.models import CornerCaseRecord
from test_navigation import click_nav, mount, no_client_mount, text_values, walk
from ui.components.algorithm_cube import AlgorithmCube


def test_home_and_top_level_navigation_open_the_same_method_library_without_loading_cases():
    with patch('ui.pages.case_library_page.corner_cases', side_effect=AssertionError('Catalog loaded too soon')):
        page, repo = mount()
        before = deepcopy(repo.data.to_dict())
        home = page.root.controls[0].content
        button = next(c for c in walk(home) if isinstance(c, ft.TextButton) and c.content == 'Open Method Library')
        button.on_click(None)
        view = page.root.controls[0].content
        assert view.mode == 'overview' and view.active and view._cases is None
        assert {'Method Library', 'Choose where to begin.', 'Jump to a subset'} <= set(text_values(view))
        practice = click_nav(page, 'Practice')
        assert 'Learn · Case Library' not in text_values(practice)
        assert not view.active
        assert click_nav(page, 'Method Library') is view
        assert repo.data.to_dict() == before


@pytest.mark.parametrize('label,mode', [('Start the lesson', 'lesson'), ('Open Case Library', 'library'),
                                      ('Open Algorithm Explorer', 'explorer')])
def test_overview_actions_open_the_correct_workspace_and_overview_is_always_accessible(label, mode):
    page, repo = mount()
    view = click_nav(page, 'Method Library')
    before = deepcopy(repo.data.to_dict())
    button = next(c for c in walk(view) if isinstance(c, ft.TextButton) and c.content == label)
    button.on_click(None)
    assert view.mode == mode and view.viewer.algorithm is not None
    view.section_buttons['overview'].on_click(None)
    assert view.mode == 'overview'
    assert view.section_buttons['overview'].style.bgcolor != view.section_buttons[mode].style.bgcolor
    assert repo.data.to_dict() == before


def test_subset_shortcuts_clear_conflicting_filters_and_select_a_case_in_that_subset():
    page, repo = mount()
    view = click_nav(page, 'Method Library')
    before = deepcopy(repo.data.to_dict())
    for subset, count in (('U/U', 54), ('U/D', 108), ('D/U', 108), ('D/D', 108)):
        view.search.value, view.status_filter.value, view.favorites.value = 'no-match', 'learned', True
        button = next(c for c in walk(view) if isinstance(c, ft.OutlinedButton) and c.content == f'{subset} · {count} cases')
        button.on_click(None)
        assert view.mode == 'library' and view.subset.value == subset
        assert len(view.filtered_cases()) == count and view.cases[view.selected_case].subset == subset
        view._set_mode('overview')
    assert repo.data.to_dict() == before


@pytest.mark.parametrize('width,height', [(1400, 760), (1000, 430), (600, 400), (366, 570), (280, 380)])
def test_overview_and_its_navigation_fit_the_viewport_with_a_scrollable_body(width, height):
    page, _ = mount(width=width)
    view = click_nav(page, 'Method Library')
    view.set_viewport(width, height)
    assert view.header.height + view.spacing + view.body.height <= height
    assert isinstance(view.body.controls[0], ft.ListView)
    assert view.body.controls[0].height == view.body.height
    assert view.scheme_picker.width <= width
    assert not any(isinstance(c, AlgorithmCube) for c in walk(view))
    assert len(view.section_buttons) == 4


def test_overview_progress_refreshes_from_saved_records_and_navigation_cancels_playback():
    page, repo = mount()
    view = click_nav(page, 'Method Library')
    view._set_mode('library')
    repo.data.corner_case_library[view.selected_case] = CornerCaseRecord(status='learned', favorite=True)
    view.viewer.playing = True
    token = view.viewer._token
    click_nav(page, 'Timer')
    assert not view.viewer.playing and view.viewer._token > token
    assert click_nav(page, 'Method Library') is view
    view._set_mode('overview')
    assert '1 / 378 learned' in text_values(view) and '1 favorites' in text_values(view)


@pytest.mark.parametrize('duration,minimum_frames', [(.3, 18), (.6, 36), (1.2, 72)])
def test_3d_turns_publish_more_frames_with_easing_and_keep_the_requested_duration(duration, minimum_frames):
    cube = AlgorithmCube()
    cube.load(parse_algorithm('R'))
    cube.speed.value = str(duration)
    clock, fractions = [0.0], []
    async def sleep(delay): clock[0] += delay
    def redraw(update=True):
        if cube._moving is not None: fractions.append(cube._fraction)
    with patch('ui.components.algorithm_cube.time.perf_counter', side_effect=lambda: clock[0]), \
         patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep), patch.object(cube, '_redraw', redraw):
        asyncio.run(cube._play(cube._token, 1))
    assert len(fractions) >= minimum_frames - 1
    assert fractions == sorted(fractions) and fractions[-1] == 1
    assert fractions[0] < 1 / minimum_frames  # eased start
    assert clock[0] == pytest.approx(duration)
    assert cube.index == 1 and cube._moving is None and not cube.playing


def test_slow_rendering_skips_stale_frames_without_stretching_a_turn_or_replaying_after_seek():
    cube = AlgorithmCube()
    cube.load(parse_algorithm('R U'))
    clock, published = [0.0], []
    async def sleep(delay): clock[0] += delay
    def redraw(update=True):
        if cube._moving is not None:
            published.append(cube._fraction)
            clock[0] += .045
    with patch('ui.components.algorithm_cube.time.perf_counter', side_effect=lambda: clock[0]), \
         patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep), patch.object(cube, '_redraw', redraw):
        asyncio.run(cube._play(cube._token, 1))
    assert 5 < len(published) < 20
    assert clock[0] <= .6 + .045
    assert cube.index == 1 and cube._moving is None and cube._fraction == 0
    assert published[-1] > .95  # the exact next state replaces the final partial frame
    cube.seek(0)
    original_token = cube._token
    async def seek_while_waiting(delay): cube.seek(2)
    with patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=seek_while_waiting), \
         patch.object(cube, '_redraw') as redraw:
        asyncio.run(cube._play(original_token, 2))
    assert cube.index == 2 and cube._moving is None
    assert redraw.call_count == 1  # only the requested seek publishes


def test_interpolated_frames_update_only_the_canvas_and_reuse_move_captions():
    cube = AlgorithmCube()
    cube.load(parse_algorithm('R U'))
    captions = cube.move_text.spans
    cube.playing, cube._moving, cube._fraction = True, 'R', .4
    with patch.object(cube, '_page', return_value=object()), \
         patch.object(cube.canvas, 'update') as canvas_update, patch.object(cube, 'update') as full_update:
        cube._redraw()
    canvas_update.assert_called_once()
    full_update.assert_not_called()
    assert cube.move_text.spans is captions


def test_restarting_a_finished_algorithm_publishes_the_first_move_before_animation():
    cube = AlgorithmCube()
    cube.load(parse_algorithm('R U'))
    cube.seek(2)
    assert cube.counter.value == '2 / 2'
    page = SimpleNamespace(run_task=Mock())
    with patch.object(cube, '_page', return_value=page), patch.object(cube, 'update') as full_update:
        cube._toggle()
    assert cube.index == 0 and cube.counter.value == '0 / 2'
    assert cube.move_text.spans[0].style.weight == ft.FontWeight.BOLD
    assert cube.playing and cube.play_button.icon == ft.Icons.PAUSE
    full_update.assert_called_once()
    page.run_task.assert_called_once()
