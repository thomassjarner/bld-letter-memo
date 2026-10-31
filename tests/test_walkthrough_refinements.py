"""Physical-piece focus, paced execution, display parity and exact editor routes."""
import asyncio
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

import flet as ft
import pytest

from core.algorithms import algorithm_states, inverse_moves, parse_algorithm
from core.commutator_finder import execution_signature
from core.corner_algorithms import builtin_algorithms
from core.corner_walkthrough import SOLVED, apply_moves, build_corner_plan, walkthrough_initial
from core.cube_definitions import CORNER_STICKER_ORDER, EDGE_PIECES, EDGE_STICKER_ORDER
from core.tracer import _at, _key
from core.walkthrough_details import move_statistics, step_commutator
from data.models import CaseAlgorithm, CategoryScheme, CornerCaseRecord
from test_case_library import open_library
from test_corner_walkthrough import assert_plan, scheme_for, twist_scramble
from test_gold_scrambles import GOLD_TESTS
from test_navigation import no_client_mount, text_values, walk
from ui.components.algorithm_cube import AlgorithmCube
from ui.components.cube_projection import project_cube

ODD = "R U R' U' R' F R2 U' R' U' R U R' F'"
SCREEN_SCRAMBLE = "R2 D2 R2 B R2 D2 F U2 L2 D2 R2 F R' B' L2 B R' U2 F'"


def open_walkthrough(source=SCREEN_SCRAMBLE, buffer='UFR'):
    _, repo, _, view = open_library()
    scheme = scheme_for(buffer)
    repo.data.schemes[scheme.name] = scheme
    view.open_corner_walkthrough(source, scheme.name)
    return repo, view, view.walkthrough


@pytest.mark.parametrize('buffer', ['UFR', 'LUB', 'DFR', 'RDB'])
def test_focus_tracks_only_the_actual_three_corner_identities_through_every_stage_and_its_turns(buffer):
    _, _, w = open_walkthrough(buffer=buffer)
    cube = w.viewer
    excludes_buffer = False
    for stage, step in zip(cube.algorithm.stages, w.plan.steps):
        before, after = cube.states[stage.start], cube.states[stage.end]
        expected = {frozenset(home) for pos, home in before.items() if home != after[pos]}
        assert len(expected) == 3 and all(len(piece) == 3 for piece in expected)
        for index in (stage.start, (stage.start + stage.end) // 2, stage.end - 1):
            cube.seek(index)
            assert cube.affected == expected
            affected, highlights = cube._stage_focus[stage.label]
            assert len(highlights) == 9 and {frozenset(s) for s in highlights} == expected
            tiles = project_cube(cube.states[index], 600, 350, mode='2D', buffer=buffer,
                affected=affected, targets=cube.targets, highlight_stickers=highlights)
            assert sum(tile.outline != '#0A0F0D' for tile in tiles) == 9
            if frozenset(buffer) not in expected:
                excludes_buffer = True
                assert buffer not in highlights
                assert next(tile for tile in tiles if tile.label == '★').outline == '#0A0F0D'
            plain = project_cube(cube.states[index], 600, 350, mode='2D', focus=False,
                affected=affected, targets=cube.targets, highlight_stickers=highlights)
            assert all(tile.outline == '#0A0F0D' for tile in plain)
    assert excludes_buffer  # Regression: the original home buffer must not stay bright.


@pytest.mark.parametrize('simultaneous', [False, True])
def test_default_playback_stops_at_each_algorithm_and_continue_keeps_the_finished_pieces_in_view(simultaneous):
    repo, _, w = open_walkthrough()
    cube = w.viewer
    cube.set_simultaneous_moves(simultaneous)
    cube.mode_picker.value = '2D'
    before = deepcopy(repo.data.to_dict())
    clock = [0.0]
    async def sleep(delay): clock[0] += delay
    with patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep), \
         patch('ui.components.algorithm_cube.time.perf_counter', side_effect=lambda: clock[0]):
        for stage in cube.algorithm.stages:
            asyncio.run(cube._play(cube._token, len(cube.algorithm.moves)))
            assert cube.index == stage.end and not cube.playing and cube._moving is None
            assert cube._boundary_stage == stage and cube.current_stage.value == 'Completed · ' + stage.label
            assert cube.affected == cube._stage_focus[stage.label][0]
            assert cube.continue_button.visible == (stage.end < len(cube.algorithm.moves))
            if cube.continue_button.visible:
                fake = SimpleNamespace(run_task=Mock())
                with patch.object(cube, '_page', return_value=fake), patch.object(cube, '_update'):
                    cube.continue_button.on_click(None)
                assert cube._boundary_stage is None and cube.playing
                callback, token, end = fake.run_task.call_args.args
                assert callback == cube._play and end == len(cube.algorithm.moves) and token == cube._token
        assert cube.states[cube.index] == w.plan.final
    assert repo.data.to_dict() == before


