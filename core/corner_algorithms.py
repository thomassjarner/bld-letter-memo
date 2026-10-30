"""Verified supplied algorithms and their one-move UFR setup alternatives.

Built-ins are code-owned options, never inserted into a user's saved records.
The empty preference keeps choosing the best available built-in. Personal
alternatives and explicitly preferred built-ins retain their stable IDs.
"""
from dataclasses import dataclass
from functools import cached_property, lru_cache
from hashlib import sha256
import json

from core.algorithms import apply_move, inverse_moves, inverse_state, normalized_state, parse_algorithm, simplify_moves
from core.corner_algorithm_additions import ADDITIONAL_ALGORITHMS
from core.corner_algorithm_seeds import SUPPLIED_ALGORITHMS
from core.corner_cases import corner_cases, identify_case_state
from core.cube_definitions import CORNER_PIECES, CORNER_STICKER_ORDER, EDGE_STICKER_ORDER, find_piece_for_sticker
from core.tracer import _at, _key, _solved

SETUP_MOVES = tuple(face + wide + suffix for wide in ('', 'w')
                    for face in 'URFDLB' for suffix in ('', "'", '2'))
QUALITY_NOTICE = 'Built-in algorithms may not be optimal in this version. Save your own alg to replace the default.'
ALL_SUBMISSIONS = tuple(dict.fromkeys(SUPPLIED_ALGORITHMS + ADDITIONAL_ALGORITHMS))


@dataclass(frozen=True)
class BuiltinAlgorithm:
    id: str
    name: str
    alg: str
    origin: str
    position: str = ''
    setup: str = ''
    _moves: tuple = ()

    @cached_property
    def moves(self):
        return self._moves or parse_algorithm(self.alg).moves


def _commutator_source(text):
    # Accept the supplied setup:[A,B] column as canonical [setup: [A,B]].
    return text if text.startswith('[') else '[' + text + ']'


def _verify_seed(position, source, commutator):
    plain = parse_algorithm(source)
    algorithm = plain if commutator.strip().casefold() in ('not found.', 'not found', '') else parse_algorithm(_commutator_source(commutator))
    net = normalized_state(algorithm)
    if normalized_state(plain) != net:
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


def generate_algorithm_registry():
    """Full verification/build route; normal page loading uses the index."""
    transitions = [(move, apply_move(_solved(), move), inverse_moves((move,))[0]) for move in SETUP_MOVES]
    found, seen = {}, set()
    seeds = []
    for position, expanded, commutator in ALL_SUBMISSIONS:
        algorithm, net = _verify_seed(position, expanded, commutator)
        try:
            direct_case = identify_case_state(net)
        except ValueError:
            direct_case = None  # other buffers still supply useful UFR setups
        seeds.append((position, algorithm, net, direct_case))
    # Register every direct submission before deduplicating setup variants.
    # A preceding seed's setup must not hide a later direct submission.
    def variants():
        for position, algorithm, net, direct_case in seeds:
            yield position, algorithm, direct_case, '', net, algorithm.moves
        for position, algorithm, net, direct_case in seeds:
            for move, before, undo in transitions:
                yield (position, algorithm, direct_case, move, _conjugated_state(net, before, undo),
                       (move,) + algorithm.moves + (undo,))
    for position, algorithm, direct_case, setup, effect, moves in variants():
        try:
            key = identify_case_state(effect)
        except ValueError:
            continue
        if setup and key == direct_case:
            continue
        source = f'[{setup}: {algorithm.source}]' if setup else algorithm.source
        identifier = 'builtin:' + sha256((position + '\n' + source).encode()).hexdigest()[:20]
        if identifier in seen:
            continue
        seen.add(identifier)
        name = f'Setup {setup} · {position}' if setup else f'Supplied · {position}'
        candidate = BuiltinAlgorithm(identifier, name, source,
            'one_move' if setup else 'supplied', position, setup, moves)
        found.setdefault(key, []).append((candidate, len(simplify_moves(moves))))
    return {key: tuple(c for c, _ in sorted(values,
                key=lambda item: (item[0].origin != 'supplied', item[1], 'w' in item[0].setup, item[0].id)))
            for key, values in found.items()}


@lru_cache(maxsize=1)
def _compiled_catalogs():
    from core.corner_algorithm_index import ALGORITHM_INDEX, SUBMISSIONS_SHA256
    digest = sha256(json.dumps(ALL_SUBMISSIONS, ensure_ascii=False).encode()).hexdigest()
    if digest != SUBMISSIONS_SHA256:
        raise ValueError('Rebuild the corner algorithm index after changing supplied algorithms.')
    sources = [(position, source.strip() if comm.strip().casefold() in ('not found.', 'not found', '')
                else _commutator_source(comm).strip()) for position, source, comm in ALL_SUBMISSIONS]
    registry, visible = {}, {}
    for key, seed, setup, show in ALGORITHM_INDEX:
        position, body = sources[seed]
        source = f'[{setup}: {body}]' if setup else body
        identifier = 'builtin:' + sha256((position + '\n' + source).encode()).hexdigest()[:20]
        name = f'Setup {setup} · {position}' if setup else f'Supplied · {position}'
        algorithm = BuiltinAlgorithm(identifier, name, source, 'one_move' if setup else 'supplied', position, setup)
        registry.setdefault(key, []).append(algorithm)
        if show: visible.setdefault(key, []).append(algorithm)
    return ({key: tuple(group) for key, group in registry.items()},
            {key: tuple(group) for key, group in visible.items()})


def _algorithm_registry():
    return _compiled_catalogs()[0]


@lru_cache(maxsize=1)
def supplied_case_algorithms():
    # Menus omit duplicate executions; the registry retains older IDs too.
    return _compiled_catalogs()[1]


def builtin_algorithms(key):
    case = corner_cases()[key]
    fallback = BuiltinAlgorithm('builtin:generated', 'Generated fallback · may not be optimal',
                                case.starter, 'generated')
    return _algorithm_registry().get(key, ()) + (fallback,)


def display_builtin_algorithms(key, retained=()):
    choices = list(supplied_case_algorithms().get(key, ()))
    shown = {a.id for a in choices}
    for algorithm in builtin_algorithms(key):
        if algorithm.id == 'builtin:generated' or algorithm.id in retained and algorithm.id not in shown:
            choices.append(algorithm)
            shown.add(algorithm.id)
    return tuple(choices)
