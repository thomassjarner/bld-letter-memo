"""Real tracing, stage order, timing, input, feedback and persistence regressions."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import flet as ft
import pytest

from core.cube_definitions import CORNER_PIECES, EDGE_PIECES, CORNER_STICKER_ORDER, EDGE_STICKER_ORDER
from core.progressive_memo import (CategoryMemo, ProgressivePlan, ProgressiveRun, align_letters,
                                    build_plan, normalize_letters, score_recall)
from core.scramble_generator import ScrambleGenerator
from core.tracer import ScrambleError, ScrambleTracer
from data.models import AppData, ProgressiveMemoAttempt, ProgressiveRecall
from data.shared_preferences_repository import SharedPreferencesAppDataRepository
from ui.state import AppState
from test_gold_scrambles import GOLD_TESTS, make_gold_scheme
from test_navigation import click_nav, mount, no_client_mount, walk
from test_theme_contrast import contrast


def letter_scheme():
    scheme = make_gold_scheme()
    for cat, order, pieces in ((scheme.corners, CORNER_STICKER_ORDER, CORNER_PIECES),
                               (scheme.edges, EDGE_STICKER_ORDER, EDGE_PIECES)):
        cat.stickers = {sticker: chr(65 + i) for i, sticker in enumerate(order)}
        for sticker in pieces[cat.buffer_piece]:
            cat.stickers[sticker] = 'BUFFER'
    return scheme


def simple_plan():
    corners = CategoryMemo('corners', ('AB', 'C'), ('DE', 'FG'))
    edges = CategoryMemo('edges', ('HI',), ())
    return ProgressivePlan('R U', 'Test', {}, 'CE', 'EC', (corners, edges), edges.prompts + corners.prompts)


@pytest.mark.parametrize('case', GOLD_TESTS, ids=[case['name'] for case in GOLD_TESTS])
@pytest.mark.parametrize('mode', ['visual', 'trace'])
def test_plan_reuses_exact_real_scramble_tracing_and_groups_orientation(case, mode):
    scheme = letter_scheme()
    scheme.corners.orientation_memo = scheme.edges.orientation_memo = mode
    scheme.corners.cycle_break_priority = list(reversed(CORNER_PIECES))
    scheme.edges.cycle_break_priority = list(reversed(EDGE_PIECES))
    scheme.corners.cycle_break_stickers = {p: sorted(stickers)[-1] for p, stickers in CORNER_PIECES.items()}
    scheme.edges.cycle_break_stickers = {p: sorted(stickers)[-1] for p, stickers in EDGE_PIECES.items()}
    snapshot = deepcopy(scheme.to_dict())
    plan = build_plan(case['scramble'], scheme)
    result = ScrambleTracer().trace(case['scramble'], scheme)
    for category, prefix in zip(plan.categories, ('corner', 'edge')):
        letters = getattr(result, prefix + '_letters')
        flags = getattr(result, prefix + '_orientation_target_flags')
        assert ''.join(category.ordinary_pairs + category.orientation_pairs) == ''.join(letters)
        assert ''.join(category.orientation_pairs) == ''.join(letter for letter, flag in zip(letters, flags) if flag)
        assert len([p for p in category.prompts if p.kind == 'orientation']) == bool(category.orientation_pairs)
        if mode == 'visual':
            assert not category.orientation_pairs
        assert all('(' not in p.letters and '#' not in p.letters for p in category.prompts)
    assert scheme.to_dict() == snapshot
    scheme.corners.stickers['DFR'] = 'Z'
    assert plan.scheme_snapshot == snapshot


def test_memo_and_recall_orders_are_independent_and_default_to_ce_ec():
    scheme = letter_scheme()
    for memo, execution in (('', ''), ('CE', 'CE'), ('EC', 'CE'), ('EC', 'EC')):
        scheme.memo_order, scheme.execution_order = memo, execution
        plan = build_plan(GOLD_TESTS[1]['scramble'], scheme)
        assert ''.join(category.category[0].upper() for category in plan.categories) == (memo or 'CE')
        categories = [p.category for p in plan.recall_prompts]
        assert categories[0][0].upper() == (execution or 'EC')[0]
        assert categories[-1][0].upper() == (execution or 'EC')[-1]


def test_plan_respects_orientation_parity_and_temporary_override_without_mutating_preferences():
    scheme = letter_scheme()
    scheme.memo_up, scheme.memo_front = 'Y', 'B'
    scheme.scramble_from_own_orientation = True
    scheme.three_style_enabled = True
    scramble = GOLD_TESTS[1]['scramble']
    normal = ScrambleTracer().trace(scramble, scheme)
    first_break = next(b for b in normal.corner_cycle_breaks if len(b.options) > 1)
    overrides = {first_break.break_index: first_break.options[-1][0]}
    snapshot = deepcopy(scheme.to_dict())
    expected = ScrambleTracer().trace(scramble, scheme, corner_cycle_break_overrides=overrides)
    plan = build_plan(scramble, scheme, corner_cycle_break_overrides=overrides)
    assert ''.join(plan.categories[0].ordinary_pairs) == ''.join(expected.corner_letters)
    assert ''.join(plan.categories[1].ordinary_pairs) == ''.join(expected.edge_letters)
    assert scheme.to_dict() == snapshot


def test_start_rejects_missing_buffers_letters_and_empty_letter_memo():
    scheme = letter_scheme()
    scheme.corners.buffer_sticker = scheme.corners.buffer_piece = None
    with pytest.raises(ScrambleError, match='buffer'):
        build_plan('R U', scheme)
    scheme = letter_scheme()
    scheme.edges.stickers.clear()
    with pytest.raises(ScrambleError, match='Add edges letters'):
        build_plan(GOLD_TESTS[1]['scramble'], scheme)
    with pytest.raises(ScrambleError, match='no letter targets'):
        build_plan('R R\'', letter_scheme())


def test_run_shows_each_pair_then_grouped_twists_and_complete_category_reviews():
    run = ProgressiveRun(simple_plan())
    assert run.phase == 'intro' and run.started_at is None
    assert not run.next(5)
    run.finish_intro(10)
    assert run.started_at == 10 and run.prompt.letters == 'AB'
    run.next(11)
    assert run.prompt.letters == 'C'
    run.next(12)
    assert run.prompt.letters == 'DEFG' and run.prompt.kind == 'orientation'
    run.next(13)
    assert run.phase == 'overview' and run.category.ordinary_pairs == ('AB', 'C')
    run.next(14)
    assert run.phase == 'intro' and run.category.category == 'edges'
    assert run.started_at == 10
    run.finish_intro(15)
    run.next(16)
    assert run.phase == 'overview'
    run.next(23)
    assert run.phase == 'recall' and run.prompt.letters == 'HI'
    for entered, now in (('hi', 24), ('AX', 25), ('', 26), ('DEFGX', 29.25)):
        assert run.submit(entered, now)
    assert run.phase == 'result' and run.timings() == (1300, 625)
    assert score_recall(run.recall) == (7, 10)
    assert not run.submit('HI', 30) and len(run.recall) == 4


def test_empty_category_has_review_and_first_actual_letters_start_the_clock():
    plan = simple_plan()
    empty = CategoryMemo('corners', (), ())
    plan = ProgressivePlan(plan.scramble, plan.scheme_name, {}, 'CE', 'EC',
                           (empty, plan.categories[1]), plan.categories[1].prompts)
    run = ProgressiveRun(plan)
    run.finish_intro(1)
    assert run.phase == 'overview' and run.started_at is None
    run.next(10)
    run.finish_intro(11)
    assert run.started_at == 11
    run.next(12)
    run.next(13)
    run.submit('HI', 14)
    assert run.timings() == (200, 100)


@pytest.mark.parametrize('expected, entered, correct, missing, extra', [
    ('AB', 'ab', 2, 0, 0), ('AB', 'AX', 1, 0, 0), ('ABC', 'AC', 2, 1, 0),
    ('AB', 'XAB', 2, 0, 1), ('AB', '', 0, 2, 0), ('ÆØÅ', 'æøa\u030a', 3, 0, 0),
])
def test_feedback_identifies_correct_substituted_missing_and_extra_letters(expected, entered, correct, missing, extra):
    aligned = align_letters(expected, entered)
    assert sum(match for _, _, match in aligned) == correct
    assert sum(not actual for _, actual, _ in aligned) == missing
    assert sum(not target for target, _, _ in aligned) == extra
    assert ''.join(target for target, _, _ in aligned) == normalize_letters(expected)
    assert ''.join(actual for _, actual, _ in aligned) == normalize_letters(entered)


def test_accuracy_counts_both_missing_and_extra_letters_in_a_shifted_answer():
    assert score_recall([ProgressiveRecall('corners', 'orientation', 'ABC', 'BCA')]) == (2, 4)


def open_mode():
    page, repo = mount()
    scheme = letter_scheme()
    repo.data.schemes = {scheme.name: scheme}
    repo.data.active_scheme = scheme.name
    hub = click_nav(page, 'Practice')
    next(c for c in walk(hub) if isinstance(c, ft.TextButton) and c.content == 'Open Progressive Memo').on_click(None)
    return page, repo, hub, hub.progressive


def memo_to_recall(mode, now):
    while mode.phase != 'recall':
        now[0] += 1
        if mode.phase == 'intro':
            mode._finish_intro(mode._generation, mode.run.category_index)
        else:
            mode._key_down(SimpleNamespace(key='Space'))


def test_ui_entry_delays_one_second_ignores_repeats_and_cancels_stale_tasks():
    _, repo, hub, mode = open_mode()
    mode.current_scramble = GOLD_TESTS[1]['scramble']
    mode._start()
    assert hub.mode == 'progressive' and mode.active
    assert mode.phase == 'intro' and mode.run.started_at is None
    with patch('ui.pages.progressive_memo_page.asyncio.sleep', new_callable=AsyncMock) as delay:
        asyncio.run(mode._intro_delay(mode._generation, 0))
        delay.assert_awaited_once_with(1.0)
    assert mode.phase == 'memo'
    index = mode.run.prompt_index
    mode.keyboard_listener.on_key_repeat(SimpleNamespace(key='Space'))
    assert mode.run.prompt_index == index
    old_token = mode._generation
    mode._cancel()
    mode._start()
    mode._finish_intro(old_token, 0)
    assert mode.phase == 'intro'
    hub.set_active(False)
    mode._finish_intro(mode._generation, 0)
    assert mode.phase == 'ready' and not repo.data.progressive_memo_history


def test_space_uses_actual_edit_value_saves_once_and_preserves_timer_data():
    _, repo, _, mode = open_mode()
    timer_snapshot = deepcopy(repo.data.practice_sessions)
    preferences = deepcopy(repo.data.schemes['gold'].to_dict())
    mode.current_scramble = GOLD_TESTS[1]['scramble']
    now = [100.0]
    with patch('ui.pages.progressive_memo_page.time.monotonic', side_effect=lambda: now[0]):
        mode._start()
        memo_to_recall(mode, now)
        prompts = mode.run.plan.recall_prompts
        for index, prompt in enumerate(prompts):
            now[0] += 2
            mode.recall_field.value = prompt.letters[:-1]
            # The incoming edit, rather than a stale field value, owns the answer.
            mode._input_changed(SimpleNamespace(control=SimpleNamespace(value=prompt.letters.lower() + ' ')))
            if index == 0:
                recorded = mode.run.recall_index
                mode._input_changed(SimpleNamespace(control=SimpleNamespace(value=prompt.letters.lower() + '  ')))
                mode._input_changed(SimpleNamespace(control=SimpleNamespace(value=' ')))
                assert mode.run.recall_index == recorded
            if mode.phase == 'recall':
                mode._input_changed(SimpleNamespace(control=SimpleNamespace(value='X')))
        mode._key_down(SimpleNamespace(key='Space'))
        mode._submit_recall('XX')
    assert mode.phase == 'result'
    assert len(repo.data.progressive_memo_history) == 1
    attempt = repo.data.progressive_memo_history[0]
    assert attempt.accuracy == 100 and attempt.recall_centiseconds == len(prompts) * 200
    assert attempt.scramble == GOLD_TESTS[1]['scramble']
    assert attempt.scheme_snapshot == preferences and attempt.created_at
    assert repo.data.practice_sessions == timer_snapshot
    assert repo.data.schemes['gold'].to_dict() == preferences


def test_resize_and_theme_changes_preserve_recall_focus_control_and_draft():
    page, _, hub, mode = open_mode()
    mode.current_scramble = GOLD_TESTS[1]['scramble']
    now = [100.0]
    with patch('ui.pages.progressive_memo_page.time.monotonic', side_effect=lambda: now[0]):
        mode._start()
        memo_to_recall(mode, now)
    listener, field, run = mode.keyboard_listener, mode.recall_field, mode.run
    field.value = 'AB'
    for width, height in ((1400, 808), (920, 700), (366, 570)):
        hub.set_viewport(width, height)
        assert mode.keyboard_listener is listener and mode.recall_field is field
        assert mode.run is run and field.value == 'AB'
        assert mode.header.height + mode.main_region.height + 12 == height
        assert mode.history.height > 0 and mode.stage_scroll.height > 0
        layout = mode.main_region.controls[0]
        hub.set_viewport(width - 10, height)
        assert mode.main_region.controls[0] is layout
    toggle = next(c for c in walk(page.root) if isinstance(c, ft.IconButton) and c.tooltip == 'Switch to dark mode')
    toggle.on_click(None)
    assert mode.phase == 'recall' and field.value == 'AB'
    assert field.color == '#F0F4F3'


def test_history_round_trip_old_backup_migration_and_older_attempts():
    _, repo, _, mode = open_mode()
    original = repo.data.to_dict()
    original.pop('progressive_memo_history')
    original['version'] = 13
    migrated = AppData.from_dict(json.loads(json.dumps(original)))
    assert not migrated.progressive_memo_history
    for key, value in original.items():
        if key != 'version':
            assert migrated.to_dict()[key] == value
    attempt = ProgressiveMemoAttempt('id', '2026-10-04T18:00:00+00:00', 'R U', 'gold',
                                    deepcopy(repo.data.schemes['gold'].to_dict()), 'CE', 'EC',
                                    1234, 456, 1, 2, [ProgressiveRecall('edges', 'pair', 'AB', 'AX')])
    for i in range(75):
        item = ProgressiveMemoAttempt.from_dict(attempt.to_dict())
        item.id = str(i)
        mode.state.add_progressive_memo_attempt(item)
    mode.state.add_progressive_memo_attempt(item)
    loaded = AppData.from_dict(json.loads(json.dumps(repo.data.to_dict())))
    assert len(loaded.progressive_memo_history) == 75
    assert loaded.progressive_memo_history[-1].to_dict() == item.to_dict()
    assert SharedPreferencesAppDataRepository._richness(loaded) > SharedPreferencesAppDataRepository._richness(migrated)
    mode.refresh(update=False)
    assert len(mode.history.controls) == 50 and mode.older_button.visible
    mode._older_attempts()
    assert len(mode.history.controls) == 75 and not mode.older_button.visible
    mode.history.controls[-1].on_click(None)
    assert mode.result.id == '0' and mode.result.accuracy == 50
    assert mode.result.centiseconds == 1690
    for dark in (True, False):
        mode.state.data.dark_mode = dark
        mode.refresh(update=False)
        for match in (True, False):
            tile = mode._result_letter('A', 'A' if match else 'X', match)
            assert contrast(tile.content.controls[0].color, tile.bgcolor) >= 4.5


def test_navigation_away_aborts_without_affecting_blind_timer():
    page, repo, hub, mode = open_mode()
    mode.current_scramble = GOLD_TESTS[1]['scramble']
    mode._start()
    token = mode._generation
    timer = click_nav(page, 'Timer')
    assert timer.active and timer.mode == 'timer'
    assert not hub.active and mode.phase == 'ready'
    mode._finish_intro(token, 0)
    assert not repo.data.progressive_memo_history


def test_start_uses_timer_scramble_generator():
    _, _, _, mode = open_mode()
    assert isinstance(mode.generator, ScrambleGenerator)
    with patch.object(mode.generator, 'generate', return_value=GOLD_TESTS[2]['scramble']) as generate:
        mode._new_scramble()
        mode._start()
        generate.assert_called_once_with()
    assert mode.run.plan.scramble == GOLD_TESTS[2]['scramble']


def test_async_focus_uses_text_field_and_rejects_stale_memo_focus():
    _, _, _, mode = open_mode()
    mode.current_scramble = GOLD_TESTS[1]['scramble']
    now = [100.0]
    with patch('ui.pages.progressive_memo_page.time.monotonic', side_effect=lambda: now[0]):
        mode._start()
        memo_to_recall(mode, now)
    with patch.object(ft.TextField, 'focus', new_callable=AsyncMock) as field_focus, \
            patch.object(ft.KeyboardListener, 'focus', new_callable=AsyncMock) as listener_focus:
        asyncio.run(mode._focus_async(True, mode._generation, mode.run.recall_index))
        field_focus.assert_awaited_once()
        asyncio.run(mode._focus_async(False, mode._generation, mode.run.recall_index))
        listener_focus.assert_not_awaited()
        asyncio.run(mode._focus_async(True, mode._generation - 1, mode.run.recall_index))
        asyncio.run(mode._focus_async(True, mode._generation, mode.run.recall_index + 1))
        assert field_focus.await_count == 1


def test_shared_preferences_save_reload_and_backup_include_progressive_history():
    class Preferences:
        def __init__(self):
            self.values = {}

        async def get(self, key):
            return self.values.get(key)

        async def set(self, key, value):
            self.values[key] = value

    class Host:
        def __init__(self):
            self.tasks = []

        def run_task(self, callback, *args):
            self.tasks.append(asyncio.create_task(callback(*args)))

    async def check():
        prefs, host = Preferences(), Host()
        data = AppData()
        data.schemes = {'gold': letter_scheme()}
        data.active_scheme = 'gold'
        state = AppState(SharedPreferencesAppDataRepository(host, prefs, data, None))
        attempt = ProgressiveMemoAttempt('persisted', '2026-10-04T18:00:00+00:00', 'R U', 'gold',
                                        letter_scheme().to_dict(), 'EC', 'CE', 1000, 300, 2, 2,
                                        [ProgressiveRecall('corners', 'pair', 'AB', 'AB')])
        state.add_progressive_memo_attempt(attempt)
        await asyncio.gather(*host.tasks)
        with patch('data.shared_preferences_repository.ft.SharedPreferences', return_value=prefs):
            restored = (await SharedPreferencesAppDataRepository.create(host)).load()
        assert restored.progressive_memo_history[0].to_dict() == attempt.to_dict()
        assert restored.schemes['gold'].to_dict() == data.schemes['gold'].to_dict()
        assert prefs.values[SharedPreferencesAppDataRepository.STORAGE_KEY] == prefs.values[SharedPreferencesAppDataRepository.SHADOW_KEY]
        backup = AppData.from_dict(json.loads(json.dumps(restored.to_dict())))
        assert backup.progressive_memo_history[0].accuracy == 100
        assert backup.progressive_memo_history[0].scramble == 'R U'

    asyncio.run(check())
