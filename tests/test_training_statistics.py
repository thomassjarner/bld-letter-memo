from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import flet as ft
import pytest

from core.training_statistics import PLOT_LIMIT, format_time, memo_attempts, projected_ao5, summarize, timer_attempts, trimmed_time
from data.models import PracticeSolve, ProgressiveMemoAttempt
from ui.navigation_motion import set_reduced_motion
from test_navigation import click_nav, mount, no_client_mount, text_values


def solve(cs, dnf=False, plus2=False):
    return PracticeSolve(cs, "R U R'", dnf, plus2)


def memo(good, scored, cs=3200, recall=800, scheme="A"):
    return ProgressiveMemoAttempt("", "", "", scheme, {}, "CE","EC",cs,recall,good,scored)


def test_timer_excludes_dnf_from_speed_but_not_accuracy_and_applies_penalty():
    history = [solve(1100)]*5 + [solve(100,True)]*2 + [solve(800,plus2=True),solve(1200),solve(1400)]
    s = summarize(timer_attempts(history),5)
    assert (s.overall.correct,s.overall.attempts,s.overall.accuracy,s.best) == (8,10,80,1000)
    assert (s.recent.accuracy,s.recent.median) == (60,1200)
    assert s.points[-3].attempt.time == 1000 and s.points[-3].attempt.plus2
    assert format_time(6023) == "1:00.23"


def test_five_solve_session_with_window_of_fifty_uses_every_available_result():
    rows = timer_attempts([solve(31342, dnf=i!=3) for i in range(5)])
    s = summarize(rows, 50)
    assert [p.rolling.attempts for p in s.points] == [1,2,3,4,5]
    assert [p.rolling.accuracy for p in s.points] == [0,0,0,25,20]
    assert [p.rolling.median for p in s.points] == [None,None,None,31342,31342]
    assert projected_ao5(rows, s.recent.median) == "DNF"
    assert summarize([], 50).recent is None and not summarize([], 5).points
    failures = timer_attempts([solve(1,True)]*4)
    assert summarize(failures,5).recent.accuracy == 0 and summarize(failures,5).best is None
    assert projected_ao5(failures, None) == "DNF"
    assert summarize(timer_attempts([solve(0)]), 12).recent.median == 0


def test_next_ao5_uses_last_four_actual_results_and_one_estimated_success():
    rows = timer_attempts([solve(1,True), solve(1000,plus2=True), solve(1300), solve(1500), solve(10000)])
    # Previous DNF has rolled off; drop the 12.00 and 100.00 from the next five.
    assert projected_ao5(rows, 2000) == 1600
    assert projected_ao5(rows[:4], 1800) == round((1300+1500+1800)/3)
    assert projected_ao5(rows[:3], 1800) is None
    assert projected_ao5(rows, None) is None
    assert trimmed_time([1200,1200,1200,1200,1200]) == 1200
    assert trimmed_time([900,700,None,None,1000]) == "DNF"


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


def tab(activity, value):
    activity.activity_header.picker.selected = [value]
    activity.activity_header.picker.on_change(SimpleNamespace(control=activity.activity_header.picker))


@pytest.mark.parametrize("width", [280, 390, 1440])
def test_activity_filters_stay_local_and_do_not_change_training_setup(width):
    page,repo = mount(width=width)
    repo.data.active_practice_session = "Session 2"
    repo.data.practice_sessions["Session 2"] = [solve(5000)]*10+[solve(4000),solve(1,True)]
    repo.data.progressive_memo_history = [memo(2,3,scheme="Speffz"),memo(1,1,scheme="Other")]
    before = deepcopy(repo.data.to_dict())
    home = click_nav(page, "Home")
    assert "statistics" not in home.launch_buttons
    hub = click_nav(page, "Practice")
    assert "Training statistics" not in text_values(hub) and not hasattr(hub,"open_statistics")
    timer = click_nav(page,"Timer")
    listener, scramble = timer.keyboard_listener, timer.current_scramble
    tab(timer, "stats")
    stats = timer.statistics
    assert page.root.controls[0].content is timer and timer.body_host.content is stats
    assert stats.session == "Session 2" and stats.recent_rows[0].controls[0].value == "#12"
    assert stats.metrics[0].value.value == "91.7%"
    for window in (5,50,12):
        stats._change_window(event(str(window)))
        assert stats.window == window and timer.body_host.content is stats and stats.report.visible
    stats._change_filter(event("Session 3"))
    assert stats.empty.visible and not stats.report.visible and timer.body_host.content is stats
    # Even delayed keyboard events from the training tab must not arm the timer.
    timer._on_key_down(SimpleNamespace(key="Space")); timer._on_key_up(SimpleNamespace(key="Space"))
    assert not timer.holding_space and not timer.running and timer.current_scramble == scramble
    timer.activity_header.back.on_click(None)
    assert timer.body_host.content is listener and timer.activity_tab=="train"
    tab(timer,"stats")
    assert stats.session == "Session 3"
    hub = click_nav(page,"Practice")
    hub.open_progressive()
    activity = hub.progressive
    memo_listener, memo_scramble = activity.keyboard_listener, activity.current_scramble
    tab(activity, "stats")
    ms = activity.statistics
    assert hub.mode == "progressive" and ms is not stats and ms.source == "memo"
    ms._change_filter(event("*"))
    assert ms.metrics[0].value.value == "75.0%"
    ms._change_filter(event(":Speffz")); ms._change_phase(event("recall"))
    assert ms.metrics[0].value.value == "66.7%" and ms.timing.title.value == "Rolling median recall time"
    activity._start(); activity._key_down(SimpleNamespace(key="Space"))
    assert activity.run is None
    activity.activity_header.back.on_click(None)
    assert activity.body_host.content is memo_listener and activity.active and activity.current_scramble == memo_scramble
    assert repo.data.to_dict() == before


def test_route_fades_and_live_activity_guards():
    from core.progressive_memo import ProgressiveRun
    from test_progressive_memo import simple_plan
    page,_ = mount()
    host = page.root.controls[0]
    assert isinstance(host,ft.AnimatedSwitcher) and host.transition == ft.AnimatedSwitcherTransition.FADE
    timer = click_nav(page,"Timer"); listener = timer.keyboard_listener
    timer.running = True; timer.started_at = 14
    tab(timer, "stats"); page.on_resize(None)
    assert timer.running and timer.started_at == 14 and timer.body_host.content is listener
    assert timer.activity_header.picker.selected == ["train"]
    timer.running = False; timer.holding_space = True
    tab(timer,"stats")
    assert timer.holding_space and timer.body_host.content is listener
    timer.holding_space = False
    set_reduced_motion(host,True)
    assert host.duration == host.reverse_duration == 0
    hub = click_nav(page,"Practice"); hub.open_progressive()
    memo = hub.progressive
    run = memo.run = ProgressiveRun(simple_plan())
    tab(memo, "stats")
    assert memo.run is run and memo.body_host.content is memo.keyboard_listener and memo.activity_tab == "train"


def test_navigation_only_reflows_a_hidden_cube_workspace_if_viewport_changes():
    page,_=mount()
    library=click_nav(page,"Method Library")
    with patch.object(library,"set_viewport",wraps=library.set_viewport) as reflow:
        click_nav(page,"Home");click_nav(page,"Timer")
        reflow.assert_not_called()
        page.width=390;page.on_resize(None)
        assert reflow.call_count==1
