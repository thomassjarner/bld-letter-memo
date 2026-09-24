"""
Gold-standard scramble tests for the BLD tracer (core/tracer.py).

These four scrambles were hand-worked-out and verified by the app's author
against buffer LUB (corners) / DF (edges), White-top/Green-front orientation.
They are the ground truth for the tracing engine. If any of these break,
STOP and investigate before touching core/tracer.py further -- do not
"fix" a test to match new engine output without re-verifying the expected
memo by hand.

What's checked here (letters are scheme-specific and not encoded):
- ordinary corner/edge target counts
- which pieces are flagged as orientation-only twists/flips
- corner/edge target-count parity (must always match)

Known naming caveat (see README "Migrated for Flet 0.86" section, gold
test 1): the engine's canonical piece names for edges are picked
arbitrarily (e.g. "FR", "DR") and may not match the R/L-first convention
used in the original hand-written notes ("RF", "RD"). These refer to the
SAME physical edges -- this is a display/labeling question, not a tracing
bug. The assertions below use the engine's own canonical names.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.tracer import ScrambleTracer, simulate, _orientation_only_pieces
from core.cube_definitions import CORNER_STICKER_ORDER, EDGE_STICKER_ORDER, CORNER_PIECES, EDGE_PIECES
from data.models import LetterScheme, CategoryScheme


def make_gold_scheme() -> LetterScheme:
    corners = CategoryScheme(buffer_piece="UBL", buffer_sticker="LUB")
    edges = CategoryScheme(buffer_piece="DF", buffer_sticker="DF")
    return LetterScheme(name="gold", corners=corners, edges=edges, memo_up="W", memo_front="G")


GOLD_TESTS = [
    dict(
        name="gold_test_1",
        scramble="D L2 B2 U B2 L2 F2 L2 R2 D' B D' L' F' L2 R D B L Fw' Uw",
        corner_targets=9,
        edge_targets=9,
        corner_twists=[],
        edge_flips=["FR", "DR"],  # hand-notes call these "RF"/"RD" -- see caveat above
    ),
    dict(
        name="gold_test_2",
        scramble="L' B' R' F2 D B U R B' U2 R U2 R L2 U2 R' D2 F2 L' D2 Rw'",
        corner_targets=7,
        edge_targets=11,
        corner_twists=["DBR"],
        edge_flips=["UB"],
        corner_break_index=3,   # 4th target (0-indexed 3) is the cycle-break shot
        corner_break_sticker="DFR",
        edge_break_index=2,     # 3rd target (0-indexed 2) is the cycle-break shot
        edge_break_sticker="DR",
    ),
    dict(
        name="gold_test_3",
        scramble="R' F' L2 R2 F2 R2 B L2 F' U2 L2 B' U2 L' D' U F D U2 B2 R Rw Uw",
        corner_targets=5,
        edge_targets=11,
        corner_twists=["UFR"],
        edge_flips=[],
    ),
    dict(
        name="gold_test_4",
        scramble="U' D' L2 B2 R' B D' F L' D2 L2 B D2 F2 U2 D2 L2 F D2 B Fw'",
        corner_targets=7,
        edge_targets=11,
        corner_twists=["DFL"],
        edge_flips=["DL"],
    ),
]


@pytest.mark.parametrize("case", GOLD_TESTS, ids=[c["name"] for c in GOLD_TESTS])
def test_gold_scramble(case):
    scheme = make_gold_scheme()
    tracer = ScrambleTracer()
    result = tracer.trace(case["scramble"], scheme)
    state = simulate(case["scramble"], scheme.memo_up, scheme.memo_front)

    assert len(result.corner_targets) == case["corner_targets"], (
        f"corner target count: got {len(result.corner_targets)} "
        f"({result.corner_targets}), expected {case['corner_targets']}"
    )
    assert len(result.edge_targets) == case["edge_targets"], (
        f"edge target count: got {len(result.edge_targets)} "
        f"({result.edge_targets}), expected {case['edge_targets']}"
    )

    # Corner/edge ordinary target counts must always share parity (invariant 9).
    assert len(result.corner_targets) % 2 == len(result.edge_targets) % 2

    corner_twists = sorted(_orientation_only_pieces(state, CORNER_PIECES, CORNER_STICKER_ORDER))
    edge_flips = sorted(_orientation_only_pieces(state, EDGE_PIECES, EDGE_STICKER_ORDER))
    assert corner_twists == sorted(case["corner_twists"])
    assert edge_flips == sorted(case["edge_flips"])

    if "corner_break_sticker" in case:
        assert result.corner_targets[case["corner_break_index"]] == case["corner_break_sticker"]
    if "edge_break_sticker" in case:
        assert result.edge_targets[case["edge_break_index"]] == case["edge_break_sticker"]


def test_all_memo_orientations_reframe_centers_and_preserve_parity():
    """All 24 legal cube orientations must be valid memo frames.

    Scramble notation stays in the fixed White-up/Green-front frame; simulate()
    then expresses the finished cube relative to the requested scheme frame.
    In that relative frame all six centers must read U/L/F/R/B/D again.
    """
    colors = ["W", "Y", "G", "B", "R", "O"]
    opposite = {"W": "Y", "Y": "W", "G": "B", "B": "G", "R": "O", "O": "R"}
    tracer = ScrambleTracer()
    case = GOLD_TESTS[1]

    seen_target_sequences = set()
    for up in colors:
        for front in colors:
            if front in {up, opposite[up]}:
                continue
            scheme = make_gold_scheme()
            scheme.memo_up = up
            scheme.memo_front = front
            state = simulate(case["scramble"], up, front)
            assert all(state[(
                # center key: position vector == face vector == VEC[face]
                # Use tracer helper indirectly via the public sticker lookup
                # representation by importing _at below.
                )] for _ in []) is True
            from core.tracer import _at
            assert tuple(_at(state, face) for face in "ULFRBD") == tuple("ULFRBD")

            result = tracer.trace(case["scramble"], scheme)
            assert len(result.corner_targets) % 2 == len(result.edge_targets) % 2
            assert len(result.corner_cycle_ids) == len(result.corner_targets)
            assert len(result.edge_cycle_ids) == len(result.edge_targets)
            seen_target_sequences.add((tuple(result.corner_targets), tuple(result.edge_targets)))

    # If orientation were being ignored, every frame would produce the exact
    # same target sequence. It should materially affect memo interpretation.
    assert len(seen_target_sequences) > 1


def test_three_style_odd_corner_trace_keeps_corners_and_evenizes_edges():
    tracer = ScrambleTracer()
    for case in GOLD_TESTS:
        normal_scheme = make_gold_scheme()
        normal = tracer.trace(case["scramble"], normal_scheme)
        assert len(normal.corner_targets) % 2 == 1

        scheme = make_gold_scheme()
        scheme.three_style_enabled = True
        scheme.edge_parity_partner = "UR"
        result = tracer.trace(case["scramble"], scheme)

        assert result.corner_targets == normal.corner_targets
        assert result.corner_orientation == normal.corner_orientation
        assert result.three_style_parity_applied is True
        assert len(result.edge_targets) % 2 == 0


def test_three_style_even_corner_trace_leaves_edges_normal():
    scramble = "U' L R U' B U2 F' B' D' U2 R F L D L' D2 U2 L U2 F B L2 Rw Uw'"
    tracer = ScrambleTracer()

    normal_scheme = make_gold_scheme()
    normal = tracer.trace(scramble, normal_scheme)
    assert len(normal.corner_targets) % 2 == 0

    scheme = make_gold_scheme()
    scheme.three_style_enabled = True
    scheme.edge_parity_partner = "UR"
    result = tracer.trace(scramble, scheme)

    assert result.corner_targets == normal.corner_targets
    assert result.edge_targets == normal.edge_targets
    assert result.three_style_parity_applied is False
