from random import Random
from types import SimpleNamespace

import pytest

from core.ao5_statistics import average_record
from core.session_overview import Ao5History, MemoSplit, TimeProfile, duration_label, memo_split, timer_elapsed
from core.training_statistics import timer_attempts, trimmed_time
from data.models import PracticeSolve, ProgressiveRecall
from test_navigation import click_nav, mount, no_client_mount


def test_clock_time_does_not_add_penalties_or_drop_dnf_elapsed():
    rows=timer_attempts([PracticeSolve(5900,"R",False,True),PracticeSolve(9000,"R",True),PracticeSolve(100,"R")])
    assert [r.time for r in rows]==[6100,None,100]
    assert timer_elapsed(rows)==15000 and duration_label(timer_elapsed(rows))=="2m 30s"
    assert duration_label(360150)=="1h 00m 01s"


def test_recorded_consistency_and_target_use_successful_adjusted_times_and_strict_goal():
    p=TimeProfile.from_times([None,100,0,130,60])
    assert p.total==5 and p.middle_half==(45,107.5)
    assert p.under(100)==2 and p.under(131)==4
    assert TimeProfile.from_times([None,42]).middle_half is None


@pytest.mark.parametrize("times",[[],[None]*4,[0],[12000]*5,[999,1000],[None,5150,5160,10000],
    [i*4 for i in range(290)], [1]*150+[1000000]])
def test_distribution_accounts_for_each_success_once_and_never_bins_a_dnf(times):
    p=TimeProfile.from_times(times)
    bins=p.bins()
    assert len(bins)<=6 and sum(b.count for b in bins)==len(p.timed)
    assert all(a.high+1==b.low for a,b in zip(bins,bins[1:]))
    for b in bins:
        assert b.count==sum(b.low<=t<=b.high for t in times if t is not None)


def test_ao5_trend_uses_completed_consecutive_windows_and_keeps_all_grouped_outcomes():
    rng=Random(57)
    times=[rng.choice((8500,6952,5800,9000,None,None)) for _ in range(205)]
    ao5=Ao5History.from_times(times)
    expected=[trimmed_time(times[i-4:i+1]) for i in range(4,len(times))]
    assert ao5.values==tuple(None if t=="DNF" else t for t in expected)
    assert ao5.record==average_record(times,5) and ao5.profile.under(7000)==sum(t!="DNF" and t<7000 for t in expected)
    points=ao5.points(23)
    assert len(points)==100 and (points[0].number,points[-1].number)==(28,228)
    assert sum(p.group.timed for p in points)==ao5.record.valid
    assert sum(p.group.attempts for p in points)==len(times)-4
    assert not Ao5History.from_times(times[:4]).points(0)


def test_memo_split_scores_saved_recall_only_and_skips_partial_legacy_details():
    rows=[ProgressiveRecall("edges","pair","AB","ABX"),ProgressiveRecall("corners","orientation","ÅC","Å")]
    complete=SimpleNamespace(recall=rows,correct_letters=3,scored_letters=5)
    legacy=SimpleNamespace(recall=[],correct_letters=10,scored_letters=12)
    partial=SimpleNamespace(recall=rows[:1],correct_letters=3,scored_letters=5)
    no_corners=SimpleNamespace(recall=[ProgressiveRecall("edges","pair","X","")],correct_letters=0,scored_letters=1)
    assert memo_split([complete,legacy,partial,no_corners])==MemoSplit(2,4,1,2,2)


def test_goal_counts_scope_and_sparse_ao5_are_independent_of_chart_view():
    page,repo=mount(width=390)
    repo.data.practice_sessions["Session 1"]=[PracticeSolve(t,"U",d,p) for t,d,p in [
        (8000,False,False),(8500,False,False),(9000,False,False),(8600,False,False),
        (8700,False,False),(8500,True,False),(8900,False,True),(7000,True,False)]]
    repo.data.practice_sessions["Session 2"]=[PracticeSolve(7300,"R")]
    activity=click_nav(page,"Timer");activity._select_activity_tab("stats");s=activity.statistics
    event=lambda value:SimpleNamespace(control=SimpleNamespace(value=value))
    assert s.report.controls.index(s.overview)<s.report.controls.index(s.chart_area)
    assert s.report.controls.index(s.chart_area)<s.report.controls.index(s.recent)
    assert s.metrics[2].value.value=="DNF" and s.metrics[0].value.value=="75.0%"
    s.goal_field.value="1:30";s._apply_goal()
    assert s.goal_recorded.value=="Recorded under 1:30.00: 4/8 attempts (50.0%) · 3/4 Ao5s (75.0%)"
    s._change_scope(event("5"))
    assert s.goal_recorded.value=="Recorded under 1:30.00: 2/5 attempts (40.0%) · 0/1 Ao5s (0.0%)"
    s._change_window(event("ao5"))
    assert s.timing._readout(0)=="Ao5 · DNF\nAttempts #4–8"
    s._change_filter(event("Session 2"))
    assert s.ao5_wait_panel.visible and "1 of 5" in s.ao5_wait.value and not s.timing.view.visible
    assert "No completed Ao5 yet" in s.goal_recorded.value and s.metrics[2].value.value=="—"
