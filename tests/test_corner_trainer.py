"""Exact setups, shuffled coverage, reveal boundaries and read-only recall UI."""
import asyncio
from copy import deepcopy
import random
from types import SimpleNamespace
from unittest.mock import patch

import flet as ft
import flet.canvas as cv
import pytest

from core.algorithms import normalized_state, parse_algorithm
from core.corner_cases import SUBSETS, corner_cases, identify_case_state
from core.cube_definitions import CORNER_PIECES, CORNER_STICKER_ORDER
from core.corner_trainer import CornerRecallSession, TrainerFilters, make_card, matching_cases
from core.corner_walkthrough import apply_moves
from core.tracer import _at, _solved
from data.color_themes import LIGHT_THEMES
from data.models import CaseAlgorithm, CornerCaseRecord
from test_navigation import click_nav, mount, no_client_mount, text_values, walk
from test_progressive_memo import letter_scheme


@pytest.fixture
def portable_setup():
    # Setup fallback coverage is separate from the real bundled-solver tests.
    with patch('core.corner_trainer.solve_facelets', return_value=None):
        yield


def open_trainer(width=1440):
    page, repo = mount(width=width)
    scheme = trainer_scheme()
    repo.data.schemes[scheme.name] = scheme
    repo.data.active_scheme = scheme.name
    view = click_nav(page, 'Method Library')
    view._set_mode('trainer')
    return page, repo, view, view.trainer


def trainer_scheme():
    scheme=letter_scheme()
    scheme.corners.buffer_piece=scheme.corners.buffer_sticker='UFR'
    scheme.corners.stickers={s:chr(65+i) for i,s in enumerate(CORNER_STICKER_ORDER)}
    for s in CORNER_PIECES['UFR']:scheme.corners.stickers[s]='BUFFER'
    return scheme


def test_filters_union_subsets_and_statuses_then_intersect_targets_and_favorites_without_writing():
    catalog = corner_cases()
    records = {'UBL:UBR': CornerCaseRecord(status='learning', favorite=True),
               'UBL:LUF': CornerCaseRecord(status='learned', favorite=True)}
    before = deepcopy(records)
    assert len(matching_cases(TrainerFilters(), records)) == 378
    assert len(matching_cases(TrainerFilters(subsets=frozenset({'U/U'})), records)) == 54
    assert len(matching_cases(TrainerFilters(subsets=frozenset({'U/U','U/D'})), records)) == 162
    filters = TrainerFilters(statuses=frozenset({'learning','learned'}), first='UBL', favorites=True)
    assert [c.id for c in matching_cases(filters, records)] == ['UBL:UBR','UBL:LUF']
    assert [c.id for c in matching_cases(TrainerFilters(first='UBL',second='UBR'),records)] == ['UBL:UBR']
    assert not matching_cases(TrainerFilters(first='UBL',second='LUB'),records) # same physical piece
    assert not matching_cases(TrainerFilters(subsets=frozenset()), records)
    assert not matching_cases(TrainerFilters(statuses=frozenset()), records)
    assert records == before


def test_all_378_portable_setups_match_their_exact_case_and_solution_and_restore_all_edges(portable_setup):
    for i,key in enumerate(corner_cases()):
        card = make_card(key, None, {}, random.Random(i))
        initial = card.initial
        assert identify_case_state(normalized_state(parse_algorithm(' '.join(card.moves)))) == key
        assert apply_moves(initial,card.moves) == _solved()
        assert sum(_at(initial,s) != s for s in ('U','F','R','D','L','B')) == 0
        assert all(_at(initial,s)==s for s in ('UF','FU','UR','RU','UB','BU','UL','LU','DF','FD','DR','RD','DB','BD','DL','LD','FR','RF','FL','LF','BR','RB','BL','LB'))
        assert card.commutator and normalized_state(parse_algorithm(card.commutator)) == normalized_state(parse_algorithm(' '.join(card.moves)))


@pytest.mark.parametrize('key',['UBL:UBR','UBL:FDL','FDL:UBL','FDL:RDB','BUR:BUL','RDB:LUF'])
def test_bundled_solver_setups_solve_the_exact_target_not_just_a_similar_pair(key):
    card = make_card(key, None, {}, random.Random(103))
    assert card.setup and len(card.setup)<=50
    assert apply_moves(card.initial,card.moves)==_solved()


