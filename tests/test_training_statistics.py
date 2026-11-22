from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import flet as ft
import flet.canvas as cv
import pytest

from core.training_statistics import PLOT_LIMIT, format_time, memo_attempts, summarize, timer_attempts
from data.models import PracticeSolve, ProgressiveMemoAttempt
from ui.navigation_motion import set_reduced_motion
from ui.pages.statistics_page import delta_note
from test_navigation import click_nav, mount, no_client_mount, text_values, walk


def solve(cs, dnf=False, plus2=False):
    return PracticeSolve(cs, "R U R'", dnf, plus2)


def memo(good, scored, cs=3200, recall=800, scheme="A"):
    return ProgressiveMemoAttempt("", "", "", scheme, {}, "CE","EC",cs,recall,good,scored)


def test_timer_excludes_dnf_from_speed_but_not_accuracy_and_applies_penalty():
    history = [solve(1100)]*5 + [solve(100,True)]*2 + [solve(800,plus2=True),solve(1200),solve(1400)]
    s = summarize(timer_attempts(history),5)
    assert (s.overall.correct,s.overall.attempts,s.overall.accuracy,s.best) == (8,10,80,1000)
    assert (s.recent.accuracy,s.recent.median,s.previous.accuracy,s.previous.median) == (60,1200,100,1100)
    assert "40.0 percentage points lower" in delta_note(s,5,True)
    assert "1.00 s slower" in delta_note(s,5,False)
    assert s.points[-3].attempt.time == 1000 and s.points[-3].attempt.plus2
    assert format_time(6023) == "1:00.23"


def test_incomplete_windows_all_dnfs_and_exact_comparison_boundary():
    rows = timer_attempts([solve(500,True)]*5 + [solve(0)]*5)
    for n in (0,1,4):
        s=summarize(rows[:n],5)
        assert s.recent is None and s.previous is None and s.best is None
        assert not any(p.rolling for p in s.points)
    only_fails=summarize(rows[:5],5)
    assert only_fails.recent.accuracy == 0 and only_fails.recent.median is None
    assert summarize(rows[:9],5).previous is None
    complete=summarize(rows,5)
    assert complete.recent.median==0 and complete.previous.median is None
    assert "No comparison" in delta_note(complete,5,False)


def test_memo_accuracy_is_by_scored_letter_and_timings_stay_separate():
    history=[memo(1,1,200,20), memo(0,9,300,80), memo(0,0,400,90),
             memo(1,2,900,100), memo(0,0,100,1), memo(12,12,120,40,scheme="B")]
    rows=memo_attempts(history,"A")
    s=summarize(rows,5)
    assert len(rows)==5 and s.perfect==1 and s.overall.accuracy==pytest.approx(100*2/12)
    assert s.recent.accuracy==s.overall.accuracy and s.overall.median==380
    assert s.memo_median==300 and s.recall_median==80
    for phase,expected in (("memo",300),("recall",80)):
        assert summarize(memo_attempts(history,"A",phase),5).recent.median==expected
    assert summarize(memo_attempts([memo(0,0)]*5),5).recent.accuracy is None


def test_old_solves_keep_attempt_order_and_rolling_prefill_before_display_range():
    rows=timer_attempts([solve(i*10, i%7==0) for i in range(200)])
    s=summarize(rows,12)
    assert len(s.points)==PLOT_LIMIT and [p.number for p in s.points]==list(range(101,201))
    assert s.points[0].rolling==summarize(rows[:101],12).recent
    assert s.overall.attempts==200


def event(value):
    return SimpleNamespace(control=SimpleNamespace(value=value))


@pytest.mark.parametrize("width", [320, 1440])
def test_stats_from_timer_home_and_memo_are_read_only_and_use_saved_histories(width):
    page,repo=mount(width=width)
    repo.data.active_practice_session="Session 2"
    repo.data.practice_sessions["Session 2"]=[solve(5000)]*10+[solve(4000),solve(1,True)]
    repo.data.progressive_memo_history=[memo(2,3,scheme="Speffz"),memo(1,1,scheme="Other")]
    before=deepcopy(repo.data.to_dict())
    timer=click_nav(page,"Timer")
    listener=timer.keyboard_listener
    timer._trends_button.on_click(None)
    hub=page.root.controls[0].content
    stats=hub.statistics
    assert hub.switcher.content is stats and stats.session=="Session 2"
    assert "91.7%" in text_values(stats) and "#12" in text_values(stats)
    assert len([c for c in walk(stats) if isinstance(c,cv.Canvas)])==2
    stats._change_filter(event("Session 3"))
    assert "No saved solves in this session yet." in text_values(stats)
    stats.back_callback()
    assert page.root.controls[0].content is timer and timer.keyboard_listener is listener
    home=click_nav(page,"Home")
    home.launch_buttons["statistics"].on_click(None)
    assert hub.mode=="statistics" and hub.statistics.session=="Session 2"
    stats.back_callback()
    assert hub.mode=="menu"
    hub.open_progressive()
    hub.progressive.stats_button.on_click(None)
    assert hub.mode=="statistics" and stats.source=="memo" and "75.0%" in text_values(stats)
    stats._change_filter(event(":Speffz"))
    stats._change_phase(event("recall"))
    assert "66.7%" in text_values(stats) and "Rolling median recall time" in text_values(stats)
    stats.back_callback()
    assert hub.mode=="progressive" and hub.progressive.active
    assert repo.data.to_dict()==before


def test_route_fades_follow_destinations_and_leave_input_and_refresh_immediate():
    page,_=mount()
    host=page.root.controls[0]
    assert isinstance(host,ft.AnimatedSwitcher) and host.transition==ft.AnimatedSwitcherTransition.FADE
    timer=click_nav(page,"Timer"); listener=timer.keyboard_listener
    assert host.content is timer and timer.active and host.duration==150
    timer.running=True;timer.started_at=14
    timer._trends_button.on_click(None);page.on_resize(None)
    assert host.content is timer and timer.running and timer.started_at==14 and timer.keyboard_listener is listener
    timer.running=False
    set_reduced_motion(host,True)
    assert host.duration==host.reverse_duration==0
    assert click_nav(page,"Home") is host.content and not timer.active


def test_navigation_only_reflows_a_hidden_cube_workspace_if_viewport_changes():
    page,_=mount()
    library=click_nav(page,"Method Library")
    with patch.object(library,"set_viewport",wraps=library.set_viewport) as reflow:
        click_nav(page,"Home");click_nav(page,"Timer")
        reflow.assert_not_called()
        page.width=390;page.on_resize(None)
        assert reflow.call_count==1
