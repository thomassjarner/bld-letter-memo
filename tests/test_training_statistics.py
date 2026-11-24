from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import flet as ft
import pytest

from core.training_statistics import PLOT_LIMIT, block, format_time, memo_attempts, select_range, summarize, timer_attempts, trimmed_time
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
    assert summarize([], 50).recent is None and not summarize([], 5).points
    failures = timer_attempts([solve(1,True)]*4)
    assert summarize(failures,5).recent.accuracy == 0 and summarize(failures,5).best is None
    assert summarize(timer_attempts([solve(0)]), 12).recent.median == 0


def test_actual_trimmed_times_keep_penalties_and_dnf_rules():
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


def test_all_history_is_included_in_both_cumulative_and_grouped_charts():
    history = timer_attempts([solve(300+i%311, i%7==0, i%5==0) for i in range(340)])
    # One early outlier and a group with a mixture of successes and DNFs.
    history[:1] = timer_attempts([solve(5)])
    for window in (None,12):
        s = summarize(history,window)
        assert len(s.points)==PLOT_LIMIT and (s.points[0].number,s.points[-1].number)==(1,340)
        assert [p.number for p in s.latest] == list(range(329,341))
        start = 0
        for p in s.points:
            end = p.number
            assert p.group == block(history[start:end])
            assert p.rolling == block(history[max(0,end-window) if window is not None else 0:end])
            start = end
        assert s.overall == block(history) and s.best == 5
        assert sum(p.group.scored for p in s.points) == 340
    rows,offset = select_range(history,12)
    s=summarize(rows,offset=offset)
    assert [p.number for p in s.points] == list(range(329,341))
    assert s.overall == block(history[-12:]) and s.recent == s.overall


def test_large_memo_groups_weight_letters_and_include_unscored_rounds():
    rows = memo_attempts([memo(1,1),memo(0,9),memo(0,0)]*91)
    s=summarize(rows)
    assert s.overall.accuracy==10
    assert sum(p.group.scored for p in s.points)==910
    assert sum(p.group.correct for p in s.points)==91
    assert s.points[-1].rolling==s.overall


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
    assert stats.scope is None and stats.window is None and stats.scope_picker.value == "all"
    assert stats.metrics[0].value.value == "91.7%"
    assert len(stats.metrics) == 3 and not any("PB" in m.title.value or "single" in m.title.value.lower() for m in stats.metrics)
    records = [p.value for p in stats.pb_values]
    stats._change_scope(event("5"))
    assert stats.metrics[0].value.value == "80.0%" and stats.timing.start.value == "#8"
    assert [p.value for p in stats.pb_values] == records
    stats._change_scope(event("all"))
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
    ms._change_filter(event(":Speffz"))
    ms._change_metric(SimpleNamespace(control=SimpleNamespace(selected=["time"])))
    ms._change_phase(event("recall"))
    assert ms.metrics[0].value.value == "66.7%" and ms.timing.title.value == "Median recall time over time"
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
