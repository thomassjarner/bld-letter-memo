"""Timer records and estimates for five new attempts. All durations are centiseconds."""
from core.messages import message
from bisect import bisect_left, insort
from functools import cached_property, lru_cache
from itertools import product
from math import fsum, prod
from random import Random
import re
from dataclasses import dataclass


MIN_TIMED_SOLVES = 3
HALF_LIFE = 20  # In attempts, including DNFs; dates are optional in older backups.
GOAL_DRAWS = 4096


@dataclass(frozen=True, slots=True)
class AverageRecord:
    valid: int
    windows: int
    best: int | None


def rolling_averages(times, width):
    """One result for each *completed* window, in order. None means DNF."""
    ordered = []
    total = 0
    for i, t in enumerate(times):
        if i >= width:
            old = times[i-width]
            if old is not None:
                total -= old
                ordered.pop(bisect_left(ordered, old))
        if t is not None:
            total += t
            insort(ordered, t)
        if i+1 < width:
            continue
        if len(ordered) < width-1:
            yield None
            continue
        middle = total - ordered[0] - (ordered[-1] if len(ordered) == width else 0)
        yield round(middle / (width-2))


def average_record(times, width):
    """Visit every overlapping group once; a None is a DNF, not a zero time."""
    valid = 0
    best = None
    for value in rolling_averages(times,width):
        if value is not None:
            best = value if best is None else min(best,value)
            valid += 1
    return AverageRecord(valid,max(0,len(times)-width+1),best)


@dataclass(frozen=True, slots=True)
class Records:
    single: int | None
    ao5: AverageRecord
    ao12: AverageRecord


def session_records(times, *, known_ao5=None):
    return Records(min((t for t in times if t is not None), default=None),
                   known_ao5 if known_ao5 is not None else average_record(times,5),average_record(times,12))


@dataclass(frozen=True, slots=True)
class FiveOdds:
    valid: float       # At least four successes in any order.
    run_of_four: float # At least four consecutive successes within these five.
    clean: float       # Five successes.

    @classmethod
    def from_rate(cls, p):
        return cls(p**4*(5-4*p), p**4*(2-p), p**5)


def five_odds(successes, attempts):
    return FiveOdds.from_rate(successes/attempts) if attempts else None


