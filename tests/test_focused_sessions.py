"""Focused states must be legal, honor parity/settings, and preserve histories."""
from copy import deepcopy
import json
import random
import shutil
from types import SimpleNamespace
from unittest.mock import patch

import flet as ft
import pytest

from core.cube_definitions import CATEGORY_STICKER_ORDER, EDGE_PIECES
from core.focused_scrambles import (CORNER_FACELETS, EDGE_FACELETS, EDGE_NAMES, SOLVED,
    constructed_scramble, generate_focused, in_scramble_frame, parity_algorithm,
    permutation_parity, sample_state, state_facelets)
from core.scramble_generator import ScrambleGenerator
from core.tracer import ScrambleTracer, _at, _memo_swap_edge_identities, _solved, simulate
from data.models import AppData, PracticeSolve
from test_navigation import MemoryRepository, click_nav, mount, no_client_mount
from test_progressive_memo import letter_scheme


def assert_focused(scramble, category, scheme, expected_odd=None):
    state = simulate(scramble, scheme.memo_up, scheme.memo_front, scheme.scramble_from_own_orientation)
    result = ScrambleTracer().trace(scramble, scheme)
    if category == 'edges':
        assert all(_at(state, p) == p for p in CATEGORY_STICKER_ORDER['corners'])
        assert not result.corner_targets and not result.corner_orientation
        assert not result.three_style_parity_applied
        assert result.edge_targets or result.edge_orientation
    else:
        expected = (_memo_swap_edge_identities(_solved(), scheme.edges.buffer_piece, scheme.edge_parity_partner)
                    if result.three_style_parity_applied else _solved())
        assert all(_at(state, p) == _at(expected, p) for p in CATEGORY_STICKER_ORDER['edges'])
        assert not result.edge_targets and not result.edge_orientation
        assert result.corner_targets or result.corner_orientation
        if expected_odd is not None:
            assert result.three_style_parity_applied == expected_odd
    return result


def decode(facelets, positions):
    homes = [''.join(SOLVED[i] for i in slot) for slot in positions]
    permutation, orientation = [], []
    for slot in positions:
        colors = ''.join(facelets[i] for i in slot)
        home = next(i for i, value in enumerate(homes) if set(value) == set(colors))
        permutation.append(home)
        orientation.append(colors.index(homes[home][0]))
    return permutation, orientation


@pytest.mark.parametrize('category', ['edges', 'corners'])
@pytest.mark.parametrize('three_style', [False, True])
def test_sampled_states_obey_permutation_orientation_and_category_constraints(category, three_style):
    scheme = letter_scheme()
    scheme.three_style_enabled = three_style
    scheme.edges.buffer_piece, scheme.edges.buffer_sticker = 'FR', 'RF'
    scheme.edge_parity_partner = 'BL'
    rng = random.Random(37)
    odd_count = 0
    seen = set()
    for _ in range(400):
        facelets, odd = sample_state(category, rng, scheme)
        cp, co = decode(facelets, CORNER_FACELETS)
        ep, eo = decode(facelets, EDGE_FACELETS)
        assert sum(co) % 3 == sum(eo) % 2 == 0
        assert permutation_parity(cp) == permutation_parity(ep) == int(odd)
        if category == 'edges':
            assert cp == list(range(8)) and co == [0] * 8
        else:
            expected = list(range(12))
            if odd:
                a, b = EDGE_NAMES.index('FR'), EDGE_NAMES.index('BL')
                expected[a], expected[b] = expected[b], expected[a]
            assert ep == expected and eo == [0] * 12
        odd_count += odd
        seen.add(facelets)
    assert len(seen) == 400
    if category == 'corners' and three_style:
        assert 160 <= odd_count <= 240  # deterministic sample of the fair parity coin
    else:
        assert odd_count == 0


def test_parity_construction_matches_the_memo_swap_for_all_132_edge_pairs():
    for buffer in EDGE_PIECES:
        for helper in EDGE_PIECES:
            if buffer == helper:
                continue
            state = simulate(parity_algorithm(buffer, helper))
            expected = _memo_swap_edge_identities(_solved(), buffer, helper)
            assert all(_at(state, p) == _at(expected, p) for p in CATEGORY_STICKER_ORDER['edges'])


