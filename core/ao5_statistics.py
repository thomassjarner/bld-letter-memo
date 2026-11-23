"""Timer records and estimates for five new attempts. All durations are centiseconds."""
from bisect import bisect_left, insort
from dataclasses import dataclass


MIN_TIMED_SOLVES = 3


@dataclass(frozen=True, slots=True)
class AverageRecord:
    valid: int
    windows: int
    best: int | None


def average_record(times, width):
    """Visit every overlapping group once; a None is a DNF, not a zero time."""
    ordered = []
    total = valid = 0
    best = None
    for i, t in enumerate(times):
        if i >= width:
            old = times[i-width]
            if old is not None:
                total -= old
                ordered.pop(bisect_left(ordered, old))
        if t is not None:
            total += t
            insort(ordered, t)
        if i+1 < width or len(ordered) < width-1:
            continue
        middle = total - ordered[0] - (ordered[-1] if len(ordered) == width else 0)
        value = round(middle / (width-2))
        best = value if best is None else min(best, value)
        valid += 1
    return AverageRecord(valid, max(0,len(times)-width+1), best)


@dataclass(frozen=True, slots=True)
class Records:
    single: int | None
    ao5: AverageRecord
    ao12: AverageRecord


def session_records(times):
    return Records(min((t for t in times if t is not None), default=None),
                   average_record(times,5), average_record(times,12))


@dataclass(frozen=True, slots=True)
class FiveOdds:
    valid: float       # At least four successes in any order.
    run_of_four: float # At least four consecutive successes within these five.
    clean: float       # Five successes.


def five_odds(successes, attempts):
    if not attempts:
        return None
    p = successes/attempts
    return FiveOdds(p**4*(5-4*p), p**4*(2-p), p**5)


def _valid_pace(values, p):
    """Expected trimmed Ao5 given a valid set, sampling the empirical times.

    For 4 successes remove the minimum (the DNF is worst); for 5 remove
    both extremes. The probability of five successes conditional on validity
    simplifies to p/(5-4p). The gaps between sorted times give exact expected
    minima/maxima for independent draws, without generating synthetic solves.
    """
    n = len(values)
    if n < MIN_TIMED_SOLVES:
        return None
    mean = sum(values)/n
    minimum4 = minimum5 = maximum5 = previous = values[0]
    for i in range(1,n):
        current = values[i]
        if current != previous:
            gap = current-previous
            below = i/n
            minimum4 += gap*(1-below)**4
            minimum5 += gap*(1-below)**5
            maximum5 += gap*(1-below**5)
            previous = current
    four = (4*mean-minimum4)/3
    five = (5*mean-minimum5-maximum5)/3
    weight5 = p/(5-4*p)
    return round((1-weight5)*four + weight5*five)


@dataclass(frozen=True, slots=True)
class TimerInsights:
    odds: FiveOdds | None
    valid_pace: int | None
    current_streak: int
    longest_streak: int
    recorded: AverageRecord


def timer_insights(times, *, recorded=None):
    good = sorted(t for t in times if t is not None)
    streak = longest = 0
    for t in times:
        streak = 0 if t is None else streak+1
        longest = max(longest,streak)
    odds = five_odds(len(good),len(times))
    return TimerInsights(odds, _valid_pace(good, len(good)/len(times)) if times else None,
                         streak, longest, recorded if recorded is not None else average_record(times,5))