def test_pause_can_be_disabled_without_changing_the_execution_and_never_applies_to_general_alg_playback():
    _, _, w = open_walkthrough()
    w.pause_switch.value = False
    w.pause_switch.on_change(None)
    cube = w.viewer
    cube.mode_picker.value = '2D'
    async def sleep(delay): pass
    with patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep):
        asyncio.run(cube._play(cube._token, len(cube.algorithm.moves)))
    assert cube.index == len(cube.algorithm.moves) and cube.states[-1] == w.plan.final
    general = AlgorithmCube()
    assert not general.pause_after_stage
    general.load('[R,U]')
    general.mode_picker.value = '2D'
    with patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep):
        asyncio.run(general._play(general._token, len(general.algorithm.moves)))
    assert general.index == len(general.algorithm.moves) and not general.continue_button.visible


def test_switching_edge_modes_retains_the_completed_stage_and_stale_tasks_cannot_clear_it():
    _, view, w = open_walkthrough()
    cube = w.viewer
    cube.mode_picker.value = '2D'
    async def sleep(delay): pass
    with patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep):
        asyncio.run(cube._play(cube._token, len(cube.algorithm.moves)))
    held, index, affected = cube._boundary_stage, cube.index, cube.affected
    stale = cube._token
    w.edge_view.value = 'solved'
    w._edge_changed()
    assert cube._boundary_stage == held and cube.index == index and cube.affected == affected
    asyncio.run(cube._play(stale, len(cube.algorithm.moves)))
    assert cube._boundary_stage == held and cube.index == index
    view.set_active(False)
    assert not cube.playing


@pytest.mark.parametrize('edge_buffer', EDGE_STICKER_ORDER)
def test_solved_edge_display_always_swaps_uf_with_the_helper_regardless_of_edge_buffer(edge_buffer):
    scheme = scheme_for()
    piece = next(p for p, stickers in EDGE_PIECES.items() if edge_buffer in stickers)
    helper = 'UR'
    scheme.edges.buffer_piece, scheme.edges.buffer_sticker = piece, edge_buffer
    scheme.edge_parity_partner = helper
    snapshot = deepcopy(scheme.to_dict())
    for source, odd in ((ODD, True), ("R R'", False)):
        plan = build_corner_plan(source, scheme)
        initial = deepcopy(plan.initial)
        display = walkthrough_initial(plan, 'solved')
        expected = {'UF': helper, 'FU': helper[::-1], helper: 'UF', helper[::-1]: 'FU'}
        for sticker in EDGE_STICKER_ORDER:
            assert _at(display, sticker) == (expected.get(sticker, sticker) if odd else sticker)
        assert all(_at(display, s) == _at(initial, s) for s in CORNER_STICKER_ORDER + list('ULFRBD'))
        assert walkthrough_initial(plan, 'hidden') == walkthrough_initial(plan, 'scrambled') == initial
        assert plan.initial == initial and scheme.to_dict() == snapshot


def test_preview_works_without_an_edge_buffer_and_a_uf_helper_uses_ur_without_changing_settings():
    repo, _, w = open_walkthrough(ODD)
    scheme = repo.data.schemes[w.scheme_name]
    for edges, helper in ((CategoryScheme(), 'UR'), (scheme_for().edges, 'UF')):
        scheme.edges, scheme.edge_parity_partner = edges, helper
        before = deepcopy(scheme.to_dict())
        w.generate()
        assert w.plan and w.plan.parity_target
        w.edge_view.value = 'solved'
        w._edge_changed()
        assert _at(w.viewer.states[0], 'UF') == 'UR' and _at(w.viewer.states[0], 'UR') == 'UF'
        assert _at(w.viewer.states[0], 'DF') == 'DF' and scheme.to_dict() == before
        assert not any('parity' in str(t).lower() for t in text_values(w))


@pytest.mark.parametrize('memo_mode', ['visual', 'trace'])
def test_twist_only_scramble_stays_unchanged_and_odd_permutation_reserves_its_original_final_target(memo_mode):
    scheme = scheme_for(orientation=memo_mode)
    pure = build_corner_plan(twist_scramble(), scheme)
    assert not pure.steps and pure.final == pure.initial and pure.remaining_twists
    odd = build_corner_plan(twist_scramble() + ' D', scheme)
    non_twists = [s for s, flag in zip(odd.trace.corner_targets, odd.trace.corner_orientation_target_flags) if not flag]
    assert len(non_twists) % 2 and odd.parity_target == non_twists[-1]
    assert_plan(odd)
    if memo_mode == 'trace':
        assert any(odd.trace.corner_orientation_target_flags)
        assert odd.parity_target != odd.trace.corner_targets[-1]