@pytest.mark.parametrize('category,odd', [('edges', False), ('corners', False), ('corners', True)])
@pytest.mark.parametrize('own', [False, True])
@pytest.mark.parametrize('orientation', [('W', 'G'), ('Y', 'B')])
def test_portable_construction_preserves_the_other_category_and_parity(category, odd, own, orientation):
    scheme = letter_scheme()
    scheme.three_style_enabled = True
    scheme.edges.buffer_piece, scheme.edges.buffer_sticker = 'FR', 'RF'
    scheme.edge_parity_partner = 'BL'
    scheme.memo_up, scheme.memo_front = orientation
    scheme.scramble_from_own_orientation = own
    before = deepcopy(scheme.to_dict())
    for seed in range(3):
        scramble = in_scramble_frame(constructed_scramble(category, random.Random(seed), odd, scheme), scheme)
        assert_focused(scramble, category, scheme, expected_odd=odd)
    assert scheme.to_dict() == before


@pytest.mark.skipif(shutil.which('node') is None, reason='Native solver bridge needs Node; portable generation is tested separately')
@pytest.mark.parametrize('category', ['edges', 'corners'])
def test_real_solver_generates_the_exact_sampled_state_in_at_most_21_moves(category):
    scheme = letter_scheme()
    scheme.three_style_enabled = True
    for seed in (4, 5):
        facelets, odd = sample_state(category, random.Random(seed), scheme)
        with patch('core.focused_scrambles.sample_state', return_value=(facelets, odd)):
            scramble = generate_focused(category, random.Random(seed), scheme)
        assert len(scramble.split()) <= 21
        assert state_facelets(simulate(scramble)) == facelets
        assert_focused(scramble, category, scheme, expected_odd=odd)


@pytest.mark.parametrize('bad_solution', [None, 'Error 7', 'R U', ''])
def test_unavailable_or_invalid_shortening_cannot_produce_an_unrestricted_scramble(bad_solution):
    scheme = letter_scheme()
    scheme.three_style_enabled = True
    with patch('core.focused_scrambles.solve_facelets', return_value=bad_solution):
        for category in ('edges', 'corners'):
            scramble = ScrambleGenerator(random.Random(5)).generate(category=category, scheme=scheme)
            assert_focused(scramble, category, scheme)


def test_normal_scramble_generation_and_missing_scheme_keep_working():
    assert ScrambleGenerator(random.Random(5)).generate() == ScrambleGenerator(random.Random(5)).generate(category='all')
    assert len(ScrambleGenerator(random.Random(5)).generate(add_bld_orientation=False).split()) == 22
    with patch('core.focused_scrambles.solve_facelets', return_value=None):
        for category in ('edges', 'corners'):
            algorithm = ScrambleGenerator(random.Random(5)).generate(category=category)
            scheme = letter_scheme()
            assert_focused(algorithm, category, scheme)


def timer_with_history():
    page, repo = mount()
    scheme = letter_scheme()
    scheme.three_style_enabled = True
    scheme.edge_parity_partner = 'FR'
    repo.data.schemes = {scheme.name: scheme}
    repo.data.active_scheme = scheme.name
    for index, name in enumerate(('Session 1', 'Session 2', 'Session 3')):
        repo.data.practice_sessions[name] = [PracticeSolve(centiseconds=1000 + index,
            scramble=f'R U{index}', dnf=index == 1, plus2=index == 2)]
    return page, repo, click_nav(page, 'Timer')


def switch(timer, session):
    timer.session_dropdown.value = session
    timer.session_dropdown.on_select(SimpleNamespace(control=timer.session_dropdown))


def test_session_labels_change_without_renaming_ids_or_modifying_history_and_backups():
    _, repo, timer = timer_with_history()
    before = deepcopy(repo.data.to_dict())
    assert [(o.key, o.text) for o in timer.session_dropdown.options] == [
        ('Session 1', 'Session 1'), ('Session 2', 'edges only'), ('Session 3', 'corners only')]
    for name in ('Session 2', 'Session 3', 'Session 1'):
        switch(timer, name)
        assert repo.data.active_practice_session == name
        assert repo.data.practice_sessions == AppData.from_dict(before).practice_sessions
        restored = AppData.from_dict(json.loads(json.dumps(repo.data.to_dict())))
        assert restored.practice_sessions == repo.data.practice_sessions
        assert restored.active_practice_session == name
    assert repo.data.to_dict() == before


