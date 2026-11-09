"""Written components, exact notation leaves, paced study and walkthrough offsets."""
import asyncio
from copy import deepcopy
import random
from types import SimpleNamespace
from unittest.mock import Mock, patch

import flet as ft
import pytest

from core.algorithms import Algorithm, Stage, algorithm_states, parse_algorithm, simplify_moves
from core.commutator_finder import execution_signature
from core.commutator_playback import align_notation, commutator_study
from core.legacy_corner_algorithms import ALL_SUBMISSIONS
from core.tracer import _at
from test_case_library import open_library
from test_navigation import no_client_mount
from test_walkthrough_refinements import open_walkthrough
from ui.components.algorithm_cube import AlgorithmCube

SOURCE = "[R': [U2, R' D' R]]"


@pytest.mark.parametrize('source', [
    '[R,U]', "f:[U2,R' D' R]", "[x:[R':[U2,R' D' R]]]", "[R,U]'",
    '([R,U])2', "([R,U])2'", "R [U,Fw2] R'", '[R: U2 M2]',
    "[R:[U2,[F,D']]]", '[U: R R\']', '[R,R]',
])
def test_notation_components_expand_to_the_exact_written_execution_with_a_reference_for_every_move(source):
    study = commutator_study(source)
    assert study is not None
    parsed = parse_algorithm(source)
    assert study.moves == parsed.moves == parse_algorithm(study.source).moves
    assert algorithm_states(parse_algorithm(study.source))[-1] == algorithm_states(parsed)[-1]
    assert study.components[0].start == 0 and study.components[-1].end == len(parsed.moves)
    for a, b in zip(study.components, study.components[1:]): assert a.end == b.start
    for i, component in enumerate(study.components):
        assert all(m.components == frozenset((i,)) for m in study.tracked[component.start:component.end])
    leaves = {t.reference for t in study.tokens if t.reference >= 0}
    assert all(m.references and m.references <= leaves for m in study.tracked)


def test_all_supplied_commutators_and_random_wide_slice_rotation_notation_keep_their_actual_execution():
    sources = {notation for _, _, notation in ALL_SUBMISSIONS if '[' in notation}
    rng = random.Random(2390)
    turns = ('R', "D'", 'U2', 'Fw', 'Rw2', "M'", 'S', 'x', 'y2')
    for _ in range(64):
        chunks = [' '.join(rng.choice(turns) for _ in range(rng.randint(1, 4))) for _ in range(3)]
        sources.add(f'[{chunks[0]}: [{chunks[1]}, {chunks[2]}]]')
    for source in sources:
        study = commutator_study(source)
        assert study and study.moves == parse_algorithm(source).moves
        clean = simplify_moves(study.moves)
        aligned = align_notation(study, clean)
        assert aligned is not None and tuple(m.move for m in aligned) == clean
        assert all(m.components <= frozenset(range(len(study.components))) for m in aligned)


def test_combined_turns_keep_both_contributing_components_and_raw_recovery_never_substitutes_another_execution():
    study = commutator_study(SOURCE)
    assert [c.label for c in study.components] == ['Setup','A','B','Undo A','Undo B','Undo setup']
    assert [c.end - c.start for c in study.components] == [1,1,3,1,3,1]
    clean = align_notation(study, simplify_moves(study.moves))
    assert clean[-1].move == 'R2' and clean[-1].components == frozenset((4,5))
    assert len(clean[-1].references) == 2
    plain = ' '.join(parse_algorithm("[R, U' L' U]").moves)
    recovered = commutator_study(plain)
    assert recovered and execution_signature(recovered.moves) == execution_signature(parse_algorithm(plain).moves)
    assert commutator_study('R U F') is None
    assert align_notation(study, ('R',)) is None


@pytest.mark.parametrize('source', ['', 'Q', '[R,U', 'R' * 8001, '[' * 18 + 'R,U' + ']' * 18])
def test_invalid_or_oversized_notation_is_not_published_as_a_commutator(source):
    assert commutator_study(source) is None


def active_tokens(cube):
    return [s.text for s in cube.notation_text.spans if s.style.decoration == ft.TextDecoration.UNDERLINE]


def enable_components(cube):
    cube.playback_mode.value = 'components'
    cube.playback_mode.on_select(None)
    cube.mode_picker.value = '2D'


