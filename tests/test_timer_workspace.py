"""Timer resizing and history access must preserve live timing and stored solves."""
from types import SimpleNamespace
from unittest.mock import patch

import flet as ft
from data.models import PracticeSolve
from ui.pages.practice_page import PracticePage
from test_navigation import mount, click_nav, walk, no_client_mount


def test_desktop_has_large_timer_and_bounded_scrollable_history():
    page, _ = mount()
    timer = click_nav(page, 'Timer')
    assert isinstance(timer._main_region.controls[0], ft.Row)
    assert timer._timer_stage.height >= 400
    assert timer.timer_text.size >= 100
    assert timer.history.scroll == ft.ScrollMode.ALWAYS
    assert timer.history.height > 300
    assert timer.history.height + 100 == timer.history_panel.height
    row = timer._scramble_panel.content
    assert timer.scramble_text in row.controls
    assert row.controls[1].controls == [timer.previous_scramble_button, timer.new_scramble_button]


def test_resize_keeps_listener_history_and_active_solve():
    page, _ = mount()
    timer = click_nav(page, 'Timer')
    listener, history = timer.keyboard_listener, timer.history
    timer.running = True
    timer.started_at = 123.45
    timer.current_scramble = 'R U R\' U\''
    for width, height in ((1360, 768), (900, 900), (390, 700), (1440, 800)):
        page.width, page.height = width, height
        page.on_resize(None)
        assert timer.keyboard_listener is listener and timer.history is history
        assert timer.running and timer.started_at == 123.45
        assert timer.current_scramble == 'R U R\' U\''
        assert timer.history.height > 0
        assert timer._timer_stage.height > 0
        _, available = timer._viewport
        assert 44 + timer._scramble_panel.height + 24 + timer._main_region.height <= available
        if not timer._timer_layout_wide:
            assert timer._timer_workspace.height + 12 + timer.history_panel.height == timer._main_region.height
            assert timer._stats_button.visible
    timer.running = False


def test_all_old_solves_are_reachable_without_changing_saved_data():
    page, repo = mount()
    solves = [PracticeSolve(centiseconds=100 + i, scramble=f'R U{i}') for i in range(123)]
    repo.data.practice_solves = solves
    snapshot = repo.data.to_dict()
    timer = click_nav(page, 'Timer')
    history = timer.history
    assert len(history.controls) == 50 and timer.older_solves_button.visible
    assert '#123' in [c.value for c in walk(history.controls[0]) if isinstance(c, ft.Text)]
    timer._load_older_solves()
    assert len(history.controls) == 100
    timer._load_older_solves()
    assert len(history.controls) == 123
    assert not timer.older_solves_button.visible
    assert '#1' in [c.value for c in walk(history.controls[-1]) if isinstance(c, ft.Text)]
    assert repo.data.to_dict() == snapshot
    assert timer.history is history


def test_old_history_actions_reference_the_correct_solve():
    page, repo = mount()
    repo.data.practice_solves = [PracticeSolve(centiseconds=100 + i, scramble=f'R U{i}') for i in range(75)]
    timer = click_nav(page, 'Timer')
    timer._load_older_solves()
    oldest_row = timer.history.controls[-1]
    clicked = []
    timer.open_memo_callback = clicked.append
    next(c for c in walk(oldest_row) if isinstance(c, ft.IconButton) and c.tooltip == 'Take to Scramble Memo').on_click(None)
    assert clicked == ['R U0']
    next(c for c in walk(oldest_row) if isinstance(c, ft.IconButton) and c.tooltip == 'Delete solve').on_click(None)
    assert len(repo.data.practice_solves) == 74
    assert repo.data.practice_solves[0].scramble == 'R U1'


def test_keyboard_stop_and_penalties_after_resizing():
    page, repo = mount()
    timer = click_nav(page, 'Timer')
    runner = SimpleNamespace(run_task=lambda *args: None)
    with patch.object(PracticePage, 'page', property(lambda self: runner)), \
         patch.object(timer, '_safe_update', lambda: None), \
         patch.object(timer, '_focus_keyboard_listener', lambda: None):
        timer._start_timer(10.0)
        page.width, page.height = 900, 720
        page.on_resize(None)
        with patch('ui.pages.practice_page.time.monotonic', return_value=12.34):
            timer._on_key_down(SimpleNamespace(key='Space'))
        assert not timer.running
        assert repo.data.practice_solves[-1].centiseconds == 234
        timer._mark_last('plus2')
        assert repo.data.practice_solves[-1].plus2
        assert timer.timer_text.value == '4.34+'
        timer._mark_last('dnf')
        assert repo.data.practice_solves[-1].dnf
        timer._mark_last('ok')
        assert not repo.data.practice_solves[-1].dnf and not repo.data.practice_solves[-1].plus2
        assert timer.timer_text.value == '2.34'


def test_brand_is_an_unboxed_noninteractive_mark():
    page, _ = mount()
    marks = [c for c in walk(page.root) if c.key == 'brand_mark']
    assert marks and all(isinstance(c, ft.Icon) for c in marks)
    assert all(c.icon == ft.Icons.VIEW_IN_AR_OUTLINED for c in marks)
    assert all(not getattr(c, 'on_click', None) for c in marks)
