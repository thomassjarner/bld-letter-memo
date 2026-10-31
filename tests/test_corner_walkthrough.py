"""Real scramble execution, buffer/priority compatibility, parity and UI routes."""
from copy import deepcopy
import random
from types import SimpleNamespace
from unittest.mock import patch

import flet as ft
import pytest

from core.algorithms import algorithm_states, inverse_moves, parse_algorithm
from core.corner_cases import corner_cases
from core.corner_walkthrough import (SOLVED, apply_moves, build_corner_plan, corner_shot, rotations)
from core.cube_definitions import CORNER_PIECES, CORNER_STICKER_ORDER, EDGE_STICKER_ORDER, find_piece_for_sticker
from core.tracer import ScrambleTracer, _at, simulate
from data.models import CaseAlgorithm, CategoryScheme, CornerCaseRecord, LetterScheme
from test_case_library import open_library
from test_gold_scrambles import GOLD_TESTS, make_gold_scheme
from test_navigation import click_nav, mount, no_client_mount, text_values, walk
from ui.components.cube_projection import project_cube


def scheme_for(buffer='UFR', orientation='visual'):
    scheme = make_gold_scheme()
    scheme.corners.buffer_piece = find_piece_for_sticker(buffer, CORNER_PIECES)
    scheme.corners.buffer_sticker = buffer
    scheme.corners.orientation_memo = orientation
    scheme.corners.stickers = {sticker: chr(65 + i) for i, sticker in enumerate(CORNER_STICKER_ORDER)}
    return scheme


def assert_plan(plan):
    expected = corner_shot(SOLVED, plan.buffer, plan.parity_target) if plan.parity_target else SOLVED
    assert all(_at(plan.final, sticker) == _at(expected, sticker) for sticker in CORNER_STICKER_ORDER)
    assert all(_at(plan.final, sticker) == _at(plan.initial, sticker) for sticker in EDGE_STICKER_ORDER + list('ULFRBD'))
    state, index = plan.initial, 0
    for stage, step in zip(plan.algorithm.stages, plan.steps):
        assert stage.start == step.start == index and stage.end == step.end
        state = apply_moves(state, step.moves)
        assert all(_at(state, s) == _at(plan.initial, s) for s in EDGE_STICKER_ORDER)
        index = step.end
    assert index == len(plan.algorithm.moves) and state == plan.final
    assert apply_moves(plan.initial, plan.algorithm.moves) == plan.final


@pytest.mark.parametrize('buffer', CORNER_STICKER_ORDER)
@pytest.mark.parametrize('orientation', ['visual', 'trace'])
def test_gold_scrambles_work_for_every_buffer_sticker_and_both_twist_memo_modes(buffer, orientation):
    scheme = scheme_for(buffer, orientation)
    before = deepcopy(scheme.to_dict())
    for gold in GOLD_TESTS:
        plan = build_corner_plan(gold['scramble'], scheme)
        trace = ScrambleTracer().trace(gold['scramble'], scheme)
        assert plan.trace.corner_targets == trace.corner_targets
        assert plan.trace.corner_orientation == trace.corner_orientation
        assert plan.parity_target == (trace.corner_targets[-1] if len(trace.corner_targets) % 2 else None)
        assert_plan(plan)
    assert scheme.to_dict() == before


def test_all_memo_frames_own_orientation_modes_and_random_scrambles_keep_physical_edges():
    rng = random.Random(2370)
    opposite = {'W':'Y','Y':'W','G':'B','B':'G','R':'O','O':'R'}
    for up in opposite:
        for front in opposite:
            if front in (up, opposite[up]): continue
            for own in (False, True):
                scheme = scheme_for(rng.choice(CORNER_STICKER_ORDER), rng.choice(('visual','trace')))
                scheme.memo_up, scheme.memo_front, scheme.scramble_from_own_orientation = up, front, own
                scramble = ' '.join(rng.choice('URFDLB') + rng.choice(('',"'",'2')) for _ in range(24))
                plan = build_corner_plan(scramble, scheme)
                assert plan.initial == simulate(scramble, up, front, own)
                assert_plan(plan)


