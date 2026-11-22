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
    rolling: Block | None


@dataclass(frozen=True, slots=True)
class Summary:
    overall: Block
    recent: Block | None
    previous: Block | None
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
    points = tuple(Point(end, rows[end - 1], block(rows[end-window:end]) if end >= window else None)
                   for end in range(max(1, n-PLOT_LIMIT+1), n+1))
    return Summary(
        block(rows), points[-1].rolling if points else None,
        block(rows[n-2*window:n-window]) if n >= 2*window else None,
        min((r.time for r in rows if r.time is not None), default=None),
        sum(r.scored > 0 and r.correct == r.scored for r in rows),
        median_of(r.memo for r in rows), median_of(r.recall for r in rows), points,
    )