@dataclass(frozen=True)
class Forecast:
    """Success chance and weighted successful times for one selected range."""
    success_rate: float | None
    timed_count: int
    values: tuple[int, ...]
    mass: tuple[float, ...]  # Conditional on success, in ascending time order.
    cdf: tuple[float, ...]

    @cached_property
    def valid_pace(self):
        if self.timed_count < MIN_TIMED_SOLVES:
            return None
        # Each gap contributes only when the order statistic lies above it.
        mean = fsum(t*w for t,w in zip(self.values,self.mass))
        minimum4 = minimum5 = maximum5 = self.values[0]
        for lo,hi,below in zip(self.values,self.values[1:],self.cdf):
            gap = hi-lo
            minimum4 += gap*(1-below)**4
            minimum5 += gap*(1-below)**5
            maximum5 += gap*(1-below**5)
        four = (4*mean-minimum4)/3     # One DNF: remove it and the fastest time.
        five = (5*mean-minimum5-maximum5)/3
        p = self.success_rate
        w5 = p/(5-4*p)
        return round((1-w5)*four+w5*five)

    @cached_property
    def _goal_samples(self):
        # Built only for a requested Ao5 time goal, never on chart hover or scroll.
        # Each dimension covers the entire weighted CDF. Fixed shuffles keep the
        # estimate repeatable, and drawing conditional on success handles rare Ao5s.
        quantiles = [self.values[bisect_left(self.cdf,(i+.5)/GOAL_DRAWS)] for i in range(GOAL_DRAWS)]
        four, five = [], []
        for ia,ib,ic,id_,ie in _strata():
            a,b,c,d,e = (quantiles[k] for k in (ia,ib,ic,id_,ie))
            total = a+b+c+d
            best = min(a,b,c,d)
            four.append((total-best+1)//3)
            five.append((total+e-min(best,e)-max(a,b,c,d,e)+1)//3)
        return sorted(four),sorted(five)

    def goal_odds(self, goal):
        """P(next single < goal), P(next valid Ao5 < goal) over all attempts."""
        if self.success_rate is None:
            return None,None,False
        p = self.success_rate
        i = bisect_left(self.values,goal)
        single = p*(self.cdf[i-1] if i else 0)
        if self.timed_count < MIN_TIMED_SOLVES:
            return single,None,False
        if i == 0:
            return single,0.0,False
        if i == len(self.values):
            return single,FiveOdds.from_rate(p).valid,False
        if len(self.values) <= 4:
            def below(n):
                probability = []
                for sample in product(range(len(self.values)),repeat=n):
                    times = sorted(self.values[j] for j in sample)
                    kept = times[1:] if n==4 else times[1:-1]
                    if (sum(kept)+1)//3 < goal:
                        probability.append(prod(self.mass[j] for j in sample))
                return fsum(probability)
            q4,q5 = below(4),below(5)
            approximate = False
        else:
            four,five = self._goal_samples
            q4,q5 = bisect_left(four,goal)/GOAL_DRAWS,bisect_left(five,goal)/GOAL_DRAWS
            approximate = True
        return single, min(1.0,5*p**4*(1-p)*q4+p**5*q5), approximate


@lru_cache(maxsize=1)
def _strata():
    rng = Random(560)
    columns = [list(range(GOAL_DRAWS)) for _ in range(5)]
    for col in columns:
        rng.shuffle(col)
    return tuple(zip(*columns))


def recent_forecast(times):
    if not times:
        return Forecast(None,0,(),(),())
    latest_success = next((i for i in range(len(times)-1,-1,-1) if times[i] is not None),None)
    if latest_success is None:
        return Forecast(0.0,0,(),(),())
    # Normalize conditional time weights at the last SUCCESS, separately from
    # the success rate. A long run of DNFs must not erase all historical pace.
    end = len(times)-1
    total = fsum(2.0**(-age/HALF_LIFE) for age in range(len(times)))
    by_time = {}
    n = 0
    for i,t in enumerate(times):
        if t is not None:
            n += 1
            weight = 2.0**((i-latest_success)/HALF_LIFE)
            if weight:
                by_time[t] = by_time.get(t,0.0)+weight
    success_total = fsum(by_time.values())
    p = min(1.0,success_total*2.0**((latest_success-end)/HALF_LIFE)/total)
    values = tuple(sorted(by_time))
    mass = tuple(by_time[t]/success_total for t in values)
    cdf = []
    acc = 0.0
    for w in mass:
        acc = min(1.0,acc+w)
        cdf.append(acc)
    cdf[-1] = 1.0
    return Forecast(1.0 if n==len(times) else p,n,values,mass,tuple(cdf))


def parse_goal(text):
    """Positive centiseconds from seconds or m:ss, with optional decimals."""
    raw = (text or "").strip()
    m = re.fullmatch(r"(?:(\d{1,5}):([0-5]\d)|(\d{1,7}))(?:[.,](\d{1,2}))?",raw,flags=re.ASCII)
    if not m:
        raise ValueError(message('Enter seconds or m:ss, for example 90 or 1:30.00.'))
    seconds = int(m[1])*60+int(m[2]) if m[1] is not None else int(m[3])
    cs = seconds*100+int((m[4] or "").ljust(2,"0"))
    if cs <= 0:
        raise ValueError(message('Enter a time greater than zero.'))
    return cs


@dataclass(frozen=True, slots=True)
class TimerInsights:
    forecast: Forecast
    odds: FiveOdds | None
    current_streak: int
    longest_streak: int
    recorded: AverageRecord

    @property
    def valid_pace(self):
        return self.forecast.valid_pace


def timer_insights(times, *, recorded=None):
    forecast = recent_forecast(times)
    streak = longest = 0
    for t in times:
        streak = 0 if t is None else streak+1
        longest = max(longest,streak)
    odds = FiveOdds.from_rate(forecast.success_rate) if times else None
    return TimerInsights(forecast,odds,streak,longest,
                        recorded if recorded is not None else average_record(times,5))