def test_bad_or_unavailable_solver_output_uses_a_verified_portable_setup():
    for value in (None,'Error 21','R U', 'R2 D2'):
        with patch('core.corner_trainer.solve_facelets',return_value=value):
            card=make_card('UBL:UBR',None,{})
        assert apply_moves(card.initial,card.moves)==_solved()
    with patch('core.corner_trainer.solve_facelets',side_effect=RuntimeError('No JS')):
        assert make_card('UBL:UBR',None,{}).setup


def test_preferred_custom_alg_is_used_and_invalid_imports_fall_back_without_overwriting_them(portable_setup):
    case = corner_cases()['BUR:BUL']
    records={case.id:CornerCaseRecord(algorithms=[CaseAlgorithm('mine','My version',case.starter+" R R'")],preferred_algorithm='mine')}
    before=deepcopy(records)
    card=make_card(case.id,None,records)
    assert card.algorithm_id=='mine' and card.name=='My version' and not card.warning
    assert records==before
    records[case.id].algorithms[0].alg='R'
    before=deepcopy(records)
    card=make_card(case.id,None,records)
    assert card.warning and card.algorithm_id!='mine'
    assert apply_moves(card.initial,card.moves)==_solved() and records==before


def test_round_shuffles_once_covers_every_case_and_counts_grades_and_reveals_once(portable_setup):
    scheme=trainer_scheme();records={}
    selected=matching_cases(TrainerFilters(first='UBL'),records)
    round=CornerRecallSession(selected+[selected[0]],scheme,records,random.Random(7))
    assert len(round.deck)==len(selected) and len(set(round.deck))==len(selected)
    assert round.deck != [c.id for c in selected]
    before=deepcopy(scheme.to_dict())
    scheme.corners.stickers.clear()
    for i,key in enumerate(round.deck):
        assert round.position==i and not round.answered
        assert not round.grade(True) and not round.advance() # no prepared card
        card=round.prepare();assert card.case_id==key and '?' not in card.letters
        if i%2: assert round.reveal()
        assert round.grade(i%3!=0)
        assert not round.grade(False) and not round.reveal()
        assert round.results[-1].revealed==bool(i%2)
        if i+1<len(round.deck): assert round.advance()
    assert round.complete and not round.advance()
    assert len(round.results)==len(selected) and {r.card.case_id for r in round.results}==set(round.deck)
    assert round.recall_rate==100*round.remembered/len(selected)
    assert round.scheme.to_dict()==before and records=={}


def test_empty_round_is_rejected_and_no_letters_are_invented(portable_setup):
    with pytest.raises(ValueError,match='No cases'):CornerRecallSession([],None,{})
    assert make_card('UBL:UBR',None,{}).letters=='??'
    # A scheme for another buffer can have unassigned stickers in this fixed
    # UFR library; keep those unknown rather than treating BUFFER as a letter.
    assert '?' in make_card('UBL:UBR',letter_scheme(),{}).letters


