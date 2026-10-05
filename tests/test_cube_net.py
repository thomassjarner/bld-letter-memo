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
from ui.components.cube_net import (COLOR_NAMES, CUBE_STICKER_ORDER, FACE_COLORS, NET_ROWS, MIN_STICKER_SIZE, STICKER_BORDER,
                                   CubeNetEditor, face_stickers, orientation_colors)
from ui.components.sticker_grid import FaceCardsEditor, MIN_CARD_STICKER_SIZE
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
def test_cube_edits_both_categories_and_locks_each_buffer_from_either_prior_tab(category):
    _, repo, view = open_editor()
    view.selected_category = category
    change_editor(view, 'cube')
    editor = view._cube_editor
    scheme = repo.data.schemes['gold']
    locked = set().union(*(CATEGORY_PIECES[c][getattr(scheme, c).buffer_piece] for c in ('edges', 'corners')))
    assert set(view._sticker_fields) == set(CUBE_STICKER_ORDER) - locked
    for sticker, cell in editor.cell_controls.items():
        assert isinstance(cell.content, ft.Semantics) == (sticker in view._sticker_fields)
        if sticker in view._sticker_fields:
            assert cell.content.content is view._sticker_fields[sticker]
    for cat in (scheme.edges, scheme.corners):
        assert 'Buffer sticker' in editor.cell_controls[cat.buffer_sticker].tooltip
    assert [s for s in CUBE_STICKER_ORDER if s not in locked] == view._sticker_order
    # Imported schemes need not contain literal BUFFER markers to stay locked.
    for category in ('edges', 'corners'):
        cat = getattr(scheme, category)
        for sticker in CATEGORY_PIECES[category][cat.buffer_piece]:
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
    with patch.object(type(view), 'update'):
        view._on_tab_change(SimpleNamespace(control=SimpleNamespace(selected_index=1)))
    assert view.selected_category == 'corners'
    change_editor(view, 'cube')
    assert [tab.label for tab in view._category_tabs.content.tabs] == ['All stickers', 'Preferences']
    with patch.object(type(view), 'update'):
        view._on_tab_change(SimpleNamespace(control=SimpleNamespace(selected_index=1)))
        assert view.selected_category == 'preferences' and not view._sticker_fields
        assert view.editor_dropdown not in list(walk(view.body_scroll))
        view._on_tab_change(SimpleNamespace(control=SimpleNamespace(selected_index=0)))
    assert view.selected_category == 'corners' and view._cube_editor is not None
    assert view.editor_dropdown.value == 'cube'
    change_editor(view, 'cards')
    assert view.selected_category == 'corners'
    assert [tab.label for tab in view._category_tabs.content.tabs] == ['Edges', 'Corners', 'Preferences']


def test_resizing_keeps_fields_square_and_scrolling_accessible_without_rebuilding():
    _, repo, view = open_editor()
    change_editor(view, 'cube')
    editor, fields, scroll = view._cube_editor, view._sticker_fields, view.body_scroll
    snapshot = deepcopy(repo.data.to_dict())
    for width, height in ((1400, 808), (920, 700), (366, 570)):
        view.set_viewport(width, height)
        assert view._cube_editor is editor and view._sticker_fields is fields and view.body_scroll is scroll
        assert all(cell.width == cell.height and cell.width >= MIN_STICKER_SIZE for cell in editor.cell_controls.values())
        assert all(face.width == face.height for face in editor.face_controls.values())
        assert all(field.width == field.height for field in fields.values())
        assert editor.net_scroll.width <= width and scroll.scroll == ft.ScrollMode.ALWAYS
        if width < 760:
            assert isinstance(view.controls[1], ft.Column)
            assert editor.net_scroll.scroll == ft.ScrollMode.ALWAYS
        else:
            assert isinstance(view.controls[1], ft.Row)
    assert repo.data.to_dict() == snapshot


