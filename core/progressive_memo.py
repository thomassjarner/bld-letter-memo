"""Progressive Memo sequencing and scoring, using the existing BLD tracer."""
from __future__ import annotations

from dataclasses import dataclass
import unicodedata

from core.cube_definitions import CATEGORY_PIECES, find_piece_for_sticker
from core.tracer import ScrambleError, ScrambleTracer
from data.models import LetterScheme, ProgressiveRecall


def normalize_letters(value: str) -> str:
    return "".join(unicodedata.normalize("NFC", value or "").upper().split())


def pairs(letters: str) -> tuple[str, ...]:
    return tuple(letters[i:i + 2] for i in range(0, len(letters), 2))


@dataclass(frozen=True)
class MemoPrompt:
    category: str
    kind: str
    letters: str
    index: int = 0
    count: int = 0

    @property
    def label(self) -> str:
        if self.kind == "orientation":
            if self.category == "edges" and self.count:
                return f"Flip {self.index + 1} / {self.count}"
            return "All twists" if self.category == "corners" else "All flips"
        return f"Pair {self.index + 1} / {self.count}"


@dataclass(frozen=True)
class CategoryMemo:
    category: str
    ordinary_pairs: tuple[str, ...]
    orientation_pairs: tuple[str, ...]

    @property
    def prompts(self) -> tuple[MemoPrompt, ...]:
        ordinary = tuple(MemoPrompt(self.category, "pair", pair, i, len(self.ordinary_pairs))
                         for i, pair in enumerate(self.ordinary_pairs))
        orientation = (MemoPrompt(self.category, "orientation", "".join(self.orientation_pairs)),) if self.orientation_pairs else ()
        return ordinary + orientation

    @property
    def recall_prompts(self) -> tuple[MemoPrompt, ...]:
        if self.category != "edges":
            return self.prompts
        ordinary = tuple(prompt for prompt in self.prompts if prompt.kind == "pair")
        flips = tuple(MemoPrompt(self.category, "orientation", pair, index, len(self.orientation_pairs))
                      for index, pair in enumerate(self.orientation_pairs))
        return ordinary + flips


@dataclass(frozen=True)
class ProgressivePlan:
    scramble: str
    scheme_name: str
    scheme_snapshot: dict
    memo_order: str
    execution_order: str
    categories: tuple[CategoryMemo, ...]
    recall_prompts: tuple[MemoPrompt, ...]


def build_plan(scramble: str, scheme: LetterScheme,
               corner_cycle_break_overrides=None, edge_cycle_break_overrides=None) -> ProgressivePlan:
    # Freeze the scheme for this attempt. Later edits cannot change its answer.
    snapshot = scheme.duplicate(scheme.name)
    for category in ("corners", "edges"):
        cat = getattr(snapshot, category)
        buffer = cat.buffer_sticker or cat.buffer_piece
        if not buffer or not find_piece_for_sticker(buffer, CATEGORY_PIECES[category]):
            raise ScrambleError(f"Choose a {category[:-1]} buffer in Letter Schemes first.")
    result = ScrambleTracer().trace(scramble, snapshot,
                                   corner_cycle_break_overrides=corner_cycle_break_overrides,
                                   edge_cycle_break_overrides=edge_cycle_break_overrides)
    categories = {}
    for category, prefix in (("corners", "corner"), ("edges", "edge")):
        letters = getattr(result, prefix + "_letters")
        targets = getattr(result, prefix + "_targets")
        flags = getattr(result, prefix + "_orientation_target_flags")
        missing = [target for target, letter in zip(targets, letters) if letter == "?"]
        if missing:
            raise ScrambleError(f"Add {category} letters for {', '.join(dict.fromkeys(missing))} in Letter Schemes first.")
        ordinary, orientation = [], []
        for index, letter in enumerate(letters):
            orientation_target = index < len(flags) and flags[index]
            (orientation if orientation_target else ordinary).append(letter)
        if category == "edges" and snapshot.three_style_enabled and len("".join(ordinary)) % 2:
            # The tracer already applies the configured parity swap. Never
            # conceal an inconsistent plan by dropping or padding a target.
            raise ScrambleError("3-style edge memo must contain complete pairs. Check the scheme's edge letters and parity settings.")
        categories[category[0].upper()] = CategoryMemo(category, pairs("".join(ordinary)), pairs("".join(orientation)))
    memo_order = snapshot.memo_order or "CE"
    execution_order = snapshot.execution_order or "EC"
    if memo_order not in {"CE", "EC"} or execution_order not in {"CE", "EC"}:
        raise ScrambleError("Set valid CE / EC memo and execution orders in Letter Schemes.")
    recall = tuple(prompt for letter in execution_order for prompt in categories[letter].recall_prompts)
    if not recall:
        raise ScrambleError("This scramble has no letter targets to recall. Try a new scramble.")
    return ProgressivePlan(scramble, snapshot.name, snapshot.to_dict(), memo_order, execution_order,
                           tuple(categories[letter] for letter in memo_order), recall)


