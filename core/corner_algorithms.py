"""Verified supplied algorithms and their one-move UFR setup alternatives.

Built-ins are code-owned options, never inserted into a user's saved records.
The empty preference keeps choosing the best available built-in. Personal
alternatives and explicitly preferred built-ins retain their stable IDs.
"""
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256

from core.algorithms import apply_move, inverse_moves, inverse_state, normalized_state, parse_algorithm
from core.corner_algorithm_seeds import SUPPLIED_ALGORITHMS
from core.corner_cases import corner_cases, identify_case_state
from core.cube_definitions import CORNER_PIECES, CORNER_STICKER_ORDER, EDGE_STICKER_ORDER, find_piece_for_sticker
from core.tracer import _at, _key, _solved

SETUP_MOVES = tuple(face + wide + suffix for wide in ('', 'w')
                    for face in 'URFDLB' for suffix in ('', "'", '2'))
QUALITY_NOTICE = 'Built-in algorithms may not be optimal in this version. Save your own alg to replace the default.'


@dataclass(frozen=True)
class BuiltinAlgorithm:
    id: str
    name: str
    alg: str
    origin: str
    position: str = ''
    setup: str = ''


def _commutator_source(text):
    # Accept the supplied setup:[A,B] column as canonical [setup: [A,B]].
    return text if text.startswith('[') else '[' + text + ']'


def _verify_seed(position, source, commutator):
    algorithm = parse_algorithm(_commutator_source(commutator))
    net = normalized_state(algorithm)
    if normalized_state(parse_algorithm(source)) != net:
        raise ValueError(f'Supplied algorithm and commutator disagree: {position}')
    buffer, first, second = position.split('-')
    initial = inverse_state(net)
    involved = {find_piece_for_sticker(s, CORNER_PIECES) for s in (buffer, first, second)}
    if (len(involved) != 3 or None in involved
            or (_at(initial, buffer), _at(initial, first), _at(initial, second)) != (first, second, buffer)
            or any(_at(net, s) != s for s in EDGE_STICKER_ORDER)
            or any(_at(net, s) != s for piece, stickers in CORNER_PIECES.items()
                   if piece not in involved for s in stickers)
            or sum(_at(net, s) != s for s in CORNER_STICKER_ORDER) != 9):
        raise ValueError(f'Supplied algorithm does not solve its stated pure corner cycle: {position}')
    return algorithm, net


def _conjugated_state(net, before, undo):
    # Relabel the seed's input stickers by the setup state, then undo the
    # setup's positions. This composes full sticker permutations without
    # resimulating every move of the same seed for all 36 setups.
    return apply_move({p: before[_key(home)] for p, home in net.items()}, undo)


@lru_cache(maxsize=1)
def supplied_case_algorithms():
    transitions = [(move, apply_move(_solved(), move), inverse_moves((move,))[0]) for move in SETUP_MOVES]
    found, seen = {}, set()
    seeds = []
    for position, expanded, commutator in SUPPLIED_ALGORITHMS:
        algorithm, net = _verify_seed(position, expanded, commutator)
        try:
            direct_case = identify_case_state(net)
        except ValueError:
            direct_case = None  # the four UFL seeds still supply useful setups
        seeds.append((position, algorithm, net, direct_case))
    # Register every direct submission before deduplicating setup variants.
    # A preceding seed's setup must not hide a later direct submission.
    variants = [(position, algorithm, direct_case, '', net, algorithm.moves)
                for position, algorithm, net, direct_case in seeds]
    variants += [(position, algorithm, direct_case, move, _conjugated_state(net, before, undo),
                  (move,) + algorithm.moves + (undo,))
                 for position, algorithm, net, direct_case in seeds for move, before, undo in transitions]
    for position, algorithm, direct_case, setup, effect, moves in variants:
        try:
            key = identify_case_state(effect)
        except ValueError:
            continue
        if setup and key == direct_case:
            continue
        if (key, moves) in seen:
            continue
        seen.add((key, moves))
        source = f'[{setup}: {algorithm.source}]' if setup else algorithm.source
        identifier = 'builtin:' + sha256((position + '\n' + source).encode()).hexdigest()[:20]
        name = f'Setup {setup} · {position}' if setup else f'Supplied · {position}'
        candidate = BuiltinAlgorithm(identifier, name, source,
            'one_move' if setup else 'supplied', position, setup)
        found.setdefault(key, []).append((candidate, len(moves)))
    return {key: tuple(c for c, _ in sorted(values,
                key=lambda item: (item[0].origin != 'supplied', item[1], 'w' in item[0].setup, item[0].id)))
            for key, values in found.items()}


def builtin_algorithms(key):
    case = corner_cases()[key]
    fallback = BuiltinAlgorithm('builtin:generated', 'Generated fallback · may not be optimal',
                                case.starter, 'generated')
    return supplied_case_algorithms().get(key, ()) + (fallback,)
