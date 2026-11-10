"""Timer routes, view-only sorting and semantic success colors across all palettes."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
import pytest
from data.color_themes import LIGHT_THEMES
from data.models import PracticeSolve
from test_navigation import click_nav, mount, no_client_mount, walk
from test_theme_contrast import contrast
from ui.design import build_theme
from ui.pages.practice_page import PracticePage
from ui.theme_colors import apply_palette, success_color


def timer_with_solves(solves):
    page, repo = mount()
    repo.data.practice_solves = solves
    return page, repo, click_nav(page, 'Timer')


def row_ids(timer):
    return [next(c.value for c in walk(row) if isinstance(c, ft.Text) and c.value.startswith('#'))
            for row in timer.history.controls]


def sample_solves():
    return [PracticeSolve(1000, 'R'), PracticeSolve(850, 'U', plus2=True), PracticeSolve(950, 'D'),
            PracticeSolve(300, 'F', dnf=True), PracticeSolve(1000, 'L'), PracticeSolve(2000, 'B')]


def test_sort_buttons_toggle_both_directions_and_keep_chronology_statistics_and_data():
    _, repo, timer = timer_with_solves(sample_solves())
    before = deepcopy(repo.data.to_dict()); stats = timer.stats_text.value
    listener, history = timer.keyboard_listener, timer.history
    assert row_ids(timer) == ['#6','#5','#4','#3','#2','#1']
    for button, expected, label in [
        (timer.time_sort_button, ['#3','#1','#5','#2','#6','#4'], 'Fastest'),
        (timer.time_sort_button, ['#4','#6','#2','#1','#5','#3'], 'Slowest'),
        (timer.date_sort_button, ['#6','#5','#4','#3','#2','#1'], 'Newest'),
        (timer.date_sort_button, ['#1','#2','#3','#4','#5','#6'], 'Oldest'),
        (timer.time_sort_button, ['#3','#1','#5','#2','#6','#4'], 'Fastest'),
    ]:
        button.on_click(None)
        assert row_ids(timer) == expected and button.content == label
        assert timer.stats_text.value == stats and repo.data.to_dict() == before
        assert timer.keyboard_listener is listener and timer.history is history
    assert timer.date_sort_button.content == 'Newest'


def test_fastest_sort_ranks_the_entire_session_before_pagination_and_resize_keeps_the_order():
    page, repo, timer = timer_with_solves([PracticeSolve(100+i, f'R {i}') for i in range(123)])
    before = deepcopy(repo.data.to_dict())
    timer.time_sort_button.on_click(None)
    assert row_ids(timer)[0] == '#1' and len(row_ids(timer)) == 50
    timer._load_older_solves();assert len(row_ids(timer)) == 100
    timer._load_older_solves();assert len(row_ids(timer)) == 123
    assert row_ids(timer)[-1] == '#123' and not timer.older_solves_button.visible
    listener = timer.keyboard_listener
    for width,height in [(390,700),(280,400),(1440,900)]:
        page.width,page.height = width,height;page.on_resize(None)
        assert timer.history_sort == 'fastest' and row_ids(timer)[0] == '#1'
        assert timer.keyboard_listener is listener
        assert timer._timer_stage.height > 0 and timer.history.height > 0
    assert repo.data.to_dict() == before


def test_sorted_history_routes_copy_and_deletion_reference_the_original_solve():
    _, repo, timer = timer_with_solves(sample_solves())
    timer.time_sort_button.on_click(None)
    row = timer.history.controls[0]
    memo, analysis = [], []
    timer.open_memo_callback = memo.append;timer.open_corner_walkthrough_callback = analysis.append
    for label in ['Scramble Memo · saved solve','3-style corner analysis · saved solve']:
        next(c for c in walk(row) if isinstance(c,ft.IconButton) and c.tooltip==label).on_click(None)
    assert memo == ['D'] and analysis == ['D']
    with patch.object(timer,'_copy_time_and_scramble') as copy:
        row.content.controls[0].controls[1].on_click(None)
        assert copy.call_args.args[0] is repo.data.practice_solves[2]
    next(c for c in walk(row) if isinstance(c,ft.IconButton) and c.tooltip=='Delete solve').on_click(None)
    assert [s.scramble for s in repo.data.practice_solves] == ['R','U','F','L','B']


def test_current_and_last_solve_have_separate_named_analysis_routes_and_original_feature_icons():
    _, repo, timer = timer_with_solves(sample_solves())
    memo, analysis = [], []
    timer.open_memo_callback = memo.append;timer.open_corner_walkthrough_callback = analysis.append
    timer.current_scramble='R U';timer.last_solve_index=2;timer._safe_update()
    timer.scramble_memo_button.on_click(None);timer.corner_walkthrough_button.on_click(None)
    timer.memo_button.on_click(None);timer.corner_analysis_button.on_click(None)
    assert memo == ['R U','D'] and analysis == ['R U','D']
    for button, name in [(timer.scramble_memo_button,'memo'),(timer.corner_walkthrough_button,'walkthrough'),
                         (timer.memo_button,'memo'),(timer.corner_analysis_button,'walkthrough')]:
        assert button.icon.key == 'feature_icon_'+name
    assert timer.memo_button.content == 'Scramble Memo'
    assert timer.corner_analysis_button.content == '3-style corner analysis'
    timer.last_solve_index=None;timer._safe_update();assert timer.corner_analysis_button.disabled
    timer.running=True;timer._safe_update()
    assert timer.scramble_memo_button.disabled and timer.corner_walkthrough_button.disabled
    assert timer.corner_analysis_button.disabled
    timer.running=False


@pytest.mark.parametrize('palette',LIGHT_THEMES)
@pytest.mark.parametrize('dark',[False,True])
def test_armed_timer_and_fastest_history_stay_green_with_contrast_in_every_theme(palette,dark):
    _, repo, timer = timer_with_solves([PracticeSolve(950,'R'),PracticeSolve(1500,'U'),PracticeSolve(200,'D',dnf=True)])
    repo.data.dark_mode=dark;repo.data.light_theme=palette
    timer.holding_space=True;timer.active=True
    with patch('ui.pages.practice_page.asyncio.sleep',new=AsyncMock()):
        asyncio.run(timer._arm_after_delay())
    timer.before_update()
    expected=success_color(dark)
    assert timer.armed and timer.timer_text.color == expected
    best=next(c for c in walk(timer.history) if isinstance(c,ft.Text) and c.value=='9.50')
    assert best.color == expected
    normal=next(c for c in walk(timer.history) if isinstance(c,ft.Text) and c.value=='15.00')
    assert normal.color != expected
    for alternate in LIGHT_THEMES:
        apply_palette(timer,dark,alternate)
        assert timer.timer_text.color == best.color == expected
        scheme=build_theme(dark,alternate).color_scheme
        for role in ('surface','surface_container_lowest','surface_container_low','surface_container',
                     'surface_container_high','surface_container_highest'):
            assert contrast(expected,getattr(scheme,role)) >= 4.5
    r,g,b=(int(expected[i:i+2],16) for i in (1,3,5));assert g>r and g>b
    runner=SimpleNamespace(run_task=Mock())
    with patch.object(PracticePage,'page',property(lambda self:runner)),patch.object(timer,'_safe_update'):
        timer._on_key_up(SimpleNamespace(key='Space'))
    assert timer.running and not timer.holding_space
    timer.before_update();assert timer.timer_text.color == build_theme(dark,palette).color_scheme.on_surface
    timer.running=False
