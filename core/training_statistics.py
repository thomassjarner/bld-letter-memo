"""Read-only training statistics. Attempt order works even for undated backups."""
from dataclasses import dataclass
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


def timer_attempts(solves):
    return [Attempt(int(not s.dnf), 1, None if s.dnf else effective_time(s), s.plus2 and not s.dnf)
            for s in solves]


def memo_attempts(rounds, scheme=None, phase="total"):
    if phase not in ("total", "memo", "recall"):
        raise ValueError("Unknown timing phase")
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


@dataclass(frozen=True, slots=True)
class Summary:
    overall: Block
    recent: Block | None
    best: int | None
    perfect: int
    memo_median: float | None
    recall_median: float | None
    points: tuple


def summarize(rows, window=12):
    if window not in WINDOWS:
        raise ValueError("Unsupported rolling window")
    n = len(rows)
    # Bound chart work for long histories; the first visible point can still
    # use earlier attempts. No tracing, time-based guesses or synthetic DNFs.
    points = tuple(Point(end, rows[end - 1], block(rows[max(0, end-window):end]))
                   for end in range(max(1, n-PLOT_LIMIT+1), n+1))
    return Summary(
        block(rows), points[-1].rolling if points else None,
        min((r.time for r in rows if r.time is not None), default=None),
        sum(r.scored > 0 and r.correct == r.scored for r in rows),
        median_of(r.memo for r in rows), median_of(r.recall for r in rows), points,
    )


def trimmed_time(times):
    """The timer's Ao5/Ao12 rule: drop best and worst; None is a DNF."""
    if len(times) < 3:
        return None
    finite = sorted(t for t in times if t is not None)
    dnfs = len(times) - len(finite)
    if dnfs >= 2:
        return "DNF"
    middle = finite[1:] if dnfs else finite[1:-1]
    return round(sum(middle) / len(middle))


def projected_ao5(rows, next_single):
    """Conditional next Ao5, not a simulated run of five future solves."""
    if len(rows) < 4:
        return None
    last_four = [r.time for r in rows[-4:]]
    if last_four.count(None) >= 2:
        return "DNF"  # Even a successful fifth solve cannot rescue this average.
    if next_single is None:
        return None
    return trimmed_time([*last_four, round(next_single)])
