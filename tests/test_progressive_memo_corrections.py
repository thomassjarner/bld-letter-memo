"""Editable recall positions, arrow shortcuts, parity and one-letter feedback."""
import asyncio
from copy import deepcopy
import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import flet as ft
import pytest

from core.cube_definitions import EDGE_STICKER_ORDER
from core.progressive_memo import CategoryMemo, ProgressivePlan, ProgressiveRun, build_plan, score_recall
from core.scramble_generator import ScrambleGenerator
from core.tracer import ScrambleError, ScrambleTracer
from data.models import ProgressiveMemoAttempt, ProgressiveRecall
from test_gold_scrambles import GOLD_TESTS
from test_navigation import no_client_mount, text_values, walk
from test_progressive_memo import letter_scheme, open_mode


def plan():
    corners=CategoryMemo('corners',('AB','C'),())
    edges=CategoryMemo('edges',('DE',),('FG','HI'))
    return ProgressivePlan('R U','Test',{},'CE','EC',(corners,edges),edges.recall_prompts+corners.recall_prompts)


def recall_mode():
    page,repo,hub,mode=open_mode()
    mode.run=ProgressiveRun(plan())
    mode.run.phase='recall';mode.run.started_at=10;mode.run.memo_finished_at=20
    mode._render_stage();mode._update()
    return page,repo,hub,mode


def test_previous_replaces_the_answer_in_place_preserves_later_answers_and_unconfirmed_drafts():
    run=ProgressiveRun(plan());run.phase='recall';run.started_at=10;run.memo_finished_at=20
    assert not run.previous('DRAFT')
    run.submit('XX',21);run.submit('FG',22)
    assert run.previous('HI') and run.current_input=='FG'
    assert run.previous() and run.current_input=='XX'
    run.submit('DE',23)
    assert run.current_input=='FG' and len(run.recall)==2
    run.submit(run.current_input,24)
    assert run.current_input=='HI' # retained without having been confirmed
    for value in ('HI','AB','C'):run.submit(value,30)
    assert run.phase=='result' and len(run.recall)==5
    assert [r.entered for r in run.recall]==['DE','FG','HI','AB','C']
    assert score_recall(run.recall)==(9,9) and run.timings()==(1000,1000)
    assert not run.previous() and not run.submit('C',31)


def test_previous_skip_and_confirm_buttons_are_ordered_and_arrow_keys_do_not_repeat_or_shift_answers():
    _,repo,_,mode=recall_mode();before=deepcopy(repo.data.to_dict())
    buttons=[c for c in walk(mode.presentation) if isinstance(c,(ft.OutlinedButton,ft.FilledButton,ft.TextButton))]
    assert [b.content for b in buttons]==['Previous','Confirm','Skip']
    assert buttons[0].disabled
    mode.recall_field.value='D'
    mode._key_down(SimpleNamespace(key='Arrow Left'))
    assert mode.run.recall_index==0 and mode.recall_field.value=='D'
    mode._key_down(SimpleNamespace(key='ArrowRight'))
    assert mode.run.recall_index==1 and mode.run.recall[0].entered=='D'
    for _ in range(3):mode.keyboard_listener.on_key_repeat(SimpleNamespace(key='ArrowRight'))
    assert mode.run.recall_index==1
    mode._submit_recall('FG')
    mode.recall_field.value='HI'
    mode._key_down(SimpleNamespace(key='ArrowLeft'))
    assert mode.run.recall_index==1 and mode.recall_field.value=='FG'
    mode._key_down(SimpleNamespace(key='Right'))
    assert mode.run.recall[1].entered=='FG' and mode.recall_field.value=='HI'
    assert mode.run.recall_index==2 and len(mode.run.recall)==2 and repo.data.to_dict()==before


def test_restored_answers_are_selected_after_focus_and_typing_replaces_them_without_backspace():
    _,_,_,mode=recall_mode()
    mode._submit_recall('DE');mode._submit_recall('ZZ')
    mode._previous()
    assert mode.recall_field.value=='ZZ'
    with patch.object(ft.TextField,'focus',new_callable=AsyncMock) as focus:
        asyncio.run(mode._focus_async(True,mode._generation,1,mode._focus_revision,'ZZ'))
        focus.assert_awaited_once()
    assert mode.recall_field.selection.start==0 and mode.recall_field.selection.end==2
    mode._input_changed(SimpleNamespace(control=SimpleNamespace(value='fg')))
    assert mode.recall_field.selection is None
    mode._next()
    assert mode.run.recall[1].entered=='FG' and len(mode.run.recall)==2


