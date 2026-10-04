"""Presentation regressions without a browser or a real persistence service."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import flet as ft
import pytest
from flet.controls.base_control import BaseControl

from data.models import AppData
from ui import app
from ui.design import build_theme
from ui.pages.home_page import build_home
from ui.pages.practice_page import PracticePage


@pytest.fixture(autouse=True)
def no_client_mount():
    # This suite checks Python control wiring, not client focus/rendering.
    # Flet 0.86 raises on .page for unmounted controls; model them as detached.
    with patch.object(BaseControl, "page", property(lambda self: None)):
        yield


class MemoryRepository:
    def __init__(self):
        self.data = AppData()

    def load(self):
        return self.data

    def save(self, data):
        self.data = data


class PageHarness:
    width = 1440
    height = 900

    def add(self, root):
        self.root = root

    def update(self):
        pass


def walk(control):
    yield control
    for item in getattr(control, "controls", []) or []:
        yield from walk(item)
    child = getattr(control, "content", None)
    if isinstance(child, ft.Control):
        yield from walk(child)


def text_values(control):
    return [c.value for c in walk(control) if isinstance(c, ft.Text)]


def mount(style="top_tabs", width=1440):
    page = PageHarness()
    page.width = width
    repo = MemoryRepository()
    repo.data.navigation_style = style
    with patch.object(app.SharedPreferencesAppDataRepository, "create", AsyncMock(return_value=repo)):
        asyncio.run(app.main(page))
    return page, repo


def click_nav(page, label):
    candidates = [c for c in walk(page.root) if isinstance(c, ft.TextButton) and c.tooltip == label]
    assert candidates, label
    candidates[0].on_click(None)
    return page.root.controls[0].content


def test_home_has_routes_and_no_embedded_tools():
    routed = []
    home = build_home(routed.append)
    assert not any(isinstance(c, (ft.TextField, ft.Dropdown, ft.KeyboardListener, PracticePage)) for c in walk(home))
    for button in (c for c in walk(home) if isinstance(c, ft.TextButton)):
        button.on_click(None)
    assert routed == ["Letter Schemes", "Letter Pairs", "Practice", "Scramble Memo", "Settings"]


def test_nav_order_and_home_default():
    page, _ = mount()
    assert [label for label, _ in app.DESTINATIONS] == ["Home", "Letter Schemes", "Letter Pairs", "Scramble Memo", "Practice", "Timer", "Settings"]
    assert "Build your memo.\nTrain your recall." in text_values(page.root.controls[0].content)
    for label, _ in app.DESTINATIONS:
        assert click_nav(page, label) is not None


def test_timer_is_separate_and_reused_through_both_routes():
    page, _ = mount()
    timer = click_nav(page, "Timer")
    listener = timer.keyboard_listener
    assert timer.active and timer.mode == "timer"
    practice = click_nav(page, "Practice")
    assert practice is not timer and practice.mode == "menu"
    assert not timer.active and not practice.active
    practice.open_timer_callback()
    assert page.root.controls[0].content is timer
    assert timer.keyboard_listener is listener and timer.active
    timer.open_practice_callback()
    assert page.root.controls[0].content is practice
    assert not timer.active


def test_timer_to_memo_and_return_preserve_timer_control():
    page, _ = mount()
    timer = click_nav(page, "Timer")
    scramble = "R U R' U'"
    timer.open_memo_callback(scramble)
    memo = page.root.controls[0].content
    assert memo.scramble.value == scramble
    assert not timer.active
    assert click_nav(page, "Timer") is timer


def test_navigation_styles_and_narrow_fallback_do_not_rewrite_preference():
    for style in ("top_tabs", "compact_sidebar", "popout"):
        page, repo = mount(style)
        assert len([c for c in walk(page.root) if isinstance(c, ft.TextButton) and c.tooltip == "Home"]) == 3
        assert repo.data.navigation_style == style
    page, repo = mount("compact_sidebar", width=390)
    assert page.root.controls[1].visible
    assert not page.root.controls[2].visible
    assert repo.data.navigation_style == "compact_sidebar"
    page.width = 1440
    page.on_resize(None)
    assert page.root.controls[2].visible


def test_theme_toggle_persists_and_syncs_settings():
    page, repo = mount()
    button = next(c for c in walk(page.root) if isinstance(c, ft.IconButton) and c.tooltip == "Switch to dark mode")
    button.on_click(None)
    assert repo.data.dark_mode and page.theme_mode == ft.ThemeMode.DARK
    settings = click_nav(page, "Settings")
    assert settings.dark_mode_switch.value
    settings._dark_mode_changed(SimpleNamespace(control=SimpleNamespace(value=False)))
    assert not repo.data.dark_mode and page.theme_mode == ft.ThemeMode.LIGHT
    for dark in (False, True):
        colors = build_theme(dark).color_scheme
        assert colors.primary and colors.surface and colors.on_surface and colors.outline_variant
