"""Non-destructive review, prompt-bound edits and configurable memo constraints."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
import pytest

from core.progressive_memo import CategoryMemo, ProgressivePlan, ProgressiveRun
from data.models import AppData, ProgressiveMemoAttempt
from data.shared_preferences_repository import SharedPreferencesAppDataRepository
from test_navigation import no_client_mount, text_values, walk
from test_progressive_memo import GOLD_TESTS, memo_to_recall, open_mode
from test_progressive_memo_corrections import plan


def review_mode():
    _,repo,_,mode=open_mode()
    edges=CategoryMemo('edges',('AA','FB','LR','EH','AG','TU'),())
    corners=CategoryMemo('corners',('LV','BI','SH'),())
    p=ProgressivePlan('R U','Test',{},'CE','EC',(corners,edges),edges.recall_prompts+corners.recall_prompts)
    mode.run=ProgressiveRun(p);mode.run.phase='recall';mode.run.started_at=1;mode.run.memo_finished_at=2
    mode._load_recall_input(new_control=True);mode._render_stage();mode._update()
    return repo,mode


def edit(mode,value):
    field=mode.recall_field
    field.value=value
    field.on_change(SimpleNamespace(control=field))


def test_reported_pair_four_correction_preserves_pairs_five_six_and_the_remaining_order():
    repo,mode=review_mode()
    for answer in ('AA','FB','LR','EH','AG','TU'):mode._submit_recall(answer)
    for _ in range(3):mode._key_down(SimpleNamespace(key='ArrowLeft'))
    assert mode.run.recall_index==3 and mode.recall_field.value=='EH'
    edit(mode,'L');mode._next()
    assert mode.run.recall_index==4 and mode.recall_field.value=='AG'
    assert mode.recall_forward.content=='Next'
    # Selecting text and pressing Space can produce a whitespace-only edit.
    edit(mode,' ')
    assert mode.run.recall_index==5 and mode.recall_field.value=='TU'
    mode._key_up(SimpleNamespace(key='Space'))
    # An empty edit must not replace the saved answer with a blank.
    edit(mode,'')
    mode._key_down(SimpleNamespace(key='ArrowRight'))
    assert mode.run.recall_index==6
    for answer in ('LV','BI','SH'):mode._submit_recall(answer)
    assert len(repo.data.progressive_memo_history)==1
    assert [r.entered for r in mode.result.recall]==['AA','FB','LR','L','AG','TU','LV','BI','SH']


@pytest.mark.parametrize('forward',['arrow','button','enter','space','confirm'])
def test_reviewing_without_typing_new_letters_never_deletes_saved_answers(forward):
    _,mode=review_mode()
    for value in ('AA','FB','LR'):mode._submit_recall(value)
    for _ in range(3):mode._previous()
    for index,value in enumerate(('AA','FB','LR')):
        assert mode.run.recall_index==index and mode.recall_field.value==value
        edit(mode,'')
        if forward=='arrow':mode._key_down(SimpleNamespace(key='ArrowRight'))
        elif forward=='button':mode.recall_forward.on_click(None)
        elif forward=='enter':mode.recall_field.on_submit(SimpleNamespace(control=mode.recall_field))
        elif forward=='space':
            mode._key_up(SimpleNamespace(key='Space'));edit(mode,' ')
        else:mode._next()
    assert [r.entered for r in mode.run.recall]==['AA','FB','LR']


def test_core_cannot_erase_a_confirmed_answer_or_an_unconfirmed_draft_using_empty_input():
    run=ProgressiveRun(plan());run.phase='recall'
    run.submit('DE',1);run.remember_input('FG');run.previous('')
    assert run.current_input=='DE'
    run.remember_input('');run.submit('',2)
    assert run.recall[0].entered=='DE' and run.current_input=='FG'
    run.submit('',3)
    assert run.recall[1].entered=='FG'
    run.previous();run.remember_input('HI');run.submit('',4)
    assert run.recall[1].entered=='HI' # replacement letters still replace


def test_skip_is_only_blank_for_a_prompt_that_has_never_had_letters():
    _,mode=review_mode()
    assert mode.recall_forward.content=='Skip'
    mode._skip_recall();assert mode.run.recall[0].entered==''
    edit(mode,'FB');assert mode.recall_forward.content=='Next'
    edit(mode,'');mode._skip_recall()
    assert mode.run.recall[1].entered=='FB'
    mode._previous();edit(mode,'XY');mode._skip_recall()
    assert mode.run.recall[1].entered=='XY'


def test_delayed_change_and_submit_events_from_old_prompt_visits_cannot_touch_current_answers():
    _,mode=review_mode();first=mode.recall_field
    mode._submit_recall('AA');second=mode.recall_field
    assert first is not second
    for value in ('','ZZ',' '):
        first.value=value;first.on_change(SimpleNamespace(control=first));first.on_submit(SimpleNamespace(control=first))
    assert mode.run.recall_index==1 and mode.run.recall[0].entered=='AA'
    mode._submit_recall('FB');mode._previous();returned=mode.recall_field
    assert returned is not second and returned.value=='FB'
    second.value='';second.on_change(SimpleNamespace(control=second));second.on_submit(SimpleNamespace(control=second))
    assert mode.run.recall_index==1 and mode.run.current_input=='FB' and mode.recall_field.value=='FB'


@pytest.mark.parametrize('allow',[False,True])
@pytest.mark.parametrize('overview',[False,True])
def test_all_constraint_combinations_keep_the_same_memo_answers_and_timing(allow,overview):
    run=ProgressiveRun(plan(),allow_memo_navigation=allow,show_category_overview=overview)
    seen=[];now=10
    while run.phase!='recall':
        now+=1
        if run.phase=='intro':run.finish_intro(now)
        elif run.phase=='memo':
            seen.append((run.category.category,run.prompt.letters))
            if run.prompt_index==1:
                index=run.prompt_index;started=run.started_at
                assert run.previous_memo()==allow
                if allow:
                    assert run.prompt_index==index-1 and run.started_at==started
                    run.next(now)
            run.next(now)
        else:
            assert overview
            run.next(now)
    assert seen==[('corners','AB'),('corners','C'),('edges','DE'),('edges','FGHI')]
    assert not run.previous_memo()
    for prompt in run.plan.recall_prompts:run.submit(prompt.letters,now+1)
    assert run.timings()[0]>0 and run.timings()[1]==100


def test_memo_previous_crosses_categories_and_stale_intro_tasks_cannot_skip_a_new_title():
    _,_,_,mode=open_mode()
    mode.run=ProgressiveRun(plan(),allow_memo_navigation=True,show_category_overview=False)
    mode._finish_intro(mode._generation,0)
    mode._next();mode._next()
    assert mode.phase=='intro' and mode.run.category_index==1
    old=mode.run.memo_revision
    mode._key_down(SimpleNamespace(key='ArrowLeft'))
    assert mode.phase=='memo' and mode.run.category_index==0 and mode.run.prompt.letters=='C'
    mode._key_down(SimpleNamespace(key='ArrowRight'))
    assert mode.phase=='intro' and mode.run.category_index==1
    mode._finish_intro(mode._generation,1,old)
    assert mode.phase=='intro'
    mode._finish_intro(mode._generation,1,mode.run.memo_revision)
    assert mode.phase=='memo'
    mode._previous_memo();assert mode.run.category_index==0


@pytest.mark.parametrize('empty_first',[False,True])
def test_disabling_overview_skips_empty_categories_without_showing_all_letters(empty_first):
    empty=CategoryMemo('edges',(),());filled=CategoryMemo('corners',('AB',),())
    categories=(empty,filled) if empty_first else (filled,empty)
    p=ProgressivePlan('R','Test',{},'EC' if empty_first else 'CE','CE',categories,filled.recall_prompts)
    run=ProgressiveRun(p,show_category_overview=False)
    while run.phase!='recall':
        if run.phase=='intro':run.finish_intro(10+run.category_index)
        else:run.next(12)
        assert run.phase!='overview'
    assert run.started_at is not None and run.memo_finished_at is not None


def test_constraints_are_saved_in_backups_freeze_for_the_attempt_and_are_recorded_with_history():
    _,repo,_,mode=open_mode();before=deepcopy(repo.data.to_dict())
    assert 'Constraints' in text_values(mode)
    assert not mode.allow_memo_navigation.value and mode.show_category_overview.value
    mode.allow_memo_navigation.on_change(SimpleNamespace(control=SimpleNamespace(value=True)))
    mode.show_category_overview.on_change(SimpleNamespace(control=SimpleNamespace(value=False)))
    decoded,_=SharedPreferencesAppDataRepository._decode(json.dumps(repo.data.to_dict()))
    assert decoded.progressive_memo_allow_navigation and not decoded.progressive_memo_show_overview
    mode.current_scramble=GOLD_TESTS[1]['scramble'];now=[100.0]
    with patch('ui.pages.progressive_memo_page.time.monotonic',side_effect=lambda:now[0]):
        mode._start();run=mode.run
        assert run.allow_memo_navigation and not run.show_category_overview
        mode._constraint_changed('allow_navigation',False)
        assert repo.data.progressive_memo_allow_navigation
        memo_to_recall(mode,now)
        for prompt in run.plan.recall_prompts:mode._submit_recall(prompt.letters)
    saved=repo.data.progressive_memo_history[-1]
    assert saved.allow_memo_navigation and not saved.show_category_overview
    assert saved.accuracy==100
    restored=ProgressiveMemoAttempt.from_dict(saved.to_dict())
    assert restored.to_dict()==saved.to_dict()
    for key,value in before.items():
        if key not in ('progressive_memo_allow_navigation','progressive_memo_show_overview','progressive_memo_history'):
            assert repo.data.to_dict()[key]==value


def test_older_backups_and_attempts_default_to_one_pass_and_a_visible_overview():
    data=AppData().to_dict();data.pop('progressive_memo_allow_navigation');data.pop('progressive_memo_show_overview')
    restored=AppData.from_dict(data)
    assert not restored.progressive_memo_allow_navigation and restored.progressive_memo_show_overview
    old=ProgressiveMemoAttempt.from_dict({'id':'old','memo_centiseconds':123,'recall_centiseconds':234,
                                        'correct_letters':2,'scored_letters':3})
    assert not old.allow_memo_navigation and old.show_category_overview
    assert old.centiseconds==357 and old.correct_letters==2 and old.scored_letters==3


@pytest.mark.parametrize('width,height',[(1400,800),(900,600),(390,570),(280,360)])
def test_constraint_setup_and_memo_controls_fit_scrollable_layouts_without_changing_active_answers(width,height):
    _,repo,_,mode=open_mode();mode.set_viewport(width,height)
    assert mode.stage_scroll.height>0 and mode.stage_scroll.scroll
    mode._constraint_changed('allow_navigation',True);mode._constraint_changed('show_overview',False)
    mode._start();mode._finish_intro(mode._generation,0)
    assert mode.phase=='memo' and 'Previous' in [c.content for c in walk(mode.presentation) if isinstance(c,ft.OutlinedButton)]
    before=deepcopy(mode.run.plan)
    mode._next();mode._previous_memo();mode.set_viewport(width-5,height)
    assert mode.run.plan==before and mode.run.prompt_index==0