def test_height_only_resize_fits_all_six_faces_and_short_windows_keep_a_scroll_viewport():
    _, repo, view = open_editor()
    change_editor(view, 'cube')
    editor, fields, scroll = view._cube_editor, view._sticker_fields, view.body_scroll
    snapshot = deepcopy(repo.data.to_dict())
    sizes = []
    for height in (808, 660, 560):
        view.set_viewport(1400, height)
        assert view._cube_editor is editor and view._sticker_fields is fields and view.body_scroll is scroll
        assert view.controls[0] is view._editor_heading
        assert view.controls[0].height + scroll.height == height
        assert view.controls[1].height == scroll.height
        assert all(not c.wrap for c in scroll.controls[:3] if isinstance(c, ft.Row))
        # Include the actual fixed toolbar and help rows, padding, item gaps,
        # and a line for the existing status/error text, not just the net size.
        toolbar = sum(c.height for c in scroll.controls[:3])
        help_rows = editor.controls[0].height + editor.controls[2].height + 2 * editor.spacing
        occupied = toolbar + 20 + 4 * scroll.spacing + help_rows + editor.net_scroll.height + 18
        assert occupied <= scroll.height + 0.01
        assert editor.net_scroll.height == editor.net.height
        assert editor.net_scroll.scroll is None
        sizes.append(editor.cell_controls['UB'].width)
    assert sizes[0] > sizes[1] > sizes[2] >= MIN_STICKER_SIZE
    field = fields[view._sticker_order[0]]
    field.on_focus(SimpleNamespace(control=field))
    view.set_viewport(1400, 440)
    assert view._focused_sticker == view._sticker_order[0]
    assert editor.cell_controls['UB'].width == MIN_STICKER_SIZE
    assert scroll.height == 440 - view._editor_heading.height
    assert scroll.scroll == ft.ScrollMode.ALWAYS
    assert repo.data.to_dict() == snapshot
    change_editor(view, 'cards')
    assert view.controls[0] is view._editor_heading and view.body_scroll.height == 440 - view._editor_heading.height


def test_duplicate_letters_and_light_dark_colors_remain_readable():
    _, repo, view = open_editor()
    scheme = repo.data.schemes['gold']
    scheme.edges.stickers.update({'UB': 'Z', 'UF': 'Z'})
    scheme.corners.stickers.update({'UBR': 'Y', 'UFR': 'Y'})
    scheme.memo_up, scheme.memo_front = 'G', 'R'
    change_editor(view, 'cube')
    warning = next(c.value for c in walk(view._cube_editor) if isinstance(c, ft.Text) and (c.value or '').startswith('Duplicate letters'))
    assert 'Edges: Z:' in warning and 'Corners: Y:' in warning
    for dark in (True, False, True):
        repo.data.dark_mode = dark
        apply_palette(view, dark)
        for face in 'ULFRBD':
            center = view._cube_editor.cell_controls[face]
            assert center.content is None
            assert COLOR_NAMES[orientation_colors('G', 'R')[face]] in center.tooltip
            for sticker in face_stickers()[face]:
                cell = view._cube_editor.cell_controls[sticker]
                assert cell.bgcolor == center.bgcolor
                if len(sticker) == 1:
                    continue
                field = view._sticker_fields.get(sticker)
                text = field if field is not None else cell.content
                assert contrast(text.color, cell.bgcolor) >= 4.5
                if field is not None:
                    assert field.color == field.focused_color == field.cursor_color
                    assert field.focused_bgcolor == cell.bgcolor
    for bg, fg in FACE_COLORS.values():
        assert contrast(fg, bg) >= 4.5