@pytest.mark.parametrize('width,height',[(1400,760),(1000,430),(700,500),(390,570),(280,320)])
def test_trainer_reveal_rating_summary_and_retry_are_scrollable_and_do_not_touch_saved_data(width,height,portable_setup):
    page,repo,view,trainer=open_trainer(width)
    view.set_viewport(width,height)
    before=deepcopy(repo.data.to_dict())
    assert 'trainer' in view.section_buttons and trainer in view.body.controls
    assert trainer.listing.height==view.body.height and trainer.listing.scroll
    assert all(' · ' in o.text for o in trainer.first_target.options[1:])
    trainer._start(cases=['UBL:UBR','UBL:LUF'])
    assert view.scheme_picker.disabled and trainer.session.card
    first=trainer.session.card
    assert trainer.viewer.controls==[trainer.viewer.canvas]
    assert not any(isinstance(s,cv.Text) for s in trainer.viewer.canvas.shapes)
    assert 'Commutator' not in text_values(trainer) and first.letters not in text_values(trainer)
    trainer._show()
    assert trainer.session.revealed and first.letters in text_values(trainer)
    assert 'Commutator' in text_values(trainer) and ' '.join(first.moves) in text_values(trainer)
    trainer._grade(False);trainer._grade(True)
    assert len(trainer.session.results)==1 and not trainer.session.results[0].remembered
    # Switches from a revealed case must not leak the next question's targets.
    trainer.viewer.letter_switch.value=trainer.viewer.focus_switch.value=True
    trainer._next()
    assert not trainer.session.revealed and not trainer.session.answered
    assert not trainer.viewer.letter_switch.value and not trainer.viewer.focus_switch.value
    assert trainer.viewer.canvas.width+24<=width and trainer.viewer.canvas.height>=140
    trainer._grade(True)
    assert not trainer.session.results[-1].revealed
    trainer._next()
    assert trainer.view=='summary' and not view.scheme_picker.disabled
    assert trainer.session.recall_rate==50 and trainer.session.remembered==1
    assert 'Missed cases · 1' in text_values(trainer) and 'Remembered cases · 1' in text_values(trainer)
    trainer._retry()
    assert trainer.session.deck==[first.case_id] and trainer.view=='recall'
    assert repo.data.to_dict()==before


def test_overview_route_and_empty_filters_are_clear_and_the_session_survives_navigation_and_editing(portable_setup):
    page,repo=mount()
    view=click_nav(page,'Method Library')
    next(c for c in walk(view) if isinstance(c,ft.TextButton) and c.content=='Open corner trainer').on_click(None)
    trainer=view.trainer
    for box in trainer.subsets.values():box.value=False
    trainer._filter_changed()
    assert trainer.start_button.disabled and trainer.match_text.value.startswith('0 matching')
    for box in trainer.subsets.values():box.value=True
    trainer._filter_changed()
    trainer._start(cases=['UBL:UBR','UBL:LUF']);round=trainer.session
    trainer._show();trainer._grade(True)
    before=deepcopy(repo.data.to_dict())
    trainer._open_case(round.card)
    assert view.mode=='library' and view.selected_case==round.card.case_id
    back=next(c for c in walk(view) if isinstance(c,ft.IconButton) and c.tooltip=='Return to corner trainer')
    back.on_click(None)
    assert view.mode=='trainer' and trainer.session is round and round.answered
    timer=click_nav(page,'Timer');listener=timer.keyboard_listener
    click_nav(page,'Method Library')
    assert trainer.session is round and round.answered
    trainer._summary();assert trainer.view=='summary' and not round.complete
    trainer._resume();assert round.position==1 and trainer.view=='recall'
    assert click_nav(page,'Timer') is timer and timer.keyboard_listener is listener
    assert repo.data.to_dict()==before


@pytest.mark.parametrize('key',LIGHT_THEMES)
def test_filter_and_answer_controls_follow_every_palette_and_dark_mode_without_resetting_round(key,portable_setup):
    page,repo,view,trainer=open_trainer()
    trainer._start(cases=['UBL:UBR']);round=trainer.session
    for dark in (False,True,False):
        repo.data.light_theme=key;repo.data.dark_mode=dark
        view.refresh(update=False);trainer._show();view.before_update()
        expected='#F0F4F3' if dark else LIGHT_THEMES[key].colors['on_surface']
        assert trainer.session is round and round.position==0 and not round.results
        assert any(c.color==expected for c in walk(trainer) if isinstance(c,ft.Text))
        assert trainer.viewer.move_text.color==expected


def test_cancelled_setup_tasks_cannot_publish_or_advance_after_navigation(portable_setup):
    _,_,_,trainer=open_trainer()
    trainer.session=CornerRecallSession(['UBL:UBR'],None,{})
    trainer.view='recall';trainer.active=True;trainer.busy=True
    token=trainer._token
    async def leave(delay):trainer.set_active(False)
    with patch('ui.components.corner_trainer.asyncio.sleep',side_effect=leave):
        asyncio.run(trainer._prepare_async(token))
    assert trainer.session.card is None and not trainer.session.results and not trainer.busy
    trainer.set_active(True)
    assert trainer.session.card and trainer.session.position==0
