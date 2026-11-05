"""Saved palette choices, contrast, and controls rebuilt after a theme switch."""
import asyncio
from copy import deepcopy
from dataclasses import asdict
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
import pytest

from data.color_themes import DEFAULT_LIGHT_THEME, LIGHT_THEMES
from data.json_repository import JsonAppDataRepository
from data.models import AppData, CURRENT_VERSION, PracticeSolve
from data.shared_preferences_repository import SharedPreferencesAppDataRepository
from test_gold_scrambles import make_gold_scheme
from test_navigation import MemoryRepository, PageHarness, click_nav, mount, no_client_mount, walk
from test_resolved_theme import toggle
from test_theme_contrast import contrast
from ui import app
from ui.design import TEXT_ROLES, build_theme
from ui.state import AppState
from ui.theme_colors import apply_palette, show_themed_dialog


def select(settings, key):
    settings.light_theme_dropdown.value = key
    settings.light_theme_dropdown.on_select(SimpleNamespace(control=settings.light_theme_dropdown))


@pytest.mark.parametrize('key', LIGHT_THEMES)
def test_light_theme_text_and_actions_have_contrast_on_all_surface_levels(key):
    theme = build_theme(light_theme=key)
    colors = theme.color_scheme
    surfaces = [getattr(colors, role) for role in ('surface', 'surface_container_lowest',
        'surface_container_low', 'surface_container', 'surface_container_high', 'surface_container_highest')]
    for role in TEXT_ROLES:
        for background in surfaces:
            assert contrast(getattr(theme.text_theme, role).color, background) >= 4.5
    for foreground in ('primary', 'secondary', 'tertiary', 'error', 'on_surface_variant'):
        for background in surfaces:
            assert contrast(getattr(colors, foreground), background) >= 4.5, (key, foreground, background)
    for foreground, background in (('on_primary', 'primary'), ('on_primary_container', 'primary_container'),
                                    ('on_secondary_container', 'secondary_container')):
        assert contrast(getattr(colors, foreground), getattr(colors, background)) >= 4.5
    # Light preferences never alter the existing dark palette or text roles.
    assert asdict(build_theme(True, key).color_scheme) == asdict(build_theme(True).color_scheme)


def test_old_and_unknown_preferences_keep_all_other_backup_data_and_default_to_classic_teal():
    data = AppData()
    scheme = make_gold_scheme()
    data.schemes[scheme.name] = scheme
    data.active_scheme = scheme.name
    data.global_words = {'AB': 'Apple'}
    data.pair_aliases = {'AB': 'ØB'}
    data.pair_ratings = {'AB': 4.0}
    data.pair_rating_versions = {'AB': 1}
    data.practice_solves = [PracticeSolve(2630, "R U R'", plus2=True)]
    old = data.to_dict()
    old.pop('light_theme')
    for value in (None, '', 'unknown-theme', [], {}, False):
        restored = AppData.from_dict(dict(old, light_theme=value))
        assert restored.light_theme == DEFAULT_LIGHT_THEME
        result = restored.to_dict()
        result.pop('light_theme')
        assert result == old
    assert AppData.from_dict(old).light_theme == DEFAULT_LIGHT_THEME
    assert CURRENT_VERSION == 18


def test_selected_theme_survives_file_browser_and_backup_roundtrips_without_other_changes(tmp_path):
    repo = JsonAppDataRepository(tmp_path / 'workspace.json')
    state = AppState(repo)
    state.data.global_words = {'AB': 'Kept'}
    state.data.rating_color_hexes = ['#123456', '#FF00FF', '#654321']
    state.data.practice_solves = [PracticeSolve(2630, 'R U2 F')]
    state.data.dark_mode = True
    before = deepcopy(state.data.to_dict())
    for key in LIGHT_THEMES:
        assert state.set_light_theme(key)
        # The default may already be selected; saving it is deliberately a no-op.
        repo.save(state.data)
        decoded, _ = SharedPreferencesAppDataRepository._decode(json.dumps(state.data.to_dict()))
        for restored in (repo.load(), AppData.from_dict(state.data.to_dict()), decoded):
            assert restored.light_theme == key
            assert {k:v for k,v in restored.to_dict().items() if k != 'light_theme'} == {
                k:v for k,v in before.items() if k != 'light_theme'}
    with patch.object(repo, 'save') as save:
        assert not state.set_light_theme('invalid')
        assert not state.set_light_theme([])
        assert state.set_light_theme(state.data.light_theme)
        save.assert_not_called()