@pytest.mark.parametrize('buffer', ['UFR', 'LUB'])
def test_commutator_cards_describe_the_same_execution_including_other_buffer_setups(buffer):
    _, _, w = open_walkthrough(buffer=buffer)
    texts = text_values(w)
    recovered = 0
    for step in w.plan.steps:
        expression = step_commutator(step)
        if expression:
            recovered += 1
            assert execution_signature(parse_algorithm(expression).moves) == execution_signature(step.moves)
            assert algorithm_states(parse_algorithm(expression))[-1] == apply_moves(SOLVED, step.moves)
            assert expression in texts
    assert recovered
    assert texts.count('Commutator') == len(w.plan.steps)
    assert texts.count('Final alg') == len(w.plan.steps)
    assert sum(isinstance(c, ft.TextButton) and c.content == 'Open case & edit alg' for c in walk(w)) == len(w.plan.steps)
    assert move_statistics(('R2', "Uw'", 'M', 'x', 'y2')) == (3, 4, 2)


def test_a_failed_bounded_commutator_recovery_does_not_pretend_a_different_execution_is_the_selected_alg():
    plan = build_corner_plan(SCREEN_SCRAMBLE, scheme_for())
    step = plan.steps[0]
    # Same corner case, but a valid extra identity sequence with a different execution.
    extra = ('R', 'U') * 105
    assert apply_moves(SOLVED, extra) == SOLVED
    source = ' '.join(step.moves + extra)
    part = replace(step.parts[0], source=source, setup=(), orientation_reset=())
    modified = replace(step, moves=step.moves + extra, parts=(part,))
    assert step_commutator(modified) is None
    # Large combined executions still render a card when a whole-buffer setup
    # exceeds the input bounds of the standalone reverse finder.
    assert step_commutator(replace(modified, moves=modified.moves * 4)) is None


@pytest.mark.parametrize('personal', [False, True])
def test_card_links_open_the_exact_selected_algorithm_and_return_to_the_same_walkthrough_without_saving(personal):
    repo, view, w = open_walkthrough(buffer='LUB')
    step = w.plan.steps[0]
    key = step.parts[0].case_id
    if personal:
        default = builtin_algorithms(key)[0]
        repo.data.corner_case_library[key] = CornerCaseRecord(
            algorithms=[CaseAlgorithm('mine', 'My chosen alg', default.alg)], preferred_algorithm='mine', status='learning')
        w.generate()
        step = w.plan.steps[0]
    w._select_step(1)
    index, plan = w.viewer.index, w.plan
    view.search.value = 'no matching case'
    before = deepcopy(repo.data.to_dict())
    link = next(c for c in walk(w) if isinstance(c, ft.TextButton) and c.content == 'Open case & edit alg')
    link.on_click(None)
    assert view.mode == 'library' and view.selected_case == key and not w.viewer.playing
    assert view.selected_algorithm == step.parts[0].algorithm_id
    assert view.case_converter.source == step.parts[0].source
    assert view.algorithm_editor.visible and not view.hidden
    assert any(c.id == key for c in view.filtered_cases())
    assert repo.data.to_dict() == before
    back = next(c for c in walk(view.case_toolbar) if isinstance(c, ft.IconButton) and c.tooltip == 'Return to scramble walkthrough')
    assert back.visible
    back.on_click(None)
    assert view.mode == 'walkthrough' and w.plan is plan and w.viewer.index == index
    assert repo.data.to_dict() == before


def test_names_and_twist_status_are_clear_and_the_pause_switch_is_always_available_below_the_cube():
    repo, view, w = open_walkthrough(twist_scramble())
    assert view.section_buttons['walkthrough'].content == 'Scramble walkthrough'
    assert not any('Corner walkthrough' in str(t) for t in text_values(view))
    assert w.twist_text.visible and not w.plan.steps and w.play_all_button.disabled
    assert w.details.controls == [w.summary] and not w.details.expanded
    assert w.twist_text in w.summary.controls and 'Corner twists' in w.twist_text.value
    assert 'No paired corner algorithms' in ' '.join(text_values(w))
    assert w.pause_switch in w.viewer.display_switches.controls and w.pause_switch.value
    assert w.viewer.pause_after_stage and not w.viewer.continue_button.visible
