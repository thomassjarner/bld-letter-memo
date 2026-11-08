"""A real memo must follow the active scheme's saved piece/sticker priorities."""
from copy import deepcopy

import pytest

from core.cube_definitions import CATEGORY_PIECES
from core.progressive_memo import build_plan
from core.tracer import ScrambleTracer
from test_gold_scrambles import GOLD_TESTS
from test_navigation import no_client_mount
from test_progressive_memo import letter_scheme, open_mode


SCRAMBLE = GOLD_TESTS[3]["scramble"]


def preferred_scheme(category, three_style, orientation="visual"):
    original = letter_scheme()
    original.name = "Inactive defaults"
    original.three_style_enabled = three_style
    original.corners.orientation_memo = original.edges.orientation_memo = orientation
    original_trace = ScrambleTracer().trace(SCRAMBLE, original)
    prefix = "corner" if category == "corners" else "edge"
    first = getattr(original_trace, prefix + "_cycle_breaks")[0]
    assert len(first.options) > 1
    piece, suggested = first.options[-1]
    sticker = next(sticker for sticker in CATEGORY_PIECES[category][piece] if sticker != suggested)
    active = original.duplicate("Active custom priorities")
    config = getattr(active, category)
    config.cycle_break_priority = [piece] + [p for p in CATEGORY_PIECES[category] if p != piece]
    config.cycle_break_stickers[piece] = sticker
    return original, active, original_trace, prefix, piece, sticker


def assert_memo_matches(plan, trace):
    for memo in plan.categories:
        prefix = "corner" if memo.category == "corners" else "edge"
        letters = getattr(trace, prefix + "_letters")
        flags = getattr(trace, prefix + "_orientation_target_flags")
        assert "".join(memo.ordinary_pairs) == "".join(letter for letter, flag in zip(letters, flags) if not flag)
        assert "".join(memo.orientation_pairs) == "".join(letter for letter, flag in zip(letters, flags) if flag)


@pytest.mark.parametrize("category", ["corners", "edges"])
@pytest.mark.parametrize("three_style", [False, True])
@pytest.mark.parametrize("orientation", ["visual", "trace"])
def test_saved_order_and_exact_sticker_change_real_progressive_memo(category, three_style, orientation):
    _, active, baseline, prefix, piece, sticker = preferred_scheme(category, three_style, orientation)
    saved = deepcopy(active.to_dict())
    expected = ScrambleTracer().trace(SCRAMBLE, active)
    chosen = getattr(expected, prefix + "_cycle_breaks")[0]
    assert chosen.chosen_piece == piece
    assert chosen.chosen_sticker == sticker
    assert getattr(expected, prefix + "_targets") != getattr(baseline, prefix + "_targets")
    plan = build_plan(SCRAMBLE, active)
    assert_memo_matches(plan, expected)
    assert plan.scheme_snapshot == saved and active.to_dict() == saved
    if three_style:
        assert len("".join(next(m for m in plan.categories if m.category == "edges").ordinary_pairs)) % 2 == 0


@pytest.mark.parametrize("category", ["corners", "edges"])
@pytest.mark.parametrize("three_style", [False, True])
def test_start_uses_active_scheme_and_next_attempt_picks_up_switch_or_reorder(category, three_style):
    _, repo, _, mode = open_mode()
    original, active, baseline, _, _, _ = preferred_scheme(category, three_style)
    repo.data.schemes = {original.name: original, active.name: active}
    repo.data.active_scheme = active.name
    mode.current_scramble = SCRAMBLE
    saved = deepcopy(active.to_dict())
    mode._start()
    assert not mode.error and mode.run is not None
    first = mode.run.plan
    assert first.scheme_name == active.name and first.scheme_snapshot == saved
    assert_memo_matches(first, ScrambleTracer().trace(SCRAMBLE, active))

    # Editing preferences mid-attempt cannot change letters already presented.
    config = getattr(active, category)
    config.cycle_break_priority = list(getattr(original, category).cycle_break_priority)
    config.cycle_break_stickers = dict(getattr(original, category).cycle_break_stickers)
    assert first.scheme_snapshot == saved
    mode._cancel()
    mode._start()
    assert_memo_matches(mode.run.plan, baseline)
    assert mode.run.plan.categories != first.categories

    # Selecting the other scheme also takes effect on the next Start.
    mode._cancel()
    repo.data.active_scheme = original.name
    mode._start()
    assert mode.run.plan.scheme_name == original.name
    assert mode.run.plan.scheme_snapshot == original.to_dict()
    assert_memo_matches(mode.run.plan, baseline)