def test_saved_and_temporary_cycle_break_stickers_are_taken_from_the_original_tracer_without_writing_preferences():
    scheme = scheme_for('LUB')
    source = GOLD_TESTS[1]['scramble']
    trace = ScrambleTracer().trace(source, scheme)
    piece = trace.corner_cycle_breaks[0].options[-1][0]
    scheme.corners.cycle_break_priority = [piece] + list(reversed(CORNER_PIECES))
    scheme.corners.cycle_break_stickers[piece] = sorted(CORNER_PIECES[piece])[-1]
    before = deepcopy(scheme.to_dict())
    plan = build_corner_plan(source, scheme)
    assert plan.trace.corner_cycle_breaks[0].chosen_sticker == sorted(CORNER_PIECES[piece])[-1]
    alternate = sorted(CORNER_PIECES[piece])[0]
    changed = build_corner_plan(source, scheme, corner_cycle_break_overrides={0:(piece,alternate)})
    assert changed.trace.corner_cycle_breaks[0].chosen_sticker == alternate
    assert_plan(plan); assert_plan(changed)
    assert scheme.to_dict() == before


def test_preferred_personal_algorithms_include_an_orientation_reset_and_invalid_imports_fall_back_without_changes():
    scheme = scheme_for()
    source = ' '.join(inverse_moves(parse_algorithm("[R, U' L' U]").moves))
    custom = "[R, U' L' U] x"
    records = {'BUR:BUL': CornerCaseRecord(algorithms=[CaseAlgorithm('mine','My alg',custom)], preferred_algorithm='mine')}
    before = deepcopy(records)
    plan = build_corner_plan(source, scheme, records)
    assert len(plan.steps) == 1 and plan.steps[0].parts[0].algorithm_id == 'mine'
    assert plan.steps[0].parts[0].source == custom and plan.steps[0].parts[0].orientation_reset
    assert not plan.warnings and records == before
    assert_plan(plan)
    records['BUR:BUL'].algorithms[0].alg = 'R'
    before = deepcopy(records)
    fallback = build_corner_plan(source, scheme, records)
    assert fallback.warnings and fallback.steps[0].parts[0].algorithm_id != 'mine'
    assert records == before
    assert_plan(fallback)


def twist_scramble():
    # A pure paired twist built entirely from existing outer-turn starters.
    moves = (parse_algorithm(corner_cases()['UBL:DFR'].starter).moves
             + parse_algorithm(corner_cases()['DFR:LUB'].starter).moves)
    return ' '.join(inverse_moves(moves))


def test_visual_twists_get_verified_algorithms_even_when_a_parity_target_is_reserved():
    scheme = scheme_for()
    for source in (twist_scramble(), twist_scramble() + ' D'):
        plan = build_corner_plan(source, scheme)
        assert plan.trace.corner_orientation and any(step.correction for step in plan.steps)
        assert any(len(step.parts) == 2 for step in plan.steps if step.correction)
        assert_plan(plan)
    assert plan.parity_target is not None


def test_corner_walkthrough_does_not_require_an_edge_buffer_or_apply_the_virtual_edge_parity_swap():
    scheme = scheme_for('LUB')
    scheme.three_style_enabled = True
    scheme.edges = CategoryScheme()
    plan = build_corner_plan(GOLD_TESTS[0]['scramble'], scheme)
    assert plan.parity_target and not plan.trace.three_style_parity_applied
    assert_plan(plan)


def test_already_solved_corners_and_input_errors_do_not_create_any_saved_data():
    scheme = scheme_for()
    plan = build_corner_plan("R R'", scheme)
    assert not plan.steps and plan.final == plan.initial and not plan.parity_target
    for source, selected in (('', scheme), ('Q', scheme), ('R', None), ('R', LetterScheme('No buffer'))):
        with pytest.raises(ValueError): build_corner_plan(source, selected)


def test_a_single_corner_target_is_reserved_for_parity_without_executing_an_extra_algorithm():
    source = "R U R' U' R' F R2 U' R' U' R U R' F'"
    plan = build_corner_plan(source, scheme_for())
    assert plan.trace.corner_targets == ['UBR'] and plan.parity_target == 'UBR'
    assert not plan.steps and not plan.algorithm.moves and plan.final == plan.initial
    assert_plan(plan)


@pytest.mark.parametrize('width,height', [(1440,850),(1080,650),(1000,500),(600,650),(366,570),(280,400),(280,220)])
def test_walkthrough_layout_edge_views_and_full_stage_playback_are_bounded_and_read_only(width, height):
    _, repo, _, view = open_library()
    scheme = scheme_for('LUB')
    repo.data.schemes[scheme.name] = scheme
    before = deepcopy(repo.data.to_dict())
    view.open_corner_walkthrough(GOLD_TESTS[1]['scramble'], scheme.name)
    view.set_viewport(width, height)
    w = view.walkthrough
    assert w.plan and view.mode == 'walkthrough'
    assert w.width <= width and w.height <= view.body.height
    assert w.viewer.buffer == 'LUB' and w.viewer.current_stage.visible
    assert w.viewer._preserve_stages and not w.viewer.structure_switch.visible
    assert len(w.viewer.algorithm.stages) == len(w.plan.steps)
    last = len(w.plan.algorithm.moves)
    w.viewer.seek(last)
    assert all(_at(w.viewer.states[last], s) == _at(w.plan.final, s) for s in CORNER_STICKER_ORDER)
    for mode in ('solved','hidden','scrambled'):
        w.edge_view.value = mode
        w._edge_changed()
        assert w.viewer.index == last
        expected_edges = SOLVED if mode == 'solved' else w.plan.initial
        assert all(_at(w.viewer.states[last], s) == _at(expected_edges, s) for s in EDGE_STICKER_ORDER)
        assert w.viewer.edge_colors == (mode != 'hidden')
    w._select_step(0)
    assert w.viewer.index == 0 and w.viewer.targets == (w.plan.steps[0].first, w.plan.steps[0].second)
    assert repo.data.to_dict() == before


