from itertools import product
from statistics import mean
from random import Random

import pytest

from core.ao5_statistics import average_record, five_odds, session_records, timer_insights
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


@pytest.mark.parametrize("times",[[1000,1100,4000,None],[1000,1000,3200,4000],
                                  [0,0,0,None,None],[1000,3000,6000,None,None,None]])
def test_forecast_matches_direct_enumeration_of_valid_five_attempt_sets(times):
    means = []
    for future in product(times,repeat=5):
        finite = sorted(t for t in future if t is not None)
        if len(finite)==4:
            means.append(sum(finite[1:])/3)
        elif len(finite)==5:
            means.append(sum(finite[1:-1])/3)
    result=timer_insights(times)
    assert result.valid_pace == round(mean(means))
    assert result.odds.valid == pytest.approx(len(means)/len(times)**5)
    assert result.valid_pace == timer_insights(list(reversed(times))).valid_pace


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