def test_stale_selection_tasks_cannot_select_a_new_draft_even_after_returning_to_the_same_index():
    _,_,_,mode=recall_mode()
    mode._submit_recall('DE');mode._previous()
    old_revision=mode._focus_revision
    mode._submit_recall('DE');mode._previous()
    with patch.object(ft.TextField,'focus',new_callable=AsyncMock) as focus:
        asyncio.run(mode._focus_async(True,mode._generation,0,old_revision,'DE'))
        focus.assert_not_awaited()
    async def type_while_focusing():mode.recall_field.value='X'
    with patch.object(ft.TextField,'focus',side_effect=type_while_focusing):
        asyncio.run(mode._focus_async(True,mode._generation,0,mode._focus_revision,'DE'))
    assert mode.recall_field.value=='X' and mode.recall_field.selection is None
    mode._load_recall_input()
    old_revision=mode._focus_revision
    mode._input_changed(SimpleNamespace(control=SimpleNamespace(value='DE')))
    with patch.object(ft.TextField,'focus',new_callable=AsyncMock) as focus:
        asyncio.run(mode._focus_async(True,mode._generation,0,old_revision,'DE'))
        focus.assert_not_awaited()


def test_selection_uses_utf16_offsets_and_does_not_change_the_danish_letter():
    _,_,_,mode=recall_mode()
    for selected,end in (('ÆØ',2),('Å',1),('𝔄',2)):
        mode.recall_field.value=selected
        with patch.object(ft.TextField,'focus',new_callable=AsyncMock):
            asyncio.run(mode._focus_async(True,mode._generation,0,mode._focus_revision,selected))
        assert mode.recall_field.selection.start==0 and mode.recall_field.selection.end==end
        assert mode.recall_field.value==selected


def test_space_release_allows_identical_prefilled_answers_but_late_held_space_does_not_advance():
    _,_,_,mode=recall_mode()
    category=CategoryMemo('edges',('AA','AA','Z'),())
    mode.run=ProgressiveRun(ProgressivePlan('R','Test',{},'EC','EC',(category,),category.recall_prompts))
    mode.run.phase='recall';mode.run.started_at=1;mode.run.memo_finished_at=2
    mode._submit_recall('AA');mode._submit_recall('AA');mode._previous();mode._previous()
    def edit(value):mode._input_changed(SimpleNamespace(control=SimpleNamespace(value=value)))
    edit('AA ')
    assert mode.run.recall_index==1 and mode.recall_field.value=='AA'
    edit('AA  ')
    assert mode.run.recall_index==1 and mode.recall_field.value=='AA'
    mode.keyboard_listener.on_key_up(SimpleNamespace(key='Space'))
    edit('AA ')
    assert mode.run.recall_index==2 and len(mode.run.recall)==2


def test_correction_then_finish_saves_only_final_answers_once_and_keeps_timer_and_scheme_data():
    _,repo,_,mode=recall_mode()
    before=deepcopy(repo.data.to_dict())
    mode._submit_recall('XX');mode._submit_recall('FG')
    mode._previous();mode._previous();mode._submit_recall('DE');mode._submit_recall('FG')
    for value in ('HI','AB','C'):mode._submit_recall(value)
    assert mode.phase=='result' and len(repo.data.progressive_memo_history)==1
    saved=repo.data.progressive_memo_history[0]
    assert saved.accuracy==100 and [r.entered for r in saved.recall]==['DE','FG','HI','AB','C']
    mode._previous();mode._skip_recall();mode._input_submitted(SimpleNamespace(control=SimpleNamespace(value='WRONG')))
    assert len(repo.data.progressive_memo_history)==1
    for key,value in before.items():
        if key!='progressive_memo_history':assert repo.data.to_dict()[key]==value


def test_field_length_matches_each_prompt_and_a_final_single_never_records_an_extra_slot():
    _,repo,_,mode=recall_mode()
    mode._input_changed(SimpleNamespace(control=SimpleNamespace(value='DEZZ')))
    assert mode.recall_field.value=='DE'
    for _ in range(4):mode._skip_recall()
    assert mode.run.prompt.letters=='C' and 'single final letter' in ' '.join(text_values(mode))
    mode._input_changed(SimpleNamespace(control=SimpleNamespace(value='XYZ')))
    assert mode.recall_field.value=='X'
    mode._input_changed(SimpleNamespace(control=SimpleNamespace(value='XYZ ')))
    saved=repo.data.progressive_memo_history[0]
    assert saved.recall[-1].entered=='X' and saved.scored_letters==9
    assert not any(t.lower()=='extra' for t in text_values(mode.stage_scroll))


