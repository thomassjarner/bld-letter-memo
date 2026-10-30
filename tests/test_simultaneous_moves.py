"""Exact opposite-layer animation, grouping boundaries and saved playback preference."""
import asyncio
from copy import deepcopy
import itertools
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import flet as ft
import pytest

from core.algorithm_playback import can_turn_together, playback_steps
from core.algorithms import algorithm_states, apply_move, move_spec, parse_algorithm
from data.models import AppData, CURRENT_VERSION
from data.shared_preferences_repository import SharedPreferencesAppDataRepository
from test_case_library import open_library
from test_navigation import click_nav, no_client_mount, walk
from ui.components.algorithm_cube import AlgorithmCube
from ui.components.cube_projection import project_cube


def captions(cube):
    return ''.join(span.text for span in cube.move_text.spans).strip()


def test_all_outer_face_pairs_group_only_disjoint_layers_and_keep_the_original_sequence_and_effect():
    state = algorithm_states(parse_algorithm("R U' F2"))[-1]
    turns = [face + suffix for face in 'URFDLB' for suffix in ('', "'", '2')]
    for first, second in itertools.product(turns, repeat=2):
        a, b = move_spec(first), move_spec(second)
        expected = a[0] == b[0] and set(a[1]).isdisjoint(b[1])
        assert can_turn_together(first, second) == expected
        algorithm = parse_algorithm(first + ' ' + second)
        steps = playback_steps(algorithm, True)
        assert tuple(move for step in steps for move in step.moves) == algorithm.moves
        assert (len(steps) == 1) == expected
        assert len(playback_steps(algorithm, False)) == 2
        if expected:
            assert apply_move(apply_move(state, first), second) == apply_move(apply_move(state, second), first)


@pytest.mark.parametrize('source', ['U R', 'U F D', 'Rw L', 'R Lw', 'Rw Lw', 'M E', 'x R', 'F S'])
def test_nonadjacent_or_non_outer_turns_remain_separate(source):
    alg = parse_algorithm(source)
    assert all(len(step.moves) == 1 for step in playback_steps(alg, True))


def test_original_commutator_stages_are_not_joined_and_still_play_independently():
    cube = AlgorithmCube()
    cube.set_simultaneous_moves(True)
    cube.load("[R: [U D, F B]]")
    cube.structure_switch.value = True
    cube._change_structure()
    assert [len(step.moves) for step in cube._steps] == [1, 2, 2, 2, 2, 1]
    for step in cube._steps:
        assert any(stage.start <= step.start < step.end <= stage.end for stage in cube.algorithm.stages)
    # Opposite turns across the A/B boundary keep their separate lesson roles.
    assert len(playback_steps(parse_algorithm('[U,D]'), True)) == 4
    assert cube.simultaneous_moves


def test_grouped_captions_stepping_and_toggling_keep_atomic_counts_exact_states_and_source():
    source = "D' U' R L2 F' B R"
    cube = AlgorithmCube()
    cube.load(source)
    states = cube.states
    assert captions(cube) == source
    cube.set_simultaneous_moves(True)
    assert captions(cube) == "(D' U') (R L2) (F' B) R"
    assert parse_algorithm(captions(cube)).moves == cube.algorithm.moves
    assert cube.counter.value == '0 / 7'
    cube._step(1)
    assert cube.index == 2 and cube.counter.value == '2 / 7'
    cube._step(-1)
    assert cube.index == 0
    cube.seek(3)
    cube._step(-1)
    assert cube.index == 2
    cube.seek(1)
    cube._step(1)
    assert cube.index == 2
    cube.set_simultaneous_moves(False)
    assert captions(cube) == source and cube.index == 2
    assert cube.states is states and cube.original_algorithm.source == source
    assert cube.states[-1] == algorithm_states(parse_algorithm(source))[-1]


def signature(tiles):
    return sorted((tile.color, tile.label, tile.outline,
                   tuple(sorted((round(x, 5), round(y, 5)) for x, y in tile.points))) for tile in tiles)


def test_every_simultaneous_direction_and_double_turn_reaches_the_exact_combined_cube_geometry():
    state = algorithm_states(parse_algorithm("R U' F2"))[-1]
    for pair in ('UD', 'DU', 'RL', 'LR', 'FB', 'BF'):
        for a, b in itertools.product(('', "'", '2'), repeat=2):
            moves = pair[0] + a, pair[1] + b
            before = project_cube(state, 460, 300)
            start = project_cube(state, 460, 300, moving=moves, fraction=0)
            middle = project_cube(state, 460, 300, moving=moves, fraction=.5)
            final = project_cube(state, 460, 300, moving=moves, fraction=1)
            expected = apply_move(apply_move(state, moves[0]), moves[1])
            assert signature(start) == signature(before)
            assert signature(final) == signature(project_cube(expected, 460, 300))
            assert signature(middle) != signature(start)
            assert all(-1 <= x <= 461 and -1 <= y <= 301 for tile in middle for x, y in tile.points)