def test_empty_filled_and_focused_stickers_keep_the_same_square_without_face_captions():
    _, repo, view = open_editor()
    change_editor(view, 'cube')
    editor, fields = view._cube_editor, view._sticker_fields
    first, second = view._sticker_order[:2]
    cells = dict(editor.cell_controls)
    geometry = {key: (cell.width, cell.height) for key, cell in cells.items()}
    for sticker, value in ((first, ''), (first, 'ø'), (second, '')):
        field, cell = fields[sticker], cells[sticker]
        field.on_focus(SimpleNamespace(control=field))
        assert view._focused_sticker == sticker
        assert cell.border.top.width == STICKER_BORDER
        assert cell.border.top.color == field.color
        field.value = value
        field.on_change(SimpleNamespace(control=field))
        field.on_blur(SimpleNamespace(control=field))
        assert cell.border.top.width == STICKER_BORDER
        assert cell.border.top.color == ft.Colors.TRANSPARENT
        assert view._cube_editor is editor and view._sticker_fields is fields
        assert editor.cell_controls == cells
        assert {key: (tile.width, tile.height) for key, tile in cells.items()} == geometry
        assert all(f.label is None and f.collapsed and f.fit_parent_size
                   and f.border == ft.InputBorder.NONE and not f.filled for f in fields.values())
        assert cell.width == field.width + 2 * STICKER_BORDER
    assert repo.data.schemes['gold'].edges.stickers[first] == 'Ø'
    # Centers are plain color tiles, with no letter or editable field.
    for face, panel in editor.face_controls.items():
        assert cells[face].content is None and face not in fields
        assert face in cells[face].tooltip
        assert len(panel.content.controls) == 3
        assert all(isinstance(row, ft.Row) and len(row.controls) == 3 for row in panel.content.controls)
        assert not any(isinstance(c, ft.Text) and c.value == f'{face} · {COLOR_NAMES[orientation_colors("W", "G")[face]]}'
                       for c in walk(panel))


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


def test_combined_cube_saves_each_category_and_backspace_crosses_category_boundaries():
    _, repo, view = open_editor()
    change_editor(view, 'cube')
    scheme, editor, fields = repo.data.schemes['gold'], view._cube_editor, view._sticker_fields
    snapshot = deepcopy(repo.data.to_dict())
    assert not any(isinstance(c, ft.Text) and (c.value or '').startswith('Duplicate letters') for c in walk(editor))
    assert {'UB', 'UBR', 'UL'} <= fields.keys()
    for sticker, value, category in (('UB', 'ø', 'edges'), ('UBR', 'å', 'corners')):
        field = fields[sticker]
        field.value = value
        field.on_change(SimpleNamespace(control=field))
        assert getattr(scheme, category).stickers[sticker] == value.upper()
        assert field.value == value.upper()
        assert view._focused_sticker == view._sticker_order[view._sticker_order.index(sticker) + 1]
        assert view._cube_editor is editor and view._sticker_fields is fields
    assert view.selected_category == 'edges'
    edges = deepcopy(scheme.edges.to_dict())
    fields['UL'].value = ''
    fields['UL'].on_focus(SimpleNamespace(control=fields['UL']))
    view.handle_keyboard_event(SimpleNamespace(key='Backspace'))
    assert 'UBR' not in scheme.corners.stickers
    assert fields['UBR'].value == '' and view._focused_sticker == 'UBR'
    assert scheme.edges.to_dict() == edges
    for sticker in ('DF', 'FD', 'UBL', 'LUB', 'BUL', 'U', 'unknown'):
        saved = deepcopy(repo.data.to_dict())
        view._set_letter(sticker, 'Q')
        assert repo.data.to_dict() == saved
    fields['UBR'].value = 'æ'
    fields['UBR'].on_change(SimpleNamespace(control=fields['UBR']))
    change_editor(view, 'cards')
    assert view._sticker_fields['UB'].value == 'Ø'
    with patch.object(type(view), 'update'):
        view._on_tab_change(SimpleNamespace(control=SimpleNamespace(selected_index=1)))
    assert view._sticker_fields['UBR'].value == 'Æ'
    change_editor(view, 'cube')
    assert view._sticker_fields['UB'].value == 'Ø' and view._sticker_fields['UBR'].value == 'Æ'
    loaded = AppData.from_dict(json.loads(json.dumps(repo.data.to_dict())))
    assert loaded.schemes['gold'].to_dict() == scheme.to_dict()
    for key, value in snapshot.items():
        if key != 'schemes':
            assert loaded.to_dict()[key] == value