@pytest.mark.parametrize('key', LIGHT_THEMES)
def test_settings_updates_every_destination_then_dark_mode_returns_to_the_saved_palette(key):
    page, repo = mount()
    timer = click_nav(page, 'Timer')
    listener = timer.keyboard_listener
    settings = click_nav(page, 'Settings')
    before = deepcopy(repo.data.to_dict())
    select(settings, key)
    expected = build_theme(light_theme=key).color_scheme
    assert page.theme.color_scheme.primary == expected.primary
    assert page.bgcolor == expected.surface_container_low
    assert settings.light_theme_preview.bgcolor == expected.surface_container_low
    assert not settings.light_theme_dropdown.disabled
    for label, _ in app.DESTINATIONS:
        view = click_nav(page, label)
        view.before_update()
        assert any(c.color == expected.on_surface for c in walk(view) if isinstance(c, ft.Text)), label
        for control in walk(view):
            if isinstance(control, (ft.TextField, ft.Dropdown)):
                assert control.color == expected.on_surface
    toggle(page, True)
    assert repo.data.light_theme == key and page.bgcolor == '#17201C'
    assert 'light mode' in settings.light_theme_hint.value.lower()
    # A preference can be selected while dark mode stays dark.
    select(settings, key)
    assert page.theme_mode == ft.ThemeMode.DARK and page.bgcolor == '#17201C'
    toggle(page, False)
    assert page.bgcolor == expected.surface_container_low
    assert click_nav(page, 'Timer') is timer and timer.keyboard_listener is listener
    assert {k:v for k,v in repo.data.to_dict().items() if k != 'light_theme'} == {
        k:v for k,v in before.items() if k != 'light_theme'}


def test_restarting_app_loads_the_saved_palette_before_any_navigation():
    repo = MemoryRepository()
    repo.data.light_theme = 'rose'
    page = PageHarness()
    with patch.object(app.SharedPreferencesAppDataRepository, 'create', AsyncMock(return_value=repo)):
        asyncio.run(app.main(page))
    assert page.theme.color_scheme.primary == LIGHT_THEMES['rose'].colors['primary']
    assert page.bgcolor == LIGHT_THEMES['rose'].colors['surface_container_low']
    settings = click_nav(page, 'Settings')
    assert settings.light_theme_dropdown.value == 'rose'


def test_new_dialogs_use_the_selected_palette_and_keep_custom_rating_colors():
    page, repo = mount()
    settings = click_nav(page, 'Settings')
    select(settings, 'lavender')
    pairs = click_nav(page, 'Letter Pairs')
    shown = SimpleNamespace(show_dialog=Mock(), pop_dialog=Mock())
    with patch.object(type(pairs), 'page', property(lambda self: shown)):
        pairs._open_filters()
    dialog = shown.show_dialog.call_args.args[0]
    colors = LIGHT_THEMES['lavender'].colors
    for field in dialog.content.content.controls:
        if isinstance(field, ft.Dropdown):
            assert field.color == colors['on_surface']
            assert field.label_style.color == colors['on_surface_variant']
    custom = ft.Container(bgcolor='#FF00FF')
    dialog = ft.AlertDialog(title=ft.Text('Confirm'), content=custom,
                           actions=[ft.FilledButton('Save'), ft.TextButton('Cancel')])
    show_themed_dialog(shown, dialog, False, 'lavender')
    assert dialog.title.color == colors['on_surface']
    assert dialog.actions[0].style.bgcolor[ft.ControlState.DEFAULT] == colors['primary']
    assert custom.bgcolor == '#FF00FF'


def test_playback_caption_updates_inherit_the_palette_without_changing_cube_or_execution():
    from ui.components.algorithm_cube import AlgorithmCube
    viewer = AlgorithmCube()
    viewer.load('[R,U]')
    viewer.seek(1)
    initial, states = deepcopy(viewer.canvas.shapes), deepcopy(viewer.states)
    for key in ('cobalt', 'warm_sand', 'rose', 'classic_teal'):
        colors = LIGHT_THEMES[key].colors
        apply_palette(viewer, False, key)
        viewer._render_caption()
        viewer._update()
        assert viewer.move_text.color == colors['on_surface']
        assert viewer.counter.color == colors['on_surface_variant']
        assert any(s.style.bgcolor == colors['primary_container'] for s in viewer.move_text.spans)
        assert viewer.index == 1 and viewer.states == states and viewer.canvas.shapes == initial
    apply_palette(viewer, True, 'rose')
    viewer.dark_mode = True
    viewer._render_caption(); viewer._update()
    assert viewer.move_text.color == '#F0F4F3'


def test_import_updates_saved_theme_selector_preview_and_page_but_old_backups_restore_classic():
    page, repo = mount()
    settings = click_nav(page, 'Settings')
    for key in ('cobalt', None):
        backup = repo.data.to_dict()
        backup['global_words'] = {'AB': 'Kept on import'}
        if key is None:
            backup.pop('light_theme')
        else:
            backup['light_theme'] = key
        settings._pending_import = ('backup.json', json.dumps(backup).encode())
        with patch.object(type(settings), 'page', property(lambda self: SimpleNamespace(update=Mock()))):
            settings._confirm_import(None)
        selected = key or DEFAULT_LIGHT_THEME
        assert repo.data.light_theme == settings.light_theme_dropdown.value == selected
        assert settings.light_theme_preview.bgcolor == page.bgcolor == LIGHT_THEMES[selected].colors['surface_container_low']
        assert repo.data.global_words == {'AB': 'Kept on import'}
