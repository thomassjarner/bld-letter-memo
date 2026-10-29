"""UFR corner cases, independent of letter labels and preferred algorithms."""
from collections import deque
from dataclasses import dataclass
from functools import lru_cache

from core.algorithms import inverse_state, normalized_state, parse_algorithm
from core.cube_definitions import CORNER_PIECES, CORNER_STICKER_ORDER, EDGE_STICKER_ORDER, find_piece_for_sticker
from core.tracer import _apply, _at, _solved

BUFFER = 'UFR'
BASE_ALG = "[R, U' L' U]"
SUBSETS = ('U/U', 'U/D', 'D/U', 'D/D')
TARGETS = tuple(s for s in CORNER_STICKER_ORDER if s not in CORNER_PIECES[BUFFER])


def valid_targets(first, second):
    return (first in TARGETS and second in TARGETS
            and find_piece_for_sticker(first, CORNER_PIECES) != find_piece_for_sticker(second, CORNER_PIECES))


def case_id(first, second):
    if not valid_targets(first, second):
        raise ValueError('Choose stickers on two different non-buffer corners.')
    return first + ':' + second


def subset_for(first, second):
    return ('U' if 'U' in first else 'D') + '/' + ('U' if 'U' in second else 'D')


def identify_case(algorithm):
    """Identify the ordered memo targets solved by a pure UFR three-cycle."""
    return identify_case_state(normalized_state(algorithm))


def identify_case_state(net):
    """Identify a case from an effect already normalized to the original frame."""
    initial = inverse_state(net)
    if any(_at(net, s) != s for s in EDGE_STICKER_ORDER):
        raise ValueError('This algorithm also changes edges. A UFR corner case must restore all edges.')
    first = _at(initial, BUFFER)
    second = _at(initial, first)
    if not valid_targets(first, second) or _at(initial, second) != BUFFER:
        raise ValueError('This algorithm is not a pure UFR corner three-cycle.')
    involved = {BUFFER, find_piece_for_sticker(first, CORNER_PIECES), find_piece_for_sticker(second, CORNER_PIECES)}
    if any(_at(net, s) != s for piece, stickers in CORNER_PIECES.items()
           if piece not in involved for s in stickers):
        raise ValueError('This algorithm changes additional corners or twists.')
    return case_id(first, second)


@dataclass(frozen=True)
class CornerCase:
    id: str
    first: str
    second: str
    subset: str
    starter: str
    setup: str


@lru_cache(maxsize=1)
def corner_cases():
    """Generate verified starter conjugates; these are not an optimized alg sheet.

    Breadth-first search tracks one oriented sticker cycle through setups.
    The case IDs and layer subsets do not depend on the chosen starter alg.
    """
    seeds = []
    for body in (BASE_ALG, "[U' L' U, R]"):
        initial = inverse_state(normalized_state(parse_algorithm(body)))
        covered = set()
        for a in CORNER_STICKER_ORDER:
            if a in covered or _at(initial, a) == a:
                continue
            b = _at(initial, a)
            triple = (a, b, _at(initial, b))
            covered.update(triple)
            seeds.append((triple, (), body))
    transitions = []
    for face in 'URFDLB':
        for suffix in ('', "'", '2'):
            move = face + suffix
            state = _apply(_solved(), move)
            transitions.append((move, {s: _at(state, s) for s in CORNER_STICKER_ORDER}))
    queue, seen, found = deque(seeds), {s[0] for s in seeds}, {}
    while queue and len(found) < 378:
        triple, setup, body = queue.popleft()
        if BUFFER in triple:
            index = triple.index(BUFFER)
            first, second = triple[(index + 1) % 3], triple[(index + 2) % 3]
            key = case_id(first, second)
            if key not in found:
                prefix = ' '.join(setup)
                alg = f'[{prefix}: {body}]' if prefix else body
                found[key] = CornerCase(key, first, second, subset_for(first, second), alg, prefix)
        for move, mapping in transitions:
            target = tuple(mapping[s] for s in triple)
            if target not in seen:
                seen.add(target)
                queue.append((target, (move,) + setup, body))
    if len(found) != 378:
        raise ValueError('Could not build the full UFR corner case catalog.')
    return {case_id(a, b): found[case_id(a, b)] for a in TARGETS for b in TARGETS if valid_targets(a, b)}


def case_letters(case, scheme):
    def label(sticker):
        value = scheme.corners.stickers.get(sticker, '') if scheme else ''
        return value if value and value != 'BUFFER' else '?'
    return label(case.first) + label(case.second)
