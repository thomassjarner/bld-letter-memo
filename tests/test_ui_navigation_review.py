"""Human navigation and secondary-control flows without changing saved training data."""
from copy import deepcopy
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
import pytest

from test_gold_scrambles import GOLD_TESTS, make_gold_scheme
from test_navigation import click_nav, mount, no_client_mount, text_values, walk
from ui import app


def page_menu(page):
    assert page.root.controls[1].visible
    return next(c for c in walk(page.root.controls[1]) if isinstance(c, ft.PopupMenuButton))


@pytest.mark.parametrize('style,width', [('top_tabs',320),('top_tabs',800),('top_tabs',1080),('compact_sidebar',390)])
def test_compact_navigation_reaches_every_page_and_identifies_the_active_destination_without_changing_preferences(style, width):
    page, repo = mount(style,width)
    before = deepcopy(repo.data.to_dict())
    assert page.root.controls[1].height <= 64
    for label, _ in app.DESTINATIONS:
        menu = page_menu(page)
        assert [item.data for item in menu.items] == [name for name,_ in app.DESTINATIONS]
        next(item for item in menu.items if item.data == label).on_click(None)
        current = next(c for c in walk(page.root.controls[1]) if getattr(c,'key',None) == 'current_destination')
        assert current.value == label
        selected = next(i for i in page_menu(page).items if i.data == label)
        assert selected.content.controls[-1].visible
    assert repo.data.to_dict() == before
    page.width=1440;page.on_resize(None)
    assert page.root.controls[2].visible == (style=='compact_sidebar')


def test_readable_sidebar_keeps_settings_outside_the_scrolling_destinations_and_popout_still_works():
    page, repo = mount('compact_sidebar')
    sidebar=page.root.controls[2]
    assert sidebar.visible
    settings=next(c for c in sidebar.content.controls if isinstance(c,ft.TextButton) and c.tooltip=='Settings')
    assert settings.visible and '\n' not in settings.content.controls[1].value
    settings.on_click(None)
    assert page.root.controls[0].content.dark_mode_switch is not None
    page,repo=mount('popout',width=390)
    before=deepcopy(repo.data.to_dict())
    page.root.controls[4].content.on_click(None)
    assert page.root.controls[3].visible
    next(c for c in walk(page.root.controls[3]) if isinstance(c,ft.TextButton) and c.tooltip=='Timer').on_click(None)
    assert page.root.controls[0].content.mode=='timer' and not page.root.controls[3].visible
    assert repo.data.to_dict()==before


@pytest.mark.parametrize('destination',['Timer','Practice'])
def test_dismissing_navigation_returns_focus_to_keyboard_training_without_recording_or_resetting_an_attempt(destination):
    page,repo=mount(width=390)
    tool=click_nav(page,destination);before=deepcopy(repo.data.to_dict())
    if destination=='Timer':
        tool.holding_space=tool.armed=True
        with patch.object(tool,'_focus_keyboard_listener') as focus:
            page_menu(page).on_cancel(None)
        assert focus.called and tool.active and not tool.holding_space and not tool.armed
        tool.running=True;tool.started_at=123.0
        with patch.object(tool,'_focus_keyboard_listener'):
            page_menu(page).on_cancel(None)
        assert tool.running and tool.started_at==123.0
        tool.running=False
    else:
        tool.open_progressive();run=SimpleNamespace(phase='memo');tool.progressive.run=run
        with patch.object(tool.progressive,'_focus') as focus:
            page_menu(page).on_cancel(None)
        focus.assert_called_once_with(False)
        assert tool.progressive.run is run and tool.progressive.active
        tool.progressive.run=None
    assert repo.data.to_dict()==before


def test_home_quick_actions_open_the_existing_timer_and_method_library_without_showing_tools_on_home():
    page,repo=mount()
    home=page.root.controls[0].content;before=deepcopy(repo.data.to_dict())
    assert not any(isinstance(c,(ft.TextField,ft.Dropdown,ft.KeyboardListener)) for c in walk(home))
    next(c for c in walk(home) if isinstance(c,ft.FilledButton) and c.content=='Open Timer').on_click(None)
    timer=page.root.controls[0].content;listener=timer.keyboard_listener
    home=click_nav(page,'Home')
    next(c for c in walk(home) if isinstance(c,ft.OutlinedButton) and c.content=='Method Library').on_click(None)
    assert page.root.controls[0].content.mode=='overview'
    assert click_nav(page,'Timer') is timer and timer.keyboard_listener is listener
    assert repo.data.to_dict()==before


@pytest.mark.parametrize('width',[280,390,700])
def test_method_workspace_picker_exposes_all_six_sections_and_retains_the_current_mode(width):
    page,repo=mount(width=width)
    view=click_nav(page,'Method Library');before=deepcopy(repo.data.to_dict())
    assert view.section_menu in view.header.controls
    assert len(view.section_menu.options)==6
    for option in view.section_menu.options:
        view.section_menu.value=option.key
        view.section_menu.on_select(SimpleNamespace(control=view.section_menu))
        assert view.mode==option.key and view.section_menu.value==option.key
        assert view.header.height + view.spacing + view.body.height <= view.height
    assert repo.data.to_dict()==before


