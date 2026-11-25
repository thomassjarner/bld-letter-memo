"""Recorded statistics. No tracing, forecasting, or changes to saved attempts."""
from bisect import bisect_left
from dataclasses import dataclass
from math import isqrt
from statistics import median

from core.ao5_statistics import AverageRecord, rolling_averages
from core.progressive_memo import score_recall
from core.training_statistics import Attempt, Block, Point, plot_ends


@dataclass(frozen=True, slots=True)
class TimeBin:
    low: int
    high: int  # inclusive; all stored times are in centiseconds
    count: int


@dataclass(frozen=True, slots=True)
class TimeProfile:
    total: int
    timed: tuple[int, ...]

    @classmethod
    def from_times(cls,times):
        return cls(len(times),tuple(sorted(t for t in times if t is not None)))

    def under(self,goal):
        return bisect_left(self.timed,goal)

    @property
    def mean(self):
        """Arithmetic mean of the observed times in this range, in centiseconds."""
        return sum(self.timed) / len(self.timed) if self.timed else None

    @property
    def middle_half(self):
        """Inclusive, linearly interpolated 25th and 75th percentiles."""
        if len(self.timed)<2:
            return None
        def quartile(q):
            i,rem=divmod((len(self.timed)-1)*q,4)
            return self.timed[i] if not rem else (self.timed[i]*(4-rem)+self.timed[i+1]*rem)/4
        return quartile(1),quartile(3)

    def bins(self):
        if not self.timed:
            return ()
        lo,hi = self.timed[0],self.timed[-1]
        if lo==hi:
            return (TimeBin(lo,hi,len(self.timed)),)
        # The 1/2/5 progression gives the same width to every band and keeps
        # boundaries readable. Include empty bands so gaps remain visible.
        limit=min(6,max(2,isqrt(len(self.timed))))
        scale=1
        while True:
            for factor in (1,2,5):
                step=scale*factor
                if hi//step-lo//step+1 <= limit:
                    first=lo//step*step
                    return tuple(TimeBin(a,a+step-1,self.under(a+step)-self.under(a))
                                 for a in range(first,hi+1,step))
            scale*=10


def timer_elapsed(rows):
    """Actual time on the clock, including failed attempts, excluding +2."""
    return sum((r.dnf_elapsed or 0) if r.time is None else r.time-200*int(r.plus2) for r in rows)


def duration_label(cs):
    if cs < 100:
        return f"{cs/100:.2f}s"
    minutes,seconds=divmod(cs//100,60)
    hours,minutes=divmod(minutes,60)
    if hours:
        return f"{hours}h {minutes:02}m {seconds:02}s"
    return f"{minutes}m {seconds:02}s" if minutes else f"{seconds}s"


@dataclass(frozen=True, slots=True)
class Ao5History:
    values: tuple[int | None, ...]  # First result ends at the fifth selected attempt.
    profile: TimeProfile

    @classmethod
    def from_times(cls,times):
        values=tuple(rolling_averages(times,5))
        return cls(values,TimeProfile.from_times(values))

    @property
    def record(self):
        p=self.profile
        return AverageRecord(len(p.timed),p.total,p.timed[0] if p.timed else None)

    def points(self,offset):
        out=[]
        start=0
        for end in plot_ends(len(self.values)):
            window=self.values[start:end+1]
            finite=[v for v in window if v is not None]
            group=Block(len(window),len(finite),len(window),median(finite) if finite else None,len(finite))
            last=window[-1]
            out.append(Point(offset+5+end,Attempt(int(last is not None),1,last),group,group))
            start=end+1
        return tuple(out)


@dataclass(frozen=True, slots=True)
class MemoSplit:
    edge_correct: int = 0
    edge_scored: int = 0
    corner_correct: int = 0
    corner_scored: int = 0
    detailed: int = 0


def memo_split(rounds):
    edges_ok=edges_n=corners_ok=corners_n=detailed=0
    for r in rounds:
        if not r.recall or any(i.category not in ("edges","corners") for i in r.recall):
            continue
        e,en=score_recall([i for i in r.recall if i.category=="edges"])
        c,cn=score_recall([i for i in r.recall if i.category=="corners"])
        # Old/partial imports may only have the totals. Don't guess which
        # category they belonged to or turn missing detail into a mistake.
        if en+cn==0 or (e+c,en+cn)!=(r.correct_letters,r.scored_letters):
            continue
        edges_ok+=e; edges_n+=en; corners_ok+=c; corners_n+=cn; detailed+=1
    return MemoSplit(edges_ok,edges_n,corners_ok,corners_n,detailed)