def align_letters(expected: str, entered: str) -> list[tuple[str, str, bool]]:
    """Minimum-edit alignment; missing/extra letters get explicit empty slots."""
    expected, entered = normalize_letters(expected), normalize_letters(entered)
    rows, cols = len(expected), len(entered)
    costs = [[0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(rows + 1):
        costs[i][0] = i
    for j in range(cols + 1):
        costs[0][j] = j
    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            costs[i][j] = min(costs[i - 1][j - 1] + (expected[i - 1] != entered[j - 1]),
                              costs[i - 1][j] + 1, costs[i][j - 1] + 1)
    aligned = []
    i, j = rows, cols
    while i or j:
        if i and j and costs[i][j] == costs[i - 1][j - 1] + (expected[i - 1] != entered[j - 1]):
            aligned.append((expected[i - 1], entered[j - 1], expected[i - 1] == entered[j - 1]))
            i, j = i - 1, j - 1
        elif i and costs[i][j] == costs[i - 1][j] + 1:
            aligned.append((expected[i - 1], "", False))
            i -= 1
        else:
            aligned.append(("", entered[j - 1], False))
            j -= 1
    return aligned[::-1]


def score_recall(recall: list[ProgressiveRecall]) -> tuple[int, int]:
    aligned = [letter for item in recall for letter in align_letters(item.expected, item.entered)]
    return sum(match for _, _, match in aligned), len(aligned)


class ProgressiveRun:
    """One attempt; UI controls and delayed intro tasks do not own the answers."""
    def __init__(self, plan: ProgressivePlan, *, allow_memo_navigation=False, show_category_overview=True):
        self.plan = plan
        self.allow_memo_navigation = bool(allow_memo_navigation)
        self.show_category_overview = bool(show_category_overview)
        self.memo_revision = 0
        self.phase = "intro"
        self.category_index = 0
        self.prompt_index = 0
        self.recall_index = 0
        self.started_at: float | None = None
        self.memo_finished_at: float | None = None
        self.finished_at: float | None = None
        self.recall: list[ProgressiveRecall] = []
        self._drafts: dict[int, str] = {}

    @property
    def current_input(self) -> str:
        if self._drafts.get(self.recall_index):
            return self._drafts[self.recall_index]
        return self.recall[self.recall_index].entered if self.recall_index < len(self.recall) else ""

    def remember_input(self, value: str) -> None:
        value = normalize_letters(value)
        if self.phase == "recall" and value:
            # Empty edits, selection changes and review navigation must never
            # erase an answer. Only new letters replace the retained input.
            self._drafts[self.recall_index] = value

    def previous(self, draft: str | None = None) -> bool:
        if self.phase != "recall" or self.recall_index == 0:
            return False
        if draft is not None:
            self.remember_input(draft)
        self.recall_index -= 1
        return True

    @property
    def category(self) -> CategoryMemo:
        return self.plan.categories[self.category_index]

    @property
    def prompt(self) -> MemoPrompt:
        if self.phase == "recall":
            return self.plan.recall_prompts[self.recall_index]
        return self.category.prompts[self.prompt_index]

    def finish_intro(self, now: float) -> bool:
        if self.phase != "intro":
            return False
        if self.category.prompts:
            self.phase = "memo"
            if self.started_at is None:
                self.started_at = now
        elif self.show_category_overview:
            self.phase = "overview"
        else:
            self._advance_category(now)
        self.memo_revision += 1
        return True

    @property
    def can_memo_previous(self) -> bool:
        if not self.allow_memo_navigation or self.phase not in {"intro", "memo", "overview"}:
            return False
        return (self.phase == "memo" and self.prompt_index > 0
                or self.phase == "overview" and bool(self.category.prompts)
                or any(category.prompts for category in self.plan.categories[:self.category_index]))

    def previous_memo(self) -> bool:
        if not self.can_memo_previous:
            return False
        if self.phase == "memo" and self.prompt_index > 0:
            self.prompt_index -= 1
        elif self.phase == "overview" and self.category.prompts:
            self.prompt_index = len(self.category.prompts) - 1
        else:
            self.category_index = next(i for i in range(self.category_index - 1, -1, -1)
                                       if self.plan.categories[i].prompts)
            self.prompt_index = len(self.category.prompts) - 1
        self.phase = "memo"
        self.memo_revision += 1
        return True

    def _advance_category(self, now):
        if self.category_index + 1 < len(self.plan.categories):
            self.category_index += 1
            self.prompt_index = 0
            self.phase = "intro"
        else:
            self.phase = "recall"
            self.memo_finished_at = now

    def next(self, now: float) -> bool:
        if self.phase == "memo":
            self.prompt_index += 1
            if self.prompt_index == len(self.category.prompts):
                if self.show_category_overview:
                    self.phase = "overview"
                else:
                    self._advance_category(now)
            self.memo_revision += 1
            return True
        if self.phase == "overview":
            self._advance_category(now)
            self.memo_revision += 1
            return True
        return False

    def submit(self, value: str, now: float) -> bool:
        if self.phase != "recall":
            return False
        prompt = self.prompt
        value = normalize_letters(value) or self.current_input
        answer = ProgressiveRecall(prompt.category, prompt.kind, prompt.letters, value)
        if self.recall_index < len(self.recall):
            self.recall[self.recall_index] = answer
        else:
            self.recall.append(answer)
        self.remember_input(value)
        self.recall_index += 1
        if self.recall_index == len(self.plan.recall_prompts):
            self.phase = "result"
            self.finished_at = now
        return True

    def timings(self) -> tuple[int, int]:
        if self.phase != "result" or self.started_at is None or self.memo_finished_at is None or self.finished_at is None:
            raise ValueError("An unfinished attempt has no saved timing.")
        total = max(0, round((self.finished_at - self.started_at) * 100))
        memo = max(0, min(total, round((self.memo_finished_at - self.started_at) * 100)))
        return memo, total - memo