@pytest.mark.parametrize('width,height',[(280,320),(390,570),(600,650)])
def test_mobile_dictionary_filters_have_readable_fields_and_keep_the_list_scrollable(width,height):
    page,repo=mount()
    repo.data.global_words={'AB':'apple','AC':'carrot'};repo.data.pair_ratings={'AB':5,'AC':2}
    pairs=click_nav(page,'Letter Pairs');pairs.set_viewport(width,height)
    before=deepcopy(repo.data.to_dict());scroll=pairs.rows_view
    assert pairs.filter_button.visible and pairs.rows_view.height>24
    assert pairs.filters_panel.height < 204
    with patch('ui.pages.letter_pairs_page.show_themed_dialog') as show, patch.object(type(pairs),'update'):
        pairs.filter_button.on_click(None)
        dialog=pairs._filters_dialog
        assert show.call_args.args[1] is dialog and dialog.scrollable
        controls=dialog.content.content.controls
        fields=[c for c in controls if isinstance(c,ft.Dropdown)]
        assert [f.label for f in fields]==['Letter scheme','Status','Sort by rating']
        assert all(f.width is None for f in fields)
        fields[2].value='highest';fields[2].on_select(SimpleNamespace(control=fields[2]))
        assert pairs.grade_sort.value=='highest' and pairs._word_fields[0].value=='apple'
        assert pairs.rows_view is scroll and '1 filter active'==pairs.filter_button.tooltip
        fake=SimpleNamespace(pop_dialog=Mock())
        with patch.object(type(pairs),'page',property(lambda self:fake)):
            pairs._reset_filters()
        assert pairs.grade_sort.value=='default' and pairs._filters_dialog is None
    assert repo.data.to_dict()==before


def test_rename_is_secondary_and_cancel_or_invalid_names_never_write_stickers_or_preferences():
    page,repo=mount()
    s=make_gold_scheme();repo.data.schemes[s.name]=s;repo.data.active_scheme=s.name
    original_name=s.name
    view=click_nav(page,'Letter Schemes')
    before=deepcopy(repo.data.to_dict());stickers=tuple(view._sticker_order)
    assert view.rename_field not in list(walk(view.body_scroll))
    with patch('ui.pages.letter_schemes_page.show_themed_dialog'),patch.object(type(view),'update'):
        view._open_rename()
        assert view._rename_dialog and view.rename_field.value==s.name and view._focused_sticker is None
        fake=SimpleNamespace(pop_dialog=Mock())
        with patch.object(type(view),'page',property(lambda self:fake)),patch.object(view.rename_field,'update'):
            view.rename_field.value='   ';view._confirm_rename()
            assert view.rename_field.error_text and repo.data.to_dict()==before
            view._close_rename()
        assert tuple(view._sticker_order)==stickers and repo.data.to_dict()==before
        view._open_rename();view.rename_field.value='Renamed scheme'
        with patch.object(type(view),'page',property(lambda self:fake)):
            view._confirm_rename()
    assert repo.data.active_scheme=='Renamed scheme'
    assert repo.data.schemes['Renamed scheme'].to_dict()==before['schemes'][original_name]
    assert tuple(view._sticker_order)==stickers


def test_memo_identifies_the_active_scheme_and_the_words_button_matches_its_actual_mode():
    page,repo=mount()
    memo=click_nav(page,'Scramble Memo')
    assert memo.setup_scheme_button.visible
    memo.setup_scheme_button.on_click(None)
    assert page.root.controls[0].content.first_scheme_field is not None
    scheme=make_gold_scheme();repo.data.schemes[scheme.name]=scheme;repo.data.active_scheme=scheme.name
    memo=click_nav(page,'Scramble Memo');before=deepcopy(repo.data.to_dict())
    assert scheme.name in memo.scheme_context.value and 'White up / Green front' in memo.scheme_context.value
    assert not memo.setup_scheme_button.visible and not memo.trace_diagnostics.visible
    memo.scramble.value=GOLD_TESTS[0]['scramble']
    with patch.object(type(memo),'update'):
        memo.generate(None);result=memo.last_result
        assert result and memo.trace_diagnostics.visible and not memo.error.visible
        memo.toggle_button.on_click(None)
        assert memo.show_words and memo.toggle_button.content=='Show letters' and memo.last_result is result
        memo.toggle_button.on_click(None)
        assert not memo.show_words and memo.toggle_button.content=='Show words'
    assert repo.data.to_dict()==before


def test_ready_practice_modes_are_direct_actions_and_planned_modes_are_secondary():
    page,repo=mount();practice=click_nav(page,'Practice')
    planned=next(c for c in walk(practice) if isinstance(c,ft.ExpansionTile))
    assert not planned.expanded and {'Delayed Recall','Letter Pair Drill'} <= set(text_values(planned))
    assert all(c.disabled for c in walk(planned) if isinstance(c,ft.TextButton))
    before=deepcopy(repo.data.to_dict())
    next(c for c in walk(practice) if isinstance(c,ft.TextButton) and c.content=='Open Progressive Memo').on_click(None)
    assert practice.mode=='progressive' and repo.data.to_dict()==before


def test_settings_backup_and_rating_controls_are_present_and_layout_does_not_write_data():
    page,repo=mount();before=deepcopy(repo.data.to_dict());settings=click_nav(page,'Settings')
    assert isinstance(settings.controls[1],ft.ResponsiveRow)
    backup=settings.controls[1].controls[1]
    export=next(c for c in walk(backup) if isinstance(c,ft.FilledButton) and c.content=='Export backup')
    import_button=next(c for c in walk(backup) if isinstance(c,ft.OutlinedButton) and c.content=='Import backup')
    assert isinstance(settings.rating_palette_area,ft.ResponsiveRow)
    assert len(settings.rating_palette_area.controls)==repo.data.rating_color_levels
    picker=SimpleNamespace(save_file=AsyncMock(return_value='backup.json'),pick_files=AsyncMock(return_value=[]))
    with patch('flet.FilePicker',return_value=picker),patch.object(type(settings),'update'):
        asyncio.run(export.on_click(None))
        assert json.loads(picker.save_file.call_args.kwargs['src_bytes'])==before
        asyncio.run(import_button.on_click(None))
        assert settings._pending_import is None
    assert repo.data.to_dict()==before