@pytest.mark.parametrize('simultaneous', [False, True])
def test_component_mode_pauses_after_each_complete_part_and_keeps_both_trackers_on_the_last_executed_move(simultaneous):
    cube = AlgorithmCube();cube.load(SOURCE)
    original = cube.original_algorithm
    assert cube.algorithm.moves == simplify_moves(original.moves) and len(cube.states) == 10
    cube.set_simultaneous_moves(simultaneous)
    enable_components(cube)
    assert cube.algorithm.moves == original.moves and len(cube.states) == 11
    clock = [0.0]
    async def sleep(delay): clock[0] += delay
    with patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep), \
         patch('ui.components.algorithm_cube.time.perf_counter', side_effect=lambda: clock[0]):
        for ref in cube._components:
            start = cube.index
            asyncio.run(cube._play(cube._token, len(cube.algorithm.moves)))
            component = ref[0]
            assert cube.index == component.end and cube._boundary_component == ref and not cube.playing
            assert cube.component_status.value == component.label + ' complete'
            assert active_tokens(cube)
            assert sum(s.style.decoration == ft.TextDecoration.UNDERLINE for s in cube.move_text.spans) == 1
            assert clock[0] == pytest.approx(component.end * .6)
            if component.label == 'B': assert cube.index - start == 3  # No pause after each individual move.
            if cube.index < len(cube.algorithm.moves):
                assert cube.continue_button.visible and cube.stage_status.visible
                fake = SimpleNamespace(run_task=Mock())
                with patch.object(cube, '_page', return_value=fake), patch.object(cube, '_update'):
                    cube.continue_button.on_click(None)
                assert cube._boundary_component is None and cube.playing
            else: assert not cube.continue_button.visible
    assert cube.original_algorithm is original and cube.states[-1] == algorithm_states(original)[-1]


def test_undo_phase_highlights_the_corresponding_written_move_in_reverse_order_and_full_mode_tracks_merged_turns():
    cube = AlgorithmCube();cube.load(SOURCE);enable_components(cube)
    undo_b = next(c[0] for c in cube._components if c[0].label == 'Undo B')
    cube.seek(undo_b.start)
    assert active_tokens(cube) == ['R'] and 'Undo B' in cube.component_status.value
    assert cube.algorithm.moves[cube.index] == "R'"
    cube.seek(undo_b.start + 1)
    assert active_tokens(cube) == ["D'"] and cube.algorithm.moves[cube.index] == 'D'
    cube.playback_mode.value = 'full';cube._change_playback_mode()
    cube.seek(len(cube.algorithm.moves) - 1)
    assert cube.algorithm.moves[cube.index] == 'R2'
    assert 'Undo B + Undo setup' in cube.component_status.value and len(active_tokens(cube)) == 2


def test_simultaneous_moves_group_inside_a_component_and_never_join_across_component_boundaries():
    cube = AlgorithmCube();cube.load('[U D,R L]');cube.set_simultaneous_moves(True);enable_components(cube)
    assert [s.caption for s in cube._steps] == ['(U D)','(R L)',"(D' U')","(L' R')"]
    for beat in cube._steps:
        assert any(c[0].start <= beat.start < beat.end <= c[0].end for c in cube._components)
    cube.load('[U,D]');assert cube.component_mode and len(cube._steps) == 4


@pytest.mark.parametrize('buffer', ['UFR','LUB'])
def test_walkthrough_component_offsets_jump_controls_edge_modes_and_editor_return_preserve_the_exact_plan(buffer):
    repo, view, w = open_walkthrough(buffer=buffer)
    plan, before = w.plan, deepcopy(repo.data.to_dict())
    w._select_step(1)
    label = w.viewer._active_stage().label
    enable_components(w.viewer)
    cube = w.viewer
    assert cube._active_stage().label == label and cube.index == cube._active_stage().start
    assert [s.label for s in cube.algorithm.stages] == [s.label for s in plan.algorithm.stages]
    assert cube.states[-1] == plan.final
    for i, stage in enumerate(cube.algorithm.stages):
        w._select_step(i)
        assert cube.index == stage.start and len(cube.affected) == 3
    w._jump(-1)
    assert cube.index == cube.algorithm.stages[-2].start
    w._select_step(0)
    async def sleep(delay): pass
    with patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep):
        asyncio.run(cube._play(cube._token, len(cube.algorithm.moves)))
    index, held, affected = cube.index, cube._boundary_component, cube.affected
    assert held
    for mode in ('solved','hidden','scrambled'):
        w.edge_view.value = mode;w._edge_changed()
        assert cube.component_mode and cube.index == index and cube._boundary_component == held
        assert cube.affected == affected and active_tokens(cube)
    w._open_step_case(plan.steps[0].parts[0])
    assert view.mode == 'library' and not cube.playing
    view._set_mode('walkthrough')
    assert w.plan is plan and cube.component_mode and cube.index == index
    assert repo.data.to_dict() == before


