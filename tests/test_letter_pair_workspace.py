"""Bounded scrolling must keep every filtered pair and editing behavior available."""
from itertools import product
from types import SimpleNamespace

import flet as ft
from data.models import LetterScheme, CategoryScheme
from test_navigation import mount, click_nav, walk, no_client_mount


def seed_words(repo):
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    repo.data.global_words = {a + b: f'word {a}{b}' for a, b in product(letters, repeat=2) if a != b}
    repo.data.pair_aliases = {'AB': 'ØB'}
    repo.data.pair_ratings = {'AB': 5, 'AZ': 2}


def test_compact_filters_leave_a_bounded_scrolling_pair_list():
    page, repo = mount()
    seed_words(repo)
    pairs = click_nav(page, 'Letter Pairs')
    assert pairs.filters_panel.height == 128
    assert pairs.rows_view.scroll == ft.ScrollMode.ALWAYS
    assert pairs.rows_view.height > 450
    assert pairs.rows_view.width == pairs._viewport[0]
    assert pairs.content_area.scroll is None
    assert pairs.scheme_filter in pairs.filters_area.controls[0].controls
    assert pairs.status_filter in pairs.filters_area.controls[0].controls
    assert pairs.grade_sort in pairs.filters_area.controls[0].controls
    for checkbox in (pairs.search_pairs, pairs.search_words):
        # Explicit rectangular dimensions scale both the checkbox and its label.
        assert checkbox.width is None and checkbox.height is None
        assert checkbox.visual_density == ft.VisualDensity.COMPACT
    assert len(pairs._word_fields) == 25
    assert pairs._word_fields[-1].value == 'word AZ'


def test_large_filtered_result_set_keeps_all_pairs_accessible():
    page, repo = mount()
    seed_words(repo)
    snapshot = repo.data.to_dict()
    pairs = click_nav(page, 'Letter Pairs')
    pairs.grade_sort.value = 'highest'
    pairs.refresh(update=False)
    assert len(pairs._word_fields) == 650
    assert len(pairs.rows_view.controls) == 325
    assert pairs._word_fields[0].value == 'word AB'
    assert any(f.value == 'word ZY' for f in pairs._word_fields)
    assert pairs.prev_group.disabled and pairs.next_group.disabled
    assert repo.data.to_dict() == snapshot


def test_resizing_uses_one_or_two_columns_and_keeps_the_scroll_control():
    page, repo = mount()
    seed_words(repo)
    snapshot = repo.data.to_dict()
    pairs = click_nav(page, 'Letter Pairs')
    scroll = pairs.rows_view
    for width, height, columns, compact in ((1400, 808, 2, False), (920, 808, 1, False), (366, 570, 1, True)):
        pairs.set_viewport(width, height)
        assert pairs.rows_view is scroll
        assert pairs._table_columns == columns and pairs._compact_cells == compact
        assert len(pairs._word_fields) == 25
        assert pairs.rows_view.height > 100
        assert (pairs.filters_panel.height + 32 + 28 + pairs.rows_view.height + 24) == pairs.content_area.height
        assert pairs.heading.height + pairs.tabbar.height + pairs.content_area.height + 16 == height
    assert repo.data.to_dict() == snapshot


def test_typing_does_not_rebuild_fields_and_commit_keeps_the_word():
    page, repo = mount()
    repo.data.global_words = {'AB': '', 'AC': 'carrot'}
    pairs = click_nav(page, 'Letter Pairs')
    scroll, field = pairs.rows_view, pairs._word_fields[0]
    field.value = 'apple'
    field.on_change(SimpleNamespace(control=field))
    assert repo.data.global_words['AB'] == 'apple'
    assert pairs._word_fields[0] is field and pairs.rows_view is scroll
    field.on_blur(SimpleNamespace(control=field))
    assert repo.data.global_words['AB'] == 'apple'
    assert pairs.rows_view is scroll
    assert any(isinstance(c, ft.Dropdown) and c.value == '__none__' for c in walk(scroll))


def test_alias_and_rating_edits_keep_their_underlying_pair():
    page, repo = mount()
    repo.data.global_words = {'AB': 'apple', 'AC': 'carrot'}
    pairs = click_nav(page, 'Letter Pairs')
    pairs.set_viewport(366, 570)
    pairs._rating_changed('AB', '5')
    pairs._edit_pair_alias('AB')
    alias = next(c for c in walk(pairs.rows_view) if isinstance(c, ft.TextField) and c.tooltip == 'Underlying pair: AB')
    alias.value = 'ÅB'
    alias.on_submit(SimpleNamespace(control=alias))
    assert repo.data.pair_aliases['AB'] == 'ÅB'
    assert repo.data.pair_ratings['AB'] == 5
    assert repo.data.global_words['AB'] == 'apple'
    pairs.search_field.value = 'ÅB'
    pairs.refresh(update=False)
    assert len(pairs._word_fields) == 1 and pairs._word_fields[0].value == 'apple'


def test_stats_scrolls_and_fills_the_width_after_resizing():
    page, repo = mount()
    repo.data.schemes['My scheme'] = LetterScheme(
        name='My scheme', edges=CategoryScheme(buffer_piece='DF', stickers={'UR': 'A', 'UF': 'B', 'UL': 'C'}))
    repo.data.active_scheme = 'My scheme'
    repo.data.global_words = {'AB': 'apple', 'AC': 'carrot'}
    repo.data.pair_ratings = {'AB': 5, 'AC': 3}
    pairs = click_nav(page, 'Letter Pairs')
    pairs.selected_view = 'stats'
    pairs.refresh(update=False)
    scroll = pairs.stats_scroll
    for width in (720, 1000, 1400):
        pairs.set_viewport(width, 800)
        assert pairs.stats_scroll is scroll
        assert scroll.width == width and scroll.height == 702
        assert scroll.controls[0].width == width
        assert scroll.scroll == ft.ScrollMode.ALWAYS
    pairs._toggle_alpha_sort(None)
    assert pairs.stats_scroll is scroll


def test_no_match_message_is_visible_without_mutating_the_dictionary():
    page, repo = mount()
    repo.data.global_words = {'AB': 'apple'}
    snapshot = repo.data.to_dict()
    pairs = click_nav(page, 'Letter Pairs')
    pairs.search_field.value = 'ZZ'
    pairs.refresh(update=False)
    assert not pairs._word_fields
    assert any(isinstance(c, ft.Text) and c.value == 'No matching letter pairs.' for c in walk(pairs.rows_view))
    assert repo.data.to_dict() == snapshot
