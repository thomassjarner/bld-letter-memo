"""Exact temporary sticker choices retrace memo without editing saved schemes."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

import flet as ft
import pytest

from core.cube_definitions import CATEGORY_PIECES, CATEGORY_STICKER_ORDER
from core.tracer import ScrambleTracer
from test_gold_scrambles import GOLD_TESTS
from test_navigation import click_nav, mount, no_client_mount, walk
from test_progressive_memo import letter_scheme


SCRAMBLE = GOLD_TESTS[1]['scramble']


@pytest.mark.parametrize('category', ['corners', 'edges'])
@pytest.mark.parametrize('mode', ['standard', 'rotated_parity', 'own_orientation'])
def test_exact_sticker_override_reuses_tracing_for_every_available_sticker(category, mode):
    scheme = letter_scheme()
    if mode != 'standard':
        scheme.memo_up, scheme.memo_front = 'Y', 'B'
        scheme.three_style_enabled = mode == 'rotated_parity'
        scheme.scramble_from_own_orientation = mode == 'own_orientation'
        scheme.corners.orientation_memo = scheme.edges.orientation_memo = 'trace'
    # A canonical piece name must still mean its saved preferred sticker when
    # passed as a legacy string; an explicit pair must mean the exact sticker.
    for cat in ('corners', 'edges'):
        getattr(scheme, cat).cycle_break_stickers = {
            piece: next(s for s in CATEGORY_STICKER_ORDER[cat]
                        if s in stickers and s != piece)
            for piece, stickers in CATEGORY_PIECES[cat].items()
        }
    before = deepcopy(scheme.to_dict())
    tracer = ScrambleTracer()
    normal = tracer.trace(SCRAMBLE, scheme)
    prefix = category[:-1]
    breaks = getattr(normal, prefix + '_cycle_breaks')
    assert breaks
    argument = prefix + '_cycle_break_overrides'
    for info in breaks:
        for piece, preferred in info.options:
            legacy = tracer.trace(SCRAMBLE, scheme, **{argument: {info.break_index: piece}})
            assert getattr(legacy, prefix + '_cycle_breaks')[info.break_index].chosen_sticker == preferred
            for sticker in CATEGORY_PIECES[category][piece]:
                changed = tracer.trace(SCRAMBLE, scheme, **{
                    argument: {info.break_index: (piece, sticker)},
                })
                chosen = getattr(changed, prefix + '_cycle_breaks')[info.break_index]
                assert (chosen.chosen_piece, chosen.chosen_sticker) == (piece, sticker)
                assert chosen.options == info.options
                targets = getattr(changed, prefix + '_targets')
                assert targets[info.target_index] == sticker
                assert targets[:info.target_index] == getattr(normal, prefix + '_targets')[:info.target_index]
                # Established preferred-sticker tracing is the reference for
                # the entire resulting memo, including cycle closure/parity.
                reference_scheme = deepcopy(scheme)
                getattr(reference_scheme, category).cycle_break_stickers[piece] = sticker
                reference = tracer.trace(SCRAMBLE, reference_scheme, **{
                    argument: {info.break_index: piece},
                })
                for kind in ('corner', 'edge'):
                    for suffix in ('targets', 'letters', 'pairs', 'orientation',
                                   'cycle_ids', 'orientation_target_flags'):
                        name = kind + '_' + suffix
                        assert getattr(changed, name) == getattr(reference, name)
                assert changed.three_style_parity_applied == reference.three_style_parity_applied
                assert scheme.to_dict() == before


@pytest.mark.parametrize('category', ['corners', 'edges'])
def test_invalid_or_unavailable_sticker_overrides_keep_the_recommended_trace(category):
    scheme = letter_scheme()
    before = deepcopy(scheme.to_dict())
    tracer = ScrambleTracer()
    normal = tracer.trace(SCRAMBLE, scheme)
    prefix = category[:-1]
    info = getattr(normal, prefix + '_cycle_breaks')[0]
    cat = getattr(scheme, category)
    pieces = CATEGORY_PIECES[category]
    valid = {piece for piece, _ in info.options}
    unavailable = next(piece for piece in pieces if piece not in valid and piece != cat.buffer_piece)
    other_category = 'edges' if category == 'corners' else 'corners'
    invalid = [
        (info.recommended_piece, 'NOT_A_STICKER'),
        (info.recommended_piece, CATEGORY_STICKER_ORDER[other_category][0]),
        (info.recommended_piece, info.options[-1][1]),
        (cat.buffer_piece, cat.buffer_sticker),
        (unavailable, unavailable),
        ('NOT_A_PIECE', 'NOT_A_STICKER'),
    ]
    for choice in invalid:
        changed = tracer.trace(SCRAMBLE, scheme, **{
            prefix + '_cycle_break_overrides': {info.break_index: choice},
        })
        assert changed == normal
    assert scheme.to_dict() == before


def memo_page(dark=False):
    page, repo = mount()
    scheme = letter_scheme()
    repo.data.schemes = {scheme.name: scheme}
    repo.data.active_scheme = scheme.name
    repo.data.dark_mode = dark
    view = click_nav(page, 'Scramble Memo')
    view.scramble.value = SCRAMBLE
    with patch.object(type(view), 'update'):
        view.generate(None)
    return repo, view


def sticker_button(dialog, piece, sticker):
    return next(c for c in walk(dialog)
                if isinstance(c, (ft.FilledButton, ft.OutlinedButton))
                and c.tooltip == f'Use {sticker} on {piece}')


@pytest.mark.parametrize('category', ['corners', 'edges'])
@pytest.mark.parametrize('dark', [False, True])
def test_picker_shows_all_stickers_and_can_override_the_priority_piece(category, dark):
    repo, view = memo_page(dark)
    before = deepcopy(repo.data.to_dict())
    prefix = category[:-1]
    info = getattr(view.last_result, prefix + '_cycle_breaks')[0]
    fake_page = SimpleNamespace(show_dialog=Mock(), pop_dialog=Mock())
    with patch.object(type(view), 'page', property(lambda self: fake_page)), \
            patch.object(type(view), 'update'), patch.object(repo, 'save') as save:
        view._open_cycle_break_picker(category, info)
        dialog = fake_page.show_dialog.call_args.args[0]
        buttons = [c for c in walk(dialog) if isinstance(c, (ft.FilledButton, ft.OutlinedButton))]
        assert len(buttons) == sum(len(CATEGORY_PIECES[category][p]) for p, _ in info.options)
        for piece, preferred in info.options:
            for sticker in CATEGORY_PIECES[category][piece]:
                button = sticker_button(dialog, piece, sticker)
                assert sticker in button.content
                assert getattr(repo.data.schemes['gold'], category).stickers[sticker] in button.content
                assert ('preferred' in button.content) == (sticker == preferred)
                assert isinstance(button, ft.FilledButton) == (sticker == info.chosen_sticker)

        # Choosing another sticker on the highest-priority piece is still an
        # override; it must not be mistaken for "Reset to priority".
        piece = info.recommended_piece
        preferred = dict(info.options)[piece]
        alternate = next(s for s in CATEGORY_PIECES[category][piece] if s != preferred)
        sticker_button(dialog, piece, alternate).on_click(None)
        chosen = getattr(view.last_result, prefix + '_cycle_breaks')[0]
        assert (chosen.chosen_piece, chosen.chosen_sticker) == (piece, alternate)
        assert view.reset_breaks_button.visible
        fake_page.pop_dialog.assert_called_once()

        view._open_cycle_break_picker(category, chosen)
        dialog = fake_page.show_dialog.call_args.args[0]
        assert isinstance(sticker_button(dialog, piece, alternate), ft.FilledButton)
        sticker_button(dialog, piece, preferred).on_click(None)
        assert not getattr(view, prefix + '_break_overrides')
        assert not view.reset_breaks_button.visible
        assert getattr(view.last_result, prefix + '_cycle_breaks')[0].chosen_sticker == preferred
        save.assert_not_called()
    assert repo.data.to_dict() == before


def test_exact_choices_reset_together_and_expire_when_scramble_or_scheme_changes():
    repo, view = memo_page()
    normal = view.last_result
    before = deepcopy(repo.data.to_dict())

    def select_alternates():
        for category in ('corners', 'edges'):
            prefix = category[:-1]
            info = getattr(view.last_result, prefix + '_cycle_breaks')[0]
            alternate = next(s for s in CATEGORY_PIECES[category][info.chosen_piece]
                             if s != info.chosen_sticker)
            getattr(view, prefix + '_break_overrides')[0] = (info.chosen_piece, alternate)
        view._generate_result(view.state.active_scheme)

    with patch.object(type(view), 'update'):
        select_alternates()
        changed = view.last_result
        assert changed != normal
        view.generate(None)
        assert view.last_result == changed
        view._reset_cycle_breaks()
        assert view.last_result == normal
        assert not view.corner_break_overrides and not view.edge_break_overrides
        select_alternates()
        view.scramble.value = GOLD_TESTS[0]['scramble']
        view.generate(None)
        assert not view.corner_break_overrides and not view.edge_break_overrides
        view.scramble.value = SCRAMBLE
        view.generate(None)
        select_alternates()
        view.state.active_scheme.memo_front = 'R'
        view.refresh(update=False)
        assert not view.corner_break_overrides and not view.edge_break_overrides
        assert not view.reset_breaks_button.visible
        view.state.active_scheme.memo_front = 'G'
    assert repo.data.to_dict() == before