@pytest.mark.parametrize('session,category', [('Session 2', 'edges'), ('Session 3', 'corners')])
def test_switch_next_previous_stop_and_penalties_use_the_focused_session(session, category):
    _, repo, timer = timer_with_history()
    before = deepcopy(repo.data.practice_sessions)
    switch(timer, session)
    scheme = timer.state.active_scheme
    original = timer.current_scramble
    assert_focused(original, category, scheme)
    timer._new_scramble()
    second = timer.current_scramble
    assert_focused(second, category, scheme)
    timer._previous_scramble()
    assert timer.current_scramble == original
    timer._new_scramble()
    assert timer.current_scramble == second
    runner = SimpleNamespace(run_task=lambda *args: None)
    with patch.object(type(timer), 'page', property(lambda self: runner)), \
            patch.object(timer, '_safe_update'), patch.object(timer, '_focus_keyboard_listener'):
        timer._start_timer(10)
        timer._stop_timer(12.34)
        assert repo.data.practice_solves[-1].scramble == second
        assert repo.data.practice_solves[-1].centiseconds == 234
        assert_focused(timer.current_scramble, category, scheme)
        timer._mark_last('plus2')
        assert repo.data.practice_solves[-1].plus2
        timer._mark_last('dnf')
        assert repo.data.practice_solves[-1].dnf
    for name, values in before.items():
        assert repo.data.practice_sessions[name][:(len(values))] == values
        assert len(repo.data.practice_sessions[name]) == len(values) + (name == session)


def test_running_solve_blocks_session_switch_and_setting_changes_refresh_focused_scrambles():
    _, repo, timer = timer_with_history()
    timer.running = True
    before = deepcopy(repo.data.to_dict())
    original = timer.current_scramble
    switch(timer, 'Session 2')
    assert timer.session_dropdown.value == 'Session 1'
    assert repo.data.to_dict() == before and timer.current_scramble == original
    timer.running = False
    switch(timer, 'Session 3')
    timer._new_scramble()
    timer.state.active_scheme.memo_up, timer.state.active_scheme.memo_front = 'Y', 'B'
    timer.state.active_scheme.edge_parity_partner = 'BL'
    timer.refresh(update=False)
    assert len(timer.scramble_stack) == 1 and timer.scramble_index == 0
    assert_focused(timer.current_scramble, 'corners', timer.state.active_scheme)
    with patch.object(timer.generator, 'generate') as generate:
        timer.state.active_scheme.corners.stickers['UBR'] = 'Z'
        timer.refresh(update=False)
        generate.assert_not_called()


def test_invalid_parity_settings_do_not_switch_sessions_or_allow_empty_timed_solves():
    _, repo, timer = timer_with_history()
    timer.state.active_scheme.edge_parity_partner = 'DF'
    original = timer.current_scramble
    switch(timer, 'Session 3')
    assert repo.data.active_practice_session == 'Session 1'
    assert timer.current_scramble == original and 'different parity helper' in timer.status_text.value
    # Loading/importing a focused session with invalid settings must not crash
    # startup or allow a stale full scramble to be timed as corner practice.
    repo.data.active_practice_session = 'Session 3'
    timer.refresh(update=False)
    assert timer._scramble_error
    timer._start_timer(10)
    assert not timer.running
    timer.state.active_scheme.edge_parity_partner = 'FR'
    timer.refresh(update=False)
    assert not timer._scramble_error
    assert_focused(timer.current_scramble, 'corners', timer.state.active_scheme)


@pytest.mark.parametrize('session,invalid', [('Session 2', False), ('Session 3', True)])
def test_saved_focused_session_loads_at_startup_without_changing_its_history(session, invalid):
    repo = MemoryRepository()
    scheme = letter_scheme()
    scheme.three_style_enabled = True
    if invalid:
        scheme.edge_parity_partner = scheme.edges.buffer_piece
    repo.data.schemes = {scheme.name: scheme}
    repo.data.active_scheme = scheme.name
    repo.data.active_practice_session = session
    repo.data.practice_solves = [PracticeSolve(centiseconds=2500, scramble='R U')]
    before = deepcopy(repo.data.to_dict())
    with patch('test_navigation.MemoryRepository', return_value=repo):
        page, loaded = mount()
    timer = click_nav(page, 'Timer')
    assert loaded is repo and timer.session_dropdown.value == session
    assert repo.data.to_dict() == before
    if invalid:
        assert timer._scramble_error and not timer.current_scramble
        timer._start_timer(10)
        assert not timer.running
    else:
        assert_focused(timer.current_scramble, 'edges', scheme)


def test_imported_session_change_clears_stale_result_buttons_before_they_can_edit_another_history():
    _, repo, timer = timer_with_history()
    timer.last_solve_index = 0
    timer.plus2_button.disabled = False
    before = deepcopy(repo.data.practice_sessions)
    repo.data.active_practice_session = 'Session 2'
    timer.refresh(update=False)
    assert timer.last_solve_index is None
    assert all(button.disabled for button in (timer.memo_button, timer.success_button,
                                             timer.plus2_button, timer.dnf_button))
    timer._mark_last('plus2')
    assert repo.data.practice_sessions == before
