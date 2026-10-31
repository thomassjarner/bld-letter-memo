"""UF display parity and a cube-first workspace without routine status rows."""
from copy import deepcopy
from types import SimpleNamespace

import flet as ft
import pytest

from core.corner_walkthrough import build_corner_plan, edge_parity_pair, walkthrough_initial
from core.cube_definitions import EDGE_STICKER_ORDER
from core.tracer import _at
from test_corner_walkthrough import scheme_for
from test_navigation import no_client_mount, text_values, walk
from test_walkthrough_refinements import ODD, open_walkthrough

SCREEN_SCRAMBLE = "R2 D' L R2 F2 R L' U2 D F2 U B2 U' R' D' L2 U' R' B F' D2 B Rw"


@pytest.mark.parametrize('helper', ['UB', 'DF', 'BR', 'RU', 'UF', 'not an edge'])
def test_fixed_uf_preview_respects_other_helpers_and_keeps_the_real_trace_and_scheme_unchanged(helper):
    scheme = scheme_for()
    scheme.edges.buffer_piece, scheme.edges.buffer_sticker = 'DF', 'FD'
    scheme.edge_parity_partner = helper
    before = deepcopy(scheme.to_dict())
    plan = build_corner_plan(ODD, scheme)
    original = deepcopy(plan.initial)
    preview = walkthrough_initial(plan, 'solved')
    expected_helper = {'RU':'UR', 'UF':'UR', 'not an edge':'UR'}.get(helper, helper)
    assert edge_parity_pair(scheme) == ('UF', expected_helper)
    expected = {'UF':expected_helper, 'FU':expected_helper[::-1], expected_helper:'UF', expected_helper[::-1]:'FU'}
    assert all(_at(preview, s) == expected.get(s, s) for s in EDGE_STICKER_ORDER)
    assert plan.initial == original and scheme.to_dict() == before


@pytest.mark.parametrize('width,height', [(2048,900),(1440,850),(1200,600),(1080,600),(1000,500)])
def test_desktop_cube_gains_space_and_details_do_not_take_a_row_above_it(width, height):
    repo, _, w = open_walkthrough(SCREEN_SCRAMBLE)
    assert w.plan.parity_target and w.plan.remaining_twists
    w.edge_view.value = 'solved'
    w._edge_changed()
    w.set_viewport(width, height)
    assert len(w.controls) == 3
    assert w.controls[:2] == [w.input_area, w.actions]
    frame = w.controls[2]
    assert isinstance(frame, ft.Row)
    assert frame.controls[0].content.controls[0] is w.viewer
    assert frame.controls[0].height == height - w.input_area.height - w.actions.height - 2 * w.spacing
    assert w.viewer.canvas.height > min(320, max(140, height - 62 - 104 - 42 - 24 - 230))
    assert w.step_controls[-1] is w.details and w.details.controls == [w.summary]
    assert not w.details.expanded
    assert w.summary not in w.controls and w.status not in w.controls
    assert not any(any(s in str(t).lower() for s in ('parity required', 'parity remains', 'edge display', 'swapped for parity'))
                   for t in text_values(w))
    assert _at(w.viewer.states[0], 'UF') == 'UR' and _at(w.viewer.states[0], 'DF') == 'DF'
    before, plan, index, viewport = deepcopy(repo.data.to_dict()), w.plan, w.viewer.index, w.viewer._viewport
    w.details.on_change(SimpleNamespace(data='true'))
    w.set_viewport(width, height)
    assert w.details.expanded and w.viewer._viewport == viewport
    assert w.viewer.index == index and w.plan is plan and repo.data.to_dict() == before


@pytest.mark.parametrize('width,height', [(390,600),(280,400),(280,220),(1080,300)])
def test_compact_layout_places_the_cube_before_all_optional_details_and_keeps_feedback_accessible(width, height):
    _, _, w = open_walkthrough(SCREEN_SCRAMBLE)
    w.set_viewport(width, height)
    body = w.controls[0]
    assert isinstance(body, ft.ListView) and body.height == height
    assert body.controls[:3] == [w.input_area, w.actions, w.viewer]
    assert w.details in list(walk(body.controls[-1])) and not w.details.expanded
    w.scramble.value = 'Q'
    w.generate()
    assert w.plan is None and not w.viewer.visible
    assert w.feedback in w.step_controls and 'Unsupported' in w.feedback.value
    assert w.feedback in list(walk(w))


def test_no_warning_is_shown_for_an_ordinary_odd_target_count():
    _, _, w = open_walkthrough(ODD)
    assert w.plan.parity_target and not w.plan.steps
    assert 'parity' not in ' '.join(text_values(w)).lower()
    assert w.memo_text.value and w.status.value.startswith('0 algorithms')
    assert not w.details.expanded