@pytest.mark.parametrize('mode', ['3D', '2D'])
def test_playback_turns_both_faces_in_one_beat_and_finishes_at_the_unchanged_cube_state(mode):
    cube = AlgorithmCube()
    cube.set_simultaneous_moves(True)
    cube.load("U D' R L2")
    cube.mode_picker.value = mode
    clock, seen = [0.0], []
    async def sleep(delay): clock[0] += delay
    def redraw(update=True):
        if cube._moving is not None: seen.append(cube._moving)
    with patch('ui.components.algorithm_cube.time.perf_counter', side_effect=lambda: clock[0]), \
         patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep), patch.object(cube, '_redraw', redraw):
        asyncio.run(cube._play(cube._token, 4))
    assert set(seen) == {('U', "D'"), ('R', 'L2')}
    assert clock[0] == pytest.approx(1.2)
    assert cube.index == 4 and cube._moving is None and not cube.playing
    assert cube.states[cube.index] == algorithm_states(parse_algorithm("U D' R L2"))[-1]


def test_playing_to_an_atomic_boundary_inside_a_pair_never_overshoots():
    cube = AlgorithmCube()
    cube.set_simultaneous_moves(True)
    cube.load("U D'")
    cube.mode_picker.value = '2D'
    async def sleep(delay): pass
    with patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep):
        asyncio.run(cube._play(cube._token, 1))
        assert cube.index == 1 and cube.states[1] == algorithm_states(parse_algorithm('U'))[-1]
        asyncio.run(cube._play(cube._token, 2))
    assert cube.index == 2


def test_changing_the_preference_cancels_an_in_progress_pair_without_publishing_a_stale_frame():
    cube = AlgorithmCube()
    cube.set_simultaneous_moves(True)
    cube.load("U D'")
    async def sleep(delay): cube.set_simultaneous_moves(False)
    with patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep):
        asyncio.run(cube._play(cube._token, 2))
    assert not cube.simultaneous_moves and cube.index == 0 and cube._moving is None
    assert captions(cube) == "U D'"


def test_the_only_simultaneous_switch_is_in_settings_and_the_saved_choice_applies_to_all_method_views():
    page, repo, _, view = open_library()
    before = deepcopy(repo.data.to_dict())
    settings = click_nav(page, 'Settings')
    switch = settings.simultaneous_moves_switch
    assert isinstance(switch, ft.Switch) and switch.label == 'Simultaneous moves' and not switch.value
    switch.value = True
    switch.on_change(SimpleNamespace(control=switch))
    assert repo.data.simultaneous_moves
    click_nav(page, 'Method Library')
    assert view.viewer.simultaneous_moves
    view._set_mode('explorer')
    view.playground_converter.load("U D'", notify=True)
    assert captions(view.viewer) == "(U D')"
    assert not any(isinstance(c, ft.Switch) and c.label == 'Simultaneous moves' for c in walk(view))
    view._set_mode('lesson')
    assert view.viewer.simultaneous_moves
    assert [stage.label for stage in view.viewer.algorithm.stages] == ['A', 'B', 'Undo A', 'Undo B']
    restored = AppData.from_dict(json.loads(json.dumps(repo.data.to_dict())))
    assert restored.simultaneous_moves
    decoded, _ = SharedPreferencesAppDataRepository._decode(json.dumps(repo.data.to_dict()))
    assert decoded.simultaneous_moves
    for name, value in before.items():
        if name != 'simultaneous_moves': assert restored.to_dict()[name] == value


def test_old_backups_default_off_and_import_updates_the_settings_switch_without_losing_other_data():
    page, repo, _, view = open_library()
    old = deepcopy(repo.data.to_dict())
    old.pop('simultaneous_moves')
    old['version'] = 17
    old['global_words'] = {'AB': 'Kept'}
    restored = AppData.from_dict(old)
    assert CURRENT_VERSION == 18 and not restored.simultaneous_moves
    for name, value in old.items():
        if name != 'version': assert restored.to_dict()[name] == value
    assert not AppData.from_dict(dict(old, simultaneous_moves='false')).simultaneous_moves
    settings = click_nav(page, 'Settings')
    settings.simultaneous_moves_switch.value = True
    settings.theme_callback = settings.navigation_callback = None
    settings._pending_import = ('old.json', json.dumps(old).encode())
    fake = SimpleNamespace(update=Mock())
    with patch('flet.controls.base_control.BaseControl.page', property(lambda self: fake)):
        settings._confirm_import(None)
    assert not settings.simultaneous_moves_switch.value and repo.data.to_dict() == restored.to_dict()
