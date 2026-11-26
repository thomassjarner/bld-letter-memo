"""Read-only training statistics. Attempt order works even for undated backups."""
from core.messages import message
from dataclasses import dataclass
from heapq import heappop, heappush
from statistics import median


WINDOWS = (5, 12, 50)
PLOT_LIMIT = 100


def format_time(cs):
    cs = max(0, int(round(cs)))
    minutes, rem = divmod(cs, 6000)
    return f"{minutes}:{rem // 100:02}.{rem % 100:02}" if minutes else f"{rem // 100}.{rem % 100:02}"


def effective_time(solve):
    return solve.centiseconds + (200 if getattr(solve, "plus2", False) else 0)


@dataclass(frozen=True, slots=True)
class Attempt:
    correct: int
    scored: int
    time: int | None
    plus2: bool = False
    memo: int | None = None
    recall: int | None = None
    dnf_elapsed: int | None = None  # For inspecting one attempt, never used in time statistics.


def timer_attempts(solves):
    return [Attempt(int(not s.dnf), 1, None if s.dnf else effective_time(s), s.plus2 and not s.dnf,
                    dnf_elapsed=s.centiseconds if s.dnf else None)
            for s in solves]


def memo_attempts(rounds, scheme=None, phase=message('total')):
    if phase not in (message('total'), "memo", "recall"):
        raise ValueError(message('Unknown timing phase'))
    return [Attempt(r.correct_letters, r.scored_letters,
                    {"total": r.centiseconds, "memo": r.memo_centiseconds, "recall": r.recall_centiseconds}[phase],
                    memo=r.memo_centiseconds, recall=r.recall_centiseconds)
            for r in rounds if scheme is None or r.scheme_name == scheme]


def percentage(correct, scored):
    return 100 * correct / scored if scored else None


def median_of(values):
    finite = [v for v in values if v is not None]
    return median(finite) if finite else None


@dataclass(frozen=True, slots=True)
class Block:
    attempts: int
    correct: int
    scored: int
    median: float | None
    timed: int

    @property
    def accuracy(self):
        return percentage(self.correct, self.scored)


def block(rows):
    return Block(len(rows), sum(r.correct for r in rows), sum(r.scored for r in rows),
                 median_of(r.time for r in rows), sum(r.time is not None for r in rows))


@dataclass(frozen=True, slots=True)
class Point:
    number: int
    attempt: Attempt
    rolling: Block
    group: Block  # All attempts since the preceding chart point, including this one.


@dataclass(frozen=True, slots=True)
class Summary:
    overall: Block
    recent: Block | None
    best: int | None
    perfect: int
    memo_median: float | None
    recall_median: float | None
    points: tuple[Point, ...]
    latest: tuple[Point, ...]


def select_range(rows, limit=None):
    """Keep original attempt numbering inside the selected session or scheme."""
    if limit is not None and limit not in WINDOWS:
        raise ValueError(message('Unsupported history range'))
    offset = max(0, len(rows)-limit) if limit is not None else 0
    return (rows[offset:] if offset else rows), offset


def _prefix_blocks(rows, wanted):
    # Two heaps keep exact cumulative medians without sorting every prefix.
    lower, upper, result = [], [], {}
    correct = scored = 0
    for i, row in enumerate(rows):
        correct += row.correct
        scored += row.scored
        value = row.time
        if value is not None:
            if not lower or value <= -lower[0]:
                heappush(lower, -value)
            else:
                heappush(upper, value)
            if len(lower) > len(upper)+1:
                heappush(upper, -heappop(lower))
            elif len(upper) > len(lower):
                heappush(lower, -heappop(upper))
        if i in wanted:
            mid = (None if not lower else -lower[0] if len(lower) > len(upper)
                   else (-lower[0]+upper[0])/2)
            result[i] = Block(i+1, correct, scored, mid, len(lower)+len(upper))
    return result


def _single(row):
    return Block(1, row.correct, row.scored, row.time, int(row.time is not None))


def plot_ends(n):
    """End index of every plotted group. Groups are consecutive with no gaps."""
    return (list(range(n)) if n <= PLOT_LIMIT else
            [i*(n-1)//(PLOT_LIMIT-1) for i in range(PLOT_LIMIT)])


def summarize(rows, window=None, *, offset=0):
    """Cumulative by default. The optional chart window never changes the sample."""
    if window is not None and window not in WINDOWS:
        raise ValueError(message('Unsupported chart window'))
    n = len(rows)
    # Adjacent groups (no gaps). Large plots retain both endpoints and account
    # for every attempt; the recent table still contains the actual last 12.
    ends = plot_ends(n)
    tail = range(max(0,n-12),n)
    wanted = set(ends).union(tail)
    trends = (_prefix_blocks(rows,wanted) if window is None else
              {i:block(rows[max(0,i+1-window):i+1]) for i in wanted})
    points = []
    first = 0
    for i in ends:
        group = _single(rows[i]) if i == first else block(rows[first:i+1])
        points.append(Point(offset+i+1, rows[i], trends[i], group))
        first = i+1
    latest = tuple(Point(offset+i+1, rows[i], trends[i], _single(rows[i])) for i in tail)
    recent = trends.get(n-1)
    overall = recent if window is None and recent is not None else block(rows)
    return Summary(overall, recent, min((r.time for r in rows if r.time is not None), default=None),
                   sum(r.scored > 0 and r.correct == r.scored for r in rows),
                   median_of(r.memo for r in rows), median_of(r.recall for r in rows),
                   tuple(points), latest)


def trimmed_time(times):
    """The timer's Ao5/Ao12 rule: drop best and worst; None is a DNF."""
    if len(times) < 3:
        return None
    finite = sorted(t for t in times if t is not None)
    dnfs = len(times) - len(finite)
    if dnfs >= 2:
        return message('DNF')
    middle = finite[1:] if dnfs else finite[1:-1]
    return round(sum(middle) / len(middle))

