from itertools import product
from math import prod
from random import Random

import pytest

from core.ao5_statistics import average_record, five_odds, parse_goal, recent_forecast, session_records, timer_insights
from core.training_statistics import trimmed_time


@pytest.mark.parametrize("wins,n", [(1,5),(1,2),(4,5),(0,6),(7,7)])
def test_valid_average_and_streak_odds_match_all_32_possible_outcomes(wins,n):
    p = wins/n
    valid = run = clean = 0
    for seq in product((True,False),repeat=5):
        weight = p**sum(seq)*(1-p)**(5-sum(seq))
        if sum(seq) >= 4: valid += weight
        if all(seq[:4]) or all(seq[1:]): run += weight
        if all(seq): clean += weight
    odds = five_odds(wins,n)
    assert (odds.valid,odds.run_of_four,odds.clean) == pytest.approx((valid,run,clean))
    if 0<wins<n:
        assert odds.clean < odds.run_of_four < odds.valid
    assert five_odds(0,0) is None


def enumerate_forecast(times,goal):
    # Independent small oracle: draw five actual attempts (including DNFs),
    # not the separate timing / success distributions used by the estimator.
    weights = [2**((i-len(times)+1)/20) for i in range(len(times))]
    draws = list(zip(times,[w/sum(weights) for w in weights]))
    single = sum(p for t,p in draws if t is not None and t<goal)
    valid = pace_total = below = 0
    for future in product(draws,repeat=5):
        finite = sorted(t for t,_ in future if t is not None)
        if len(finite)<4:
            continue
        weight = prod(p for _,p in future)
        avg = sum(finite[1:4])/3
        valid += weight
        pace_total += avg*weight
        if round(avg)<goal:
            below += weight
    return valid,pace_total/valid,single,below


@pytest.mark.parametrize("times",[[1000,1100,4000,None],[1000,1000,3200,4000],
                                  [0,0,0,None,None],[1000,3000,6000,None,None,None]])
def test_forecast_matches_weighted_enumeration_including_dnf_and_equal_times(times):
    valid,pace,single,below = enumerate_forecast(times,3000)
    result=timer_insights(times)
    assert result.valid_pace == round(pace)
    assert result.odds.valid == pytest.approx(valid)
    pred_single,pred_ao5,sampled = result.forecast.goal_odds(3000)
    assert not sampled and (pred_single,pred_ao5)==pytest.approx((single,below))


def test_recent_successes_and_recent_fast_solves_matter_but_records_remain_exact():
    history = ([None,12000,None,None]*10) + [6000,6500,7000,7500]*10
    improving, fading = (timer_insights(h) for h in (history,history[::-1]))
    assert improving.odds.valid > fading.odds.valid
    assert improving.valid_pace < fading.valid_pace
    assert all(x>y for x,y in zip(improving.forecast.goal_odds(7200)[:2],fading.forecast.goal_odds(7200)[:2]))
    assert session_records(history) == session_records(history[::-1])
    two = recent_forecast([4000]+[None]*19+[8000])
    # The latest outcome carries twice the weight of the one 20 attempts ago.
    assert two.mass == pytest.approx((1/3,2/3))
    assert two.goal_odds(8000)[0] == pytest.approx(two.success_rate/3)


def test_timing_survives_a_long_dnf_streak_and_missing_data_is_not_a_time():
    late = recent_forecast([6000,7000,8000]+[None]*22000)
    assert 6000 < late.valid_pace < 8000
    assert late.goal_odds(9000) == (0,0,False)
    assert recent_forecast([]).goal_odds(8000)==(None,None,False)
    assert recent_forecast([None]*10).goal_odds(8000)==(0,None,False)
    assert recent_forecast([6000]*4).goal_odds(6000)==(0,0,False)
    assert recent_forecast([6000]*4).goal_odds(6001)==(1,1,False)


def test_mixed_goal_samples_are_repeatable_and_agree_with_exact_reference():
    times = [5000,6000,None,9300,6400,8300,7100]
    f = recent_forecast(times)
    valid,_,single,expected = enumerate_forecast(times,7000)
    assert "_goal_samples" not in f.__dict__
    assert f.goal_odds(5000)==(0,0,False)
    assert f.goal_odds(9400)[1]==pytest.approx(valid)
    assert "_goal_samples" not in f.__dict__
    s,a,approximate = f.goal_odds(7000)
    assert approximate and s==pytest.approx(single) and a==pytest.approx(expected,abs=.015)
    assert f.goal_odds(7000)==recent_forecast(times).goal_odds(7000)
    assert f.goal_odds(7001)[1]>=a


@pytest.mark.parametrize("value,cs",[("90",9000),("1:30.00",9000),("1:30,25",9025),
                                      (" 0.1 ",10),("0:00.01",1),("1:02",6200)])
def test_goal_accepts_seconds_or_stopwatch_notation(value,cs):
    assert parse_goal(value)==cs


@pytest.mark.parametrize("bad",["","abc","0","0.00","-9","1:60","1:2","1.234","1:03:04","nan"])
def test_goal_rejects_invalid_or_ambiguous_times(bad):
    with pytest.raises(ValueError):
        parse_goal(bad)


def test_last_four_dnfs_cannot_force_a_forecast_to_dnf():
    history = [1000,1150,2900,1800,None,None,None,None]
    result = timer_insights(history)
    assert result.current_streak==0 and result.longest_streak==4 and result.valid_pace > 0
    assert trimmed_time(history[-5:]) == "DNF"
    assert timer_insights([None]*20).valid_pace is None and timer_insights([None]*20).odds.valid == 0
    assert timer_insights([0]).valid_pace is None and timer_insights([0,0,0]).valid_pace == 0
    assert timer_insights([]).odds is None


def test_record_counts_and_bests_match_timer_rules_for_every_window():
    rng = Random(43)
    for times in ([None]*20, [0]*15, [None,100], [rng.choice([100,100,6000,77,None,None,0]) for _ in range(314)]):
        rec = session_records(times)
        for k,r in ((5,rec.ao5),(12,rec.ao12)):
            values = [trimmed_time(times[i-k:i]) for i in range(k,len(times)+1)]
            finite = [t for t in values if t!="DNF"]
            assert (r.best,r.windows,r.valid) == (min(finite,default=None),len(values),len(finite))
            assert average_record(times,k)==r
