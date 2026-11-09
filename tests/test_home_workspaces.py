"""Home deep links must reuse the existing workspaces and preserve training data."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import flet as ft
import pytest

from data.color_themes import LIGHT_THEMES
from test_gold_scrambles import GOLD_TESTS
from test_corner_trainer import trainer_scheme
from test_navigation import click_nav, mount, no_client_mount, text_values, walk
from test_progressive_memo import letter_scheme
from test_theme_contrast import contrast
from ui.design import build_theme
from ui.feature_icons import FEATURE_NAMES, feature_icon
from ui.pages.home_page import build_home
from ui.theme_colors import apply_palette


def launch(page, key):
    home = click_nav(page, "Home")
    home.launch_buttons[key].on_click(None)
    return page.root.controls[0].content


def test_home_groups_keep_setup_analysis_learning_and_practice_distinct():
    home = build_home(lambda name: None)
    expected = {
        "setup": {"Set up your memo", "Set up your letter scheme", "Build your letter pairs"},
        "analyze": {"Analyze a scramble", "Scramble Memo", "Scramble walkthrough"},
        "learn": {"Learning material", "Method Library", "Algorithm Playground"},
        "practice": {"Practice", "Blind Timer", "Progressive Memo", "3-style corner trainer"},
    }
    for key, labels in expected.items():
        group = next(c for c in walk(home) if c.key == f"home_group_{key}")
        assert labels <= set(text_values(group))
        buttons = [c for c in walk(group) if isinstance(c, ft.TextButton)]
        assert len(buttons) == (3 if key == "practice" else 2)
        assert all(button.on_click and button.tooltip for button in buttons)
    assert home.scroll == ft.ScrollMode.AUTO
    assert not any(isinstance(c, (ft.TextField, ft.Dropdown, ft.KeyboardListener)) for c in walk(home))


@pytest.mark.parametrize("style", ["top_tabs", "compact_sidebar", "popout"])
@pytest.mark.parametrize("width", [280, 390, 900, 1440])
def test_home_deep_links_reuse_existing_tools_in_every_navigation_style(style, width):
    page, repo = mount(style, width)
    before = deepcopy(repo.data.to_dict())
    memo = launch(page, "memo")
    assert memo is click_nav(page, "Scramble Memo")
    method = launch(page, "walkthrough")
    assert method.mode == "walkthrough" and method.active
    walkthrough = method.walkthrough
    walkthrough.scramble.value = "R U R' U'"
    assert click_nav(page, "Method Library") is method
    assert launch(page, "walkthrough").walkthrough is walkthrough
    assert walkthrough.scramble.value == "R U R' U'"
    assert launch(page, "library") is method and method.mode == "overview"
    next(c for c in walk(method) if isinstance(c, ft.TextButton) and c.content == "Open walkthrough").on_click(None)
    assert method.mode == "walkthrough" and method.walkthrough is walkthrough
    assert walkthrough.scramble.value == "R U R' U'"
    assert launch(page, "playground") is method and method.mode == "explorer"
    assert launch(page, "library") is method and method.mode == "overview"
    timer = launch(page, "timer")
    listener = timer.keyboard_listener
    assert timer is click_nav(page, "Timer") and timer.active
    practice = launch(page, "progressive")
    assert practice.mode == "progressive" and practice.active and practice.progressive.active
    assert not timer.active and not method.active
    practice.progressive.back_callback()
    assert practice.mode == "menu" and not practice.progressive.active
    next(c for c in walk(practice) if isinstance(c, ft.TextButton) and c.content == "Open Progressive Memo").on_click(None)
    assert practice.mode == "progressive"
    assert launch(page, "timer") is timer and timer.keyboard_listener is listener
    assert launch(page, "trainer") is method and method.mode == "trainer"
    trainer = method.trainer
    assert trainer.active and not timer.active and not practice.progressive.active
    assert launch(page, "library") is method
    next(c for c in walk(method) if isinstance(c, ft.TextButton) and c.content == "Open corner trainer").on_click(None)
    assert method.mode == "trainer" and method.trainer is trainer
    assert launch(page, "schemes") is click_nav(page, "Letter Schemes")
    assert launch(page, "pairs") is click_nav(page, "Letter Pairs")
    assert repo.data.to_dict() == before


@pytest.mark.parametrize("width", [280, 390, 1440])
def test_home_trainer_shortcut_retains_filters_and_an_existing_recall_session(width):
    page, repo = mount(width=width)
    scheme = trainer_scheme()
    repo.data.schemes = {scheme.name: scheme}
    repo.data.active_scheme = scheme.name
    method = launch(page, "trainer")
    trainer = method.trainer
    trainer.first_target.value, trainer.second_target.value = "UBL", "UBR"
    trainer._filter_changed()
    before = deepcopy(repo.data.to_dict())
    with patch("core.corner_trainer.solve_facelets", return_value=None):
        trainer._start()
    assert trainer.session and not trainer.busy
    session, card = trainer.session, trainer.session.card
    trainer._show()
    trainer._grade(True)
    assert session.answered and len(session.results) == 1
    home = click_nav(page, "Home")
    assert not trainer.active
    page.width = 390 if width == 1440 else 1440
    page.on_resize(None)
    assert home.launch_buttons["trainer"].visible
    assert launch(page, "trainer") is method
    assert method.trainer is trainer and trainer.active and trainer.view == "recall"
    assert trainer.session is session and session.card is card
    assert session.answered and len(session.results) == 1
    assert (trainer.first_target.value, trainer.second_target.value) == ("UBL", "UBR")
    assert repo.data.to_dict() == before


def test_home_shortcut_preserves_progressive_resize_and_navigation_cancel_behavior():
    page, repo = mount(width=390)
    scheme = letter_scheme()
    repo.data.schemes = {scheme.name: scheme}
    repo.data.active_scheme = scheme.name
    hub = launch(page, "progressive")
    mode = hub.progressive
    mode.current_scramble = GOLD_TESTS[1]["scramble"]
    mode._start()
    mode._finish_intro(mode._generation, 0)
    mode._next()
    run, index, plan = mode.run, mode.run.prompt_index, mode.run.plan
    before = deepcopy(repo.data.to_dict())
    page.width = 1440
    page.on_resize(None)
    assert mode.active and mode.run is run and mode.run.prompt_index == index and mode.run.plan is plan
    home = click_nav(page, "Home")
    assert not mode.active and mode.run is None  # Existing unfinished-attempt cancellation.
    buttons = dict(home.launch_buttons)
    page.width = 280
    page.on_resize(None)
    assert home.launch_buttons == buttons
    assert launch(page, "progressive") is hub
    assert mode.active and mode.run is None and mode.phase == "ready"
    assert mode.current_scramble == plan.scramble
    assert repo.data.to_dict() == before


@pytest.mark.parametrize("theme", [*LIGHT_THEMES, "dark"])
def test_custom_icon_colors_follow_the_palette_with_readable_focus_and_selection(theme):
    dark = theme == "dark"
    key = "classic_teal" if dark else theme
    colors = build_theme(dark, key).color_scheme
    for name in FEATURE_NAMES:
        icon = feature_icon(name, size=18)
        apply_palette(icon, dark, key)
        original = [shape.paint.color for shape in icon.shapes]
        assert original
        for color in original:
            if color == colors.surface_container_lowest:  # Negative play triangle.
                assert contrast(color, colors.tertiary) >= 4.5
            else:
                for background in (colors.surface, colors.surface_container_low,
                                   colors.primary_container):
                    assert contrast(color, background) >= 4.5, (name, theme, color, background)
        apply_palette(icon, not dark, "rose")
        apply_palette(icon, dark, key)
        assert [shape.paint.color for shape in icon.shapes] == original
        selected = feature_icon(name, size=18, selected=True)
        apply_palette(selected, dark, key)
        for shape in selected.shapes:
            if shape.paint.color != colors.surface_container_lowest:
                assert contrast(shape.paint.color, colors.primary_container) >= 4.5


def test_new_icon_paints_and_home_links_recolor_after_live_theme_changes():
    page, repo = mount()
    home = page.root.controls[0].content
    glyph = next(c for c in walk(home) if c.key == "feature_icon_timer")
    original = [shape.paint.color for shape in glyph.shapes]
    settings = click_nav(page, "Settings")
    settings.light_theme_dropdown.on_select(SimpleNamespace(control=SimpleNamespace(value="lavender")))
    assert repo.data.light_theme == "lavender"
    assert [shape.paint.color for shape in glyph.shapes] != original
    button = next(c for c in walk(page.root) if isinstance(c, ft.IconButton) and c.tooltip == "Switch to dark mode")
    button.on_click(None)
    colors = build_theme(True).color_scheme
    assert glyph.shapes[0].paint.color == colors.primary
    assert launch(page, "walkthrough").mode == "walkthrough"
