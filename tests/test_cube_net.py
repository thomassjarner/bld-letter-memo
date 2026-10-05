"""Cube geometry and data interchange with the existing scheme editor."""
from collections import Counter
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import patch

import flet as ft
import pytest

from core.cube_definitions import CATEGORY_PIECES, CATEGORY_STICKER_ORDER, find_piece_for_sticker
from data.models import AppData
from ui.components.cube_net import (COLOR_NAMES, FACE_COLORS, NET_ROWS, CubeNetEditor,
                                     face_stickers, orientation_colors)
from ui.theme_colors import apply_palette
from test_navigation import click_nav, mount, no_client_mount, walk
from test_progressive_memo import letter_scheme
from test_theme_contrast import contrast


def open_editor():
    page, repo = mount()
    scheme = letter_scheme()
    repo.data.schemes = {scheme.name: scheme}
    repo.data.active_scheme = scheme.name
    return page, repo, click_nav(page, 'Letter Schemes')


def change_editor(view, value):
    view.editor_dropdown.value = value
    view.editor_dropdown.on_select(SimpleNamespace(control=view.editor_dropdown))


def test_six_faces_place_each_canonical_sticker_once_without_mirroring_back_or_down():
    matrices = face_stickers()
    assert matrices == {
        'U': ('UBL', 'UB', 'UBR', 'UL', 'U', 'UR', 'UFL', 'UF', 'UFR'),
        'L': ('LUB', 'LU', 'LUF', 'LB', 'L', 'LF', 'LDB', 'LD', 'LDF'),
        'F': ('FUL', 'FU', 'FUR', 'FL', 'F', 'FR', 'FDL', 'FD', 'FDR'),
        'R': ('RUF', 'RU', 'RUB', 'RF', 'R', 'RB', 'RDF', 'RD', 'RDB'),
        'B': ('BUR', 'BU', 'BUL', 'BR', 'B', 'BL', 'BDR', 'BD', 'BDL'),
        'D': ('DFL', 'DF', 'DFR', 'DL', 'D', 'DR', 'DBL', 'DB', 'DBR'),
    }
    all_stickers = [s for face in matrices.values() for s in face]
    assert len(all_stickers) == 54 and len(set(all_stickers)) == 54
    for category in ('corners', 'edges'):
        assert Counter(s for s in all_stickers if len(s) == (3 if category == 'corners' else 2)) == Counter(CATEGORY_STICKER_ORDER[category])
    assert NET_ROWS[0][1] == 'U' and NET_ROWS[1] == ('L', 'F', 'R', 'B') and NET_ROWS[2][1] == 'D'
    # Each touching edge and corner must identify the same physical cubie.
    for left, right in (('L', 'F'), ('F', 'R'), ('R', 'B'), ('B', 'L')):
        for a, b in ((2, 0), (5, 3), (8, 6)):
            category = 'edges' if a == 5 else 'corners'
            assert find_piece_for_sticker(matrices[left][a], CATEGORY_PIECES[category]) == find_piece_for_sticker(matrices[right][b], CATEGORY_PIECES[category])
    assert set(matrices['F'][7]) == set(matrices['D'][1])
    assert set(matrices['U'][7]) == set(matrices['F'][1])


def test_net_face_colors_follow_all_24_memo_orientations():
    opposite = {'W': 'Y', 'Y': 'W', 'G': 'B', 'B': 'G', 'R': 'O', 'O': 'R'}
    seen = set()
    for up in opposite:
        for front in opposite:
            if front in {up, opposite[up]}:
                continue
            colors = orientation_colors(up, front)
            assert colors['U'] == up and colors['F'] == front
            assert colors['D'] == opposite[up] and colors['B'] == opposite[front]
            assert colors['L'] == opposite[colors['R']]
            assert set(colors.values()) == set(opposite)
            seen.add(tuple(colors[face] for face in 'ULFRBD'))
    assert len(seen) == 24
    assert orientation_colors('W', 'G')['R'] == 'R'
    assert orientation_colors('Y', 'G')['R'] == 'O'
    assert orientation_colors('G', 'R')['R'] == 'W'
    assert orientation_colors('bad', 'bad') == orientation_colors('W', 'G')


@pytest.mark.parametrize('category', ['corners', 'edges'])
def test_only_selected_category_is_editable_and_all_buffer_stickers_are_locked(category):
    _, repo, view = open_editor()
    view.selected_category = category
    change_editor(view, 'cube')
    editor = view._cube_editor
    cat = getattr(repo.data.schemes['gold'], category)
    locked = CATEGORY_PIECES[category][cat.buffer_piece]
    assert set(view._sticker_fields) == set(CATEGORY_STICKER_ORDER[category]) - locked
    for sticker, cell in editor.cell_controls.items():
        assert isinstance(cell, ft.TextField) == (sticker in view._sticker_fields)
    assert 'Buffer sticker' in editor.cell_controls[cat.buffer_sticker].tooltip
    assert [s for s in CATEGORY_STICKER_ORDER[category] if s not in locked] == view._sticker_order
    # Imported schemes need not contain literal BUFFER markers to stay locked.
    for sticker in locked:
        cat.stickers[sticker] = 'Z'
    view._refresh_body()
    assert not locked.intersection(view._sticker_fields)