def test_cube_has_independent_edge_and_corner_buffer_selectors():
    _, repo, view = open_editor()
    change_editor(view, 'cube')
    scheme = repo.data.schemes['gold']
    assert set(view._buffer_pickers) == {'edges', 'corners'}
    before_corners = deepcopy(scheme.corners.to_dict())
    with patch.object(type(view), 'update'):
        picker = view._buffer_pickers['edges']
        picker.value = 'UR'
        picker.on_select(SimpleNamespace(control=picker))
    assert scheme.corners.to_dict() == before_corners
    assert not {'UR', 'RU'}.intersection(view._sticker_fields)
    assert {'DF', 'FD'} <= view._sticker_fields.keys()
    before_edges = deepcopy(scheme.edges.to_dict())
    with patch.object(type(view), 'update'):
        picker = view._buffer_pickers['corners']
        picker.value = 'UFR'
        picker.on_select(SimpleNamespace(control=picker))
    assert scheme.edges.to_dict() == before_edges
    assert not {'UFR', 'RUF', 'FUR'}.intersection(view._sticker_fields)
    assert {'UBL', 'LUB', 'BUL'} <= view._sticker_fields.keys()
    assert view._buffer_pickers['edges'].value == 'UR'
    assert view._buffer_pickers['corners'].value == 'UFR'
    assert len(view._sticker_fields) == 43
    fields = view._sticker_fields
    for width in (1400, 366, 280):
        view.set_viewport(width, 650)
        assert view._sticker_fields is fields
        if view._buffer_toolbar.wrap:
            assert view._buffer_toolbar.height == 84
        else:
            assert sum(c.width for c in view._buffer_toolbar.controls) + 24 <= view.body_scroll.width - 20 + 0.01


@pytest.mark.parametrize('category', ['edges', 'corners'])
def test_face_cards_share_colored_square_inputs_and_responsive_compact_workspace(category):
    _, repo, view = open_editor()
    if category == 'corners':
        with patch.object(type(view), 'update'):
            view._on_tab_change(SimpleNamespace(control=SimpleNamespace(selected_index=1)))
    editor, fields, scroll = view._cards_editor, view._sticker_fields, view.body_scroll
    grid_children = editor.card_grid.controls
    scheme = repo.data.schemes['gold']
    assert isinstance(editor, FaceCardsEditor)
    locked = CATEGORY_PIECES[category][getattr(scheme, category).buffer_piece]
    assert set(fields) == set(CATEGORY_STICKER_ORDER[category]) - locked
    assert set(view._buffer_pickers) == {category}
    snapshot = deepcopy(repo.data.to_dict())
    for width, height in ((1400, 660), (920, 560), (366, 570), (280, 480)):
        view.set_viewport(width, height)
        assert view._cards_editor is editor and view._sticker_fields is fields and view.body_scroll is scroll
        assert view.controls[0] is view._editor_heading
        assert scroll.height > 0 and scroll.scroll == ft.ScrollMode.ALWAYS
        assert all(c.width == c.height and c.width >= MIN_CARD_STICKER_SIZE for c in editor.cell_controls.values())
        assert all(f.width == f.height for f in fields.values())
        assert editor.card_grid.controls is grid_children and len(grid_children) == 6
        assert all(card.width <= editor.card_grid.width for card in editor.face_controls.values())
        if width >= 760:
            occupied = sum(c.height for c in scroll.controls[:3]) + 20 + 4 * scroll.spacing + editor.extra_height + editor.card_grid.height + 18
            assert occupied <= scroll.height + 0.01
    assert repo.data.to_dict() == snapshot
    first, second = view._sticker_order[:2]
    field, cell = fields[first], editor.cell_controls[first]
    geometry = (cell.width, cell.height)
    field.on_focus(SimpleNamespace(control=field))
    field.value = 'ø'
    field.on_change(SimpleNamespace(control=field))
    field.on_blur(SimpleNamespace(control=field))
    assert getattr(scheme, category).stickers[first] == 'Ø'
    assert (cell.width, cell.height) == geometry and cell.content.content is field
    fields[second].value = ''
    view._on_sticker_focus(second)
    view.handle_keyboard_event(SimpleNamespace(key='Backspace'))
    assert first not in getattr(scheme, category).stickers
    assert fields[first].value == '' and view._focused_sticker == first
    for dark in (True, False, True):
        apply_palette(view, dark)
        for cell in editor.cell_controls.values():
            text = cell.content.content if isinstance(cell.content, ft.Semantics) else cell.content
            assert contrast(text.color, cell.bgcolor) >= 4.5
    change_editor(view, 'cube')
    assert {len(s) for s in view._sticker_fields} == {2, 3}
    change_editor(view, 'cards')
    assert set(view._sticker_fields) == set(CATEGORY_STICKER_ORDER[category]) - locked