def test_edge_mask_hides_only_edge_colors_and_letters_and_buffer_symbols_follow_the_walkthrough_buffer():
    net = project_cube(SOLVED, 600, 350, mode='2D', buffer='LUB', edge_colors=False)
    assert sum(t.color == '#35403C' for t in net) == 24
    assert all(not t.label for t in net if t.color == '#35403C')
    assert sum(t.label == '★' for t in net) == 1
    # The star is on the LUB sticker's tile; the default still uses UFR.
    normal = project_cube(SOLVED, 600, 350, mode='2D', edge_colors=True)
    assert sum(t.label == '★' for t in normal) == 1 and not any(t.color == '#35403C' for t in normal)


def test_scramble_scheme_or_saved_algorithm_changes_invalidate_a_stale_plan_and_navigation_stops_playback():
    page, repo, _, view = open_library()
    scheme = scheme_for()
    repo.data.schemes[scheme.name] = scheme
    view.open_corner_walkthrough(GOLD_TESTS[0]['scramble'], scheme.name)
    w = view.walkthrough
    w.viewer.playing = True
    click_nav(page, 'Timer')
    assert not w.viewer.playing
    click_nav(page, 'Method Library')
    scheme.corners.cycle_break_priority = list(reversed(CORNER_PIECES))
    view.refresh()
    assert w.plan is None and 'changed' in w.status.value
    w.generate();assert w.plan
    w.scramble.value = 'Q';w.scramble.on_change(None)
    assert w.plan is None and w.play_all_button.disabled
    w.generate();assert w.plan is None and 'Unsupported' in w.status.value


def test_timer_shortcuts_use_the_exact_current_or_history_scramble_and_preserve_sessions_and_keyboard():
    page, repo = mount()
    scheme = scheme_for()
    repo.data.schemes[scheme.name] = scheme;repo.data.active_scheme = scheme.name
    timer = click_nav(page, 'Timer')
    listener = timer.keyboard_listener
    current, saved = GOLD_TESTS[0]['scramble'], GOLD_TESTS[1]['scramble']
    timer.current_scramble = current
    timer.state.add_practice_solve(2630, saved)
    timer._refresh_stats_and_history(update=False)
    before = deepcopy(repo.data.to_dict())
    timer.corner_walkthrough_button.on_click(None)
    method = page.root.controls[0].content
    assert method.mode == 'walkthrough' and method.walkthrough.plan.scramble == current
    assert not timer.active and repo.data.to_dict() == before
    click_nav(page, 'Timer')
    shortcut = next(c for c in walk(timer.history) if isinstance(c, ft.IconButton) and c.tooltip == 'Corner walkthrough · saved solve')
    shortcut.on_click(None)
    assert method.walkthrough.plan.scramble == saved and repo.data.to_dict() == before
    click_nav(page, 'Timer')
    assert timer.keyboard_listener is listener
    timer.running = True
    timer.corner_walkthrough_button.on_click(None)
    shortcut.on_click(None)
    assert page.root.controls[0].content is timer and repo.data.to_dict() == before


@pytest.mark.parametrize('dark', [False, True])
def test_walkthrough_fields_labels_and_playback_keep_the_existing_light_and_dark_palette(dark):
    _, repo, _, view = open_library()
    repo.data.dark_mode = dark
    view.open_corner_walkthrough(GOLD_TESTS[0]['scramble'], repo.data.active_scheme)
    view.refresh()
    expected = '#F0F4F3' if dark else '#182B25'
    for control in walk(view.walkthrough):
        if isinstance(control, (ft.TextField, ft.Dropdown)): assert control.color == expected
    assert view.walkthrough.status.color == expected
    assert view.walkthrough.viewer.dark_mode == dark
    assert all(s.style.color.startswith('#') for s in view.walkthrough.viewer.move_text.spans)