def test_edits_autosave_and_switching_editors_preserves_letters_and_other_data():
    _, repo, view = open_editor()
    before = deepcopy(repo.data.to_dict())
    assert repo.data.letter_scheme_editor == 'cards' and view._cube_editor is None
    change_editor(view, 'cube')
    assert repo.data.schemes['gold'].to_dict() == before['schemes']['gold']
    assert isinstance(view._cube_editor, CubeNetEditor)
    editor, fields = view._cube_editor, view._sticker_fields
    sticker = view._sticker_order[0]
    field = fields[sticker]
    field.value = 'ø'
    field.on_change(SimpleNamespace(control=field))
    assert repo.data.schemes['gold'].edges.stickers[sticker] == 'Ø'
    assert field.value == 'Ø' and view._cube_editor is editor and view._sticker_fields is fields
    assert view._focused_sticker == view._sticker_order[1]
    change_editor(view, 'cards')
    assert view._sticker_fields[sticker].value == 'Ø' and view._cube_editor is None
    card_field = view._sticker_fields[sticker]
    card_field.value = 'Q'
    card_field.on_change(SimpleNamespace(control=card_field))
    change_editor(view, 'cube')
    assert view._sticker_fields[sticker].value == 'Q'
    after = repo.data.to_dict()
    for key, value in before.items():
        if key not in ('letter_scheme_editor', 'schemes'):
            assert after[key] == value
    assert after['schemes']['gold']['corners'] == before['schemes']['gold']['corners']


def test_buffer_switch_and_backspace_use_existing_scheme_editing_behavior():
    _, repo, view = open_editor()
    change_editor(view, 'cube')
    with patch.object(type(view), 'update'):
        view._set_buffer('UR')
    assert not {'UR', 'RU'}.intersection(view._sticker_fields)
    assert {'DF', 'FD'}.issubset(view._sticker_fields)
    assert repo.data.schemes['gold'].edges.buffer_sticker == 'UR'
    first, second = view._sticker_order[:2]
    view._sticker_fields[first].value = 'Z'
    view._sticker_fields[first].on_change(SimpleNamespace(control=view._sticker_fields[first]))
    view._sticker_fields[second].value = ''
    view._on_sticker_focus(second)
    view.handle_keyboard_event(SimpleNamespace(key='Backspace'))
    assert first not in repo.data.schemes['gold'].edges.stickers
    assert view._sticker_fields[first].value == '' and view._focused_sticker == first


def test_preferences_and_categories_keep_the_chosen_editor():
    _, _, view = open_editor()
    change_editor(view, 'cube')
    with patch.object(type(view), 'update'):
        view._on_tab_change(SimpleNamespace(control=SimpleNamespace(selected_index=2)))
        assert view.selected_category == 'preferences' and not view._sticker_fields
        assert view.editor_dropdown not in list(walk(view.body_scroll))
        view._on_tab_change(SimpleNamespace(control=SimpleNamespace(selected_index=1)))
    assert view.selected_category == 'corners' and view._cube_editor is not None
    assert view.editor_dropdown.value == 'cube'


def test_resizing_keeps_fields_square_and_scrolling_accessible_without_rebuilding():
    _, repo, view = open_editor()
    change_editor(view, 'cube')
    editor, fields, scroll = view._cube_editor, view._sticker_fields, view.body_scroll
    snapshot = deepcopy(repo.data.to_dict())
    for width, height in ((1400, 808), (920, 700), (366, 570)):
        view.set_viewport(width, height)
        assert view._cube_editor is editor and view._sticker_fields is fields and view.body_scroll is scroll
        assert all(cell.width == cell.height and cell.width >= 36 for cell in editor.cell_controls.values())
        assert editor.net_scroll.width <= width and scroll.scroll == ft.ScrollMode.ALWAYS
        if width < 760:
            assert isinstance(view.controls[1], ft.Column)
            assert editor.net_scroll.scroll == ft.ScrollMode.ALWAYS
        else:
            assert isinstance(view.controls[1], ft.Row)
    assert repo.data.to_dict() == snapshot


def test_duplicate_letters_and_light_dark_colors_remain_readable():
    _, repo, view = open_editor()
    scheme = repo.data.schemes['gold']
    scheme.edges.stickers.update({'UB': 'Z', 'UF': 'Z'})
    scheme.memo_up, scheme.memo_front = 'G', 'R'
    change_editor(view, 'cube')
    assert any(isinstance(c, ft.Text) and (c.value or '').startswith('Duplicate letters: Z:') for c in walk(view._cube_editor))
    for dark, expected in ((True, '#F0F4F3'), (False, '#182B25'), (True, '#F0F4F3')):
        repo.data.dark_mode = dark
        apply_palette(view, dark)
        for field in view._sticker_fields.values():
            assert field.color == expected and contrast(field.color, field.bgcolor) >= 4.5
            assert contrast(field.label_style.color, field.bgcolor) >= 4.5
        for face in 'ULFRBD':
            center = view._cube_editor.cell_controls[face]
            assert contrast(center.content.color, center.bgcolor) >= 4.5
            assert COLOR_NAMES[orientation_colors('G', 'R')[face]] in center.tooltip
    for bg, fg in FACE_COLORS.values():
        assert contrast(fg, bg) >= 4.5


def test_editor_choice_persists_in_backups_and_old_data_defaults_to_face_cards():
    _, repo, view = open_editor()
    old = repo.data.to_dict()
    old.pop('letter_scheme_editor')
    old['version'] = 14
    migrated = AppData.from_dict(json.loads(json.dumps(old)))
    assert migrated.letter_scheme_editor == 'cards'
    for key, value in old.items():
        if key != 'version':
            assert migrated.to_dict()[key] == value
    change_editor(view, 'cube')
    loaded = AppData.from_dict(json.loads(json.dumps(repo.data.to_dict())))
    assert loaded.letter_scheme_editor == 'cube'
    assert loaded.schemes['gold'].to_dict() == repo.data.schemes['gold'].to_dict()
    with patch.object(view.state, '_save') as save:
        view.state.set_letter_scheme_editor('invalid')
        save.assert_not_called()
    for invalid in ('invalid', None, [], {}):
        assert AppData.from_dict({'letter_scheme_editor': invalid}).letter_scheme_editor == 'cards'