def test_components_can_fall_back_to_one_moves_only_algorithm_without_borrowing_a_different_commutator():
    alg = Algorithm('R U F R U', ('R','U','F','R','U'), (Stage('One',0,3),Stage('Two',3,5)))
    cube = AlgorithmCube()
    cube.load(alg, preserve_stages=True, stage_notations={'One':None, 'Two':'[R,U]'})
    # The mismatching expression is rejected, so an unavailable form cannot
    # replace the actual algorithm or activate misleading study playback.
    assert not cube.playback_mode.visible and not cube.component_mode and cube.algorithm is alg
    cube.load('R U F')
    assert not cube.notation_text.visible and not cube.playback_mode.visible


def test_mixed_walkthroughs_keep_unknown_algorithms_as_one_component_and_continue_into_known_notation():
    known = parse_algorithm('[R,U]')
    moves = ('R','U','F') + known.moves
    alg = Algorithm(' '.join(moves), moves, (Stage('One',0,3),Stage('Two',3,len(moves))))
    cube = AlgorithmCube();cube.load(alg, preserve_stages=True, stage_notations={'One':None,'Two':'[R,U]'})
    enable_components(cube)
    assert len(cube._components) == 5 and cube.component_status.value == 'Algorithm · moves only'
    async def sleep(delay): pass
    with patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep):
        asyncio.run(cube._play(cube._token, len(moves)))
        assert cube.index == 3 and cube._boundary_stage.label == 'One'
        asyncio.run(cube._play(cube._token, len(moves)))
    assert cube.index == 4 and cube._boundary_component[0].label == 'A'
    assert cube.notation_text.visible and cube.states[-1] == algorithm_states(alg)[-1]


def test_fully_cancelled_commutators_still_offer_written_component_study_without_empty_tracker_errors():
    cube = AlgorithmCube();cube.load('[R,R]')
    assert not cube.algorithm.moves and cube.component_status.value == 'Identity · no moves'
    enable_components(cube)
    assert cube.algorithm.moves == ('R','R',"R'","R'") and len(cube._components) == 4
    assert cube.states[-1] == cube.states[0]


def test_component_choice_survives_an_empty_playground_and_applies_to_the_lesson_without_saving_preferences():
    _, repo, _, view = open_library()
    before = deepcopy(repo.data.to_dict())
    cube = view.viewer;enable_components(cube)
    view._set_mode('explorer')
    assert not cube.playback_mode.visible and not cube.component_mode
    view.playground_converter.load(SOURCE, notify=True)
    assert cube.component_mode and cube.notation_text.visible and cube._components
    view._set_mode('lesson')
    assert cube.component_mode and [c[0].label for c in cube._components] == ['A','B','Undo A','Undo B']
    assert repo.data.to_dict() == before


def test_mode_changes_and_stale_tasks_cancel_animation_and_restart_only_the_current_walkthrough_algorithm():
    _, _, w = open_walkthrough()
    cube = w.viewer;w._select_step(1)
    label, token = cube._active_stage().label, cube._token
    async def sleep(delay):
        cube.playback_mode.value = 'components';cube._change_playback_mode()
    with patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep):
        asyncio.run(cube._play(token, len(cube.algorithm.moves)))
    assert not cube.playing and cube._moving is None and cube._active_stage().label == label
    assert cube.index == cube._active_stage().start
    before = cube.index
    asyncio.run(cube._play(token, len(cube.algorithm.moves)))
    assert cube.index == before and cube._moving is None


@pytest.mark.parametrize('dark', [False, True])
def test_notation_and_component_controls_follow_the_palette_and_keep_the_cube_viewport(dark):
    repo, view, w = open_walkthrough()
    repo.data.dark_mode = dark;view.refresh()
    cube = w.viewer;viewport = cube._viewport
    enable_components(cube);cube._update()
    assert cube._viewport == viewport
    assert cube.playback_mode.color == ('#F0F4F3' if dark else '#182B25')
    assert cube.notation_text.visible and cube.component_status.visible
    assert all(s.style.color.startswith('#') for s in cube.notation_text.spans)
    b = next(c[0] for c in cube._components if c[0].label == 'B')
    cube.seek(b.start);cube._update()
    assert cube.component_status.color == ('#FFD08A' if dark else '#825000')