def test_decomposed_danish_input_is_normalized_before_the_single_letter_limit():
    _,_,_,mode=recall_mode()
    category=CategoryMemo('corners',('Å',),())
    mode.run=ProgressiveRun(ProgressivePlan('R','Test',{},'CE','CE',(category,),category.recall_prompts))
    mode.run.phase='recall'
    mode._input_changed(SimpleNamespace(control=SimpleNamespace(value='a\u030a')))
    assert mode.recall_field.value=='Å'


@pytest.mark.parametrize('entered',['H','','RC'])
def test_saved_single_letter_result_has_one_expected_tile_and_no_extra_box(entered):
    _,repo,_,mode=recall_mode();before=deepcopy(repo.data.to_dict())
    recall=[ProgressiveRecall('corners','pair','H',entered)]
    correct,scored=score_recall(recall)
    mode.result=ProgressiveMemoAttempt('legacy','2026-01-01','R U','Test',{},'CE','CE',100,100,correct,scored,recall)
    mode._render_result()
    tiles=[c for c in walk(mode.stage_scroll) if isinstance(c,ft.Container) and c.width==40]
    assert len(tiles)==1 and tiles[0].content.controls[1].value=='H'
    assert 'extra' not in [value.lower() for value in text_values(mode.stage_scroll)]
    if entered=='RC':assert any('Additional input:' in t for t in text_values(mode.stage_scroll))
    assert repo.data.to_dict()==before


@pytest.mark.parametrize('three_style',[False,True])
@pytest.mark.parametrize('orientation',['visual','trace'])
def test_real_scramble_edge_pairs_are_even_only_when_three_style_is_on(three_style,orientation):
    scheme=letter_scheme();scheme.three_style_enabled=three_style
    scheme.corners.orientation_memo=scheme.edges.orientation_memo=orientation
    before=deepcopy(scheme.to_dict());generator=ScrambleGenerator(random.Random(412))
    odd_edges=odd_corners=0
    for scramble in [g['scramble'] for g in GOLD_TESTS]+[generator.generate() for _ in range(40)]:
        result=ScrambleTracer().trace(scramble,scheme)
        p=build_plan(scramble,scheme)
        edges=next(c for c in p.categories if c.category=='edges')
        corners=next(c for c in p.categories if c.category=='corners')
        assert ''.join(edges.ordinary_pairs)==''.join(l for l,f in zip(result.edge_letters,result.edge_orientation_target_flags) if not f)
        odd_edges+=len(''.join(edges.ordinary_pairs))%2
        odd_corners+=len(''.join(corners.ordinary_pairs))%2
        if three_style:assert all(len(pair)==2 for pair in edges.ordinary_pairs)
    assert odd_corners>0 and (odd_edges==0 if three_style else odd_edges>0)
    assert scheme.to_dict()==before


@pytest.mark.parametrize('buffer,helper',[('DF','UR'),('UF','UB'),('FR','UL')])
def test_parity_uses_the_selected_buffer_helper_and_orientation_without_changing_preferences(buffer,helper):
    scheme=letter_scheme();scheme.three_style_enabled=True
    scheme.edges.buffer_piece=scheme.edges.buffer_sticker=buffer;scheme.edge_parity_partner=helper
    scheme.edges.stickers={s:chr(65+i) for i,s in enumerate(EDGE_STICKER_ORDER)}
    scheme.memo_up,scheme.memo_front='Y','B';scheme.scramble_from_own_orientation=True
    scheme.edges.cycle_break_priority=list(reversed(scheme.edges.cycle_break_priority))
    before=deepcopy(scheme.to_dict())
    for case in GOLD_TESTS:
        p=build_plan(case['scramble'],scheme)
        assert all(len(pair)==2 for c in p.categories if c.category=='edges' for pair in c.ordinary_pairs)
    assert scheme.to_dict()==before


def test_invalid_odd_three_style_plan_is_rejected_instead_of_padding_or_removing_letters():
    scheme=letter_scheme();scheme.three_style_enabled=True
    result=SimpleNamespace(corner_letters=['A','B'],corner_targets=['UFL','UFR'],corner_orientation_target_flags=[False,False],
        edge_letters=['C'],edge_targets=['UR'],edge_orientation_target_flags=[False])
    with patch.object(ScrambleTracer,'trace',return_value=result),pytest.raises(ScrambleError,match='complete pairs'):
        build_plan('R',scheme)
