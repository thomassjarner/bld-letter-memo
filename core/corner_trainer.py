"""Read-only UFR recall sessions and verified physical-cube setups."""
from copy import deepcopy
from dataclasses import dataclass
import random

from core.algorithms import inverse_moves, inverse_state, parse_algorithm, simplify_moves
from core.commutator_finder import execution_signature, find_commutator, has_commutator_structure
from core.corner_algorithms import builtin_algorithms
from core.corner_cases import SUBSETS, corner_cases, identify_case_state
from core.corner_walkthrough import _normalized_execution, apply_moves
from core.focused_scrambles import MOVES, solve_facelets, state_facelets
from core.tracer import _solved

STATUSES = ('new', 'learning', 'learned')


@dataclass(frozen=True)
class TrainerFilters:
    subsets: frozenset = frozenset(SUBSETS)
    first: str = 'all'
    second: str = 'all'
    statuses: frozenset = frozenset(STATUSES)
    favorites: bool = False


def matching_cases(filters, records):
    matches = []
    for case in corner_cases().values():
        record = records.get(case.id)
        status = record.status if record else 'new'
        if (case.subset in filters.subsets and status in filters.statuses
                and filters.first in ('all', case.first) and filters.second in ('all', case.second)
                and (not filters.favorites or record and record.favorite)):
            matches.append(case)
    return matches


@dataclass(frozen=True)
class TrainerCard:
    case_id: str
    first: str
    second: str
    subset: str
    letters: str
    name: str
    algorithm_id: str
    source: str
    moves: tuple
    commutator: str | None
    setup: tuple
    warning: str = ''

    @property
    def initial(self):
        return apply_moves(_solved(), self.setup)


def _notation(source, moves, reset):
    if not reset and has_commutator_structure(source):
        return source
    try:
        found = find_commutator(' '.join(moves), max_checks=1500, max_seconds=.08)
        if found and execution_signature(parse_algorithm(found.expression).moves) == execution_signature(moves):
            return found.expression
    except ValueError:
        pass
    return None


def make_card(case_id, scheme, records, rng=None):
    """Select the library's preferred alg, then independently set up its case."""
    rng = rng or random.SystemRandom()
    case = corner_cases()[case_id]
    builtins = builtin_algorithms(case.id)
    record = records.get(case.id)
    preferred = record.preferred_algorithm if record else ''
    personal = next((a for a in record.algorithms if a.id == preferred), None) if record else None
    selected = personal or next((a for a in builtins if a.id == preferred), builtins[0])
    warning = ''
    for candidate in (selected, builtins[0]):
        try:
            moves, effect, reset = _normalized_execution(candidate.alg)
            if identify_case_state(effect) != case.id:
                raise ValueError('Wrong case')
            break
        except (ValueError, StopIteration):
            warning = 'Your preferred algorithm could not be verified. Showing the built-in recommendation; your saved alg is unchanged.'
    else:
        raise ValueError('Could not verify an algorithm for this case.')
    initial = inverse_state(effect)
    # A short random detour plus the bundled two-phase solver avoids simply
    # displaying the inverse of the algorithm being tested.
    detour = []
    for _ in range(4):
        detour.append(rng.choice([m for m in MOVES if not detour or m[0] != detour[-1][0]]))
    try:
        solution = solve_facelets(state_facelets(apply_moves(initial, detour)))
    except Exception:
        solution = None
    setup = ()
    if solution and all(m in MOVES for m in solution.split()):
        setup = simplify_moves(inverse_moves(tuple(solution.split())) + inverse_moves(tuple(detour)))
    if not setup or apply_moves(_solved(), setup) != initial:
        # Native Python without JS still has a portable, exact setup, based on
        # the generated starter rather than a user's preferred algorithm.
        starter_moves, starter_effect, _ = _normalized_execution(case.starter)
        if starter_effect != effect:
            raise ValueError('The portable setup does not match this case.')
        setup = simplify_moves(inverse_moves(starter_moves))
    if apply_moves(_solved(), setup) != initial or apply_moves(initial, moves) != _solved():
        raise ValueError('The setup and solution could not be verified.')
    def letter(sticker):
        value = scheme.corners.stickers.get(sticker, '') if scheme else ''
        return value if value and value != 'BUFFER' else '?'
    return TrainerCard(case.id, case.first, case.second, case.subset,
        letter(case.first) + letter(case.second), candidate.name, candidate.id,
        candidate.alg, tuple(moves), _notation(candidate.alg, moves, reset), tuple(setup), warning)


@dataclass(frozen=True)
class RecallResult:
    card: TrainerCard
    remembered: bool
    revealed: bool


class CornerRecallSession:
    """One shuffled pass. Scheme, case membership and algorithm choices freeze."""
    def __init__(self, cases, scheme, records, rng=None):
        self.rng = rng or random.SystemRandom()
        self.deck = list(dict.fromkeys(c.id if hasattr(c, 'id') else c for c in cases))
        if not self.deck:
            raise ValueError('No cases match these filters.')
        if any(key not in corner_cases() for key in self.deck):
            raise ValueError('Unknown corner case.')
        self.rng.shuffle(self.deck)
        self.scheme = deepcopy(scheme)
        self.records = deepcopy(records)
        self.position = 0
        self.results = []
        self.card = None
        self.revealed = False

    @property
    def answered(self):
        return len(self.results) > self.position

    @property
    def complete(self):
        return len(self.results) == len(self.deck)

    @property
    def remembered(self):
        return sum(r.remembered for r in self.results)

    @property
    def recall_rate(self):
        return 100 * self.remembered / len(self.results) if self.results else 0

    def prepare(self):
        if self.card is None:
            self.card = make_card(self.deck[self.position], self.scheme, self.records, self.rng)
        return self.card

    def reveal(self):
        if self.card is None or self.answered:
            return False
        self.revealed = True
        return True

    def grade(self, remembered):
        if self.card is None or self.answered:
            return False
        self.results.append(RecallResult(self.card, bool(remembered), self.revealed))
        return True

    def advance(self):
        if not self.answered or self.complete:
            return False
        self.position += 1
        self.card = None
        self.revealed = False
        return True
