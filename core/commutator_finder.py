"""Bounded recovery of commutator notation from a move sequence.

Only same-axis turn cleanup is used to match executions. A different alg for
the same target case is never presented as a recovered commutator. Every
returned expression also passes an exact full-sticker-state comparison.
"""
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
import time

from core.algorithms import _Parser, _expand, algorithm_states, inverse_moves, move_spec, parse_algorithm, simplify_moves
from core.corner_algorithms import ALL_SUBMISSIONS

BASES = ('R', 'L', 'M', 'Rw', 'Lw', 'x', 'U', 'D', 'E', 'Uw', 'Dw', 'y', 'F', 'B', 'S', 'Fw', 'Bw', 'z')
MOVES = tuple(base + suffix for base in BASES for suffix in ('', "'", '2'))


@dataclass(frozen=True)
class CommutatorResult:
    expression: str
    method: str


def execution_signature(moves):
    """Consecutive same-axis turns as exact three-layer rotation vectors."""
    groups = []
    for move in moves:
        axis, layers, quarter = move_spec(move)
        vector = tuple(quarter % 4 if layer in layers else 0 for layer in (-1, 0, 1))
        if groups and groups[-1][0] == axis:
            vector = tuple((a + b) % 4 for a, b in zip(groups.pop()[1], vector))
        if any(vector): groups.append((axis, vector))
    return tuple(groups)


@lru_cache(maxsize=1)
def _axis_forms():
    forms = {}
    for axis in 'xyz':
        found = {(0, 0, 0): ()}
        queue = deque([(0, 0, 0)])
        moves = [(move, execution_signature((move,))[0][1]) for move in MOVES if move_spec(move)[0] == axis]
        while queue:
            vector = queue.popleft()
            for move, delta in moves:
                target = tuple((a + b) % 4 for a, b in zip(vector, delta))
                if target not in found:
                    found[target] = found[vector] + (move,)
                    queue.append(target)
        forms[axis] = found
    return forms


def _normal_moves(signature):
    forms = _axis_forms()
    return tuple(move for axis, vector in signature for move in forms[axis][vector])


def _parts(node):
    kind, values = node
    if kind == 'comm': return (), _expand(values[0]), _expand(values[1])
    if kind == 'conj':
        inner = _parts(values[1])
        if inner is not None: return _expand(values[0]) + inner[0], inner[1], inner[2]
    if kind == 'inverse':
        inner = _parts(values)
        if inner is not None: return inner[0], inner[2], inner[1]
    return None


def _notation_parts(source):
    parser = _Parser(source)
    return _parts(parser.sequence())


def _format(setup, a, b):
    setup, a, b = simplify_moves(setup), simplify_moves(a), simplify_moves(b)
    if not a or not b: return None
    body = f'[{" ".join(a)}, {" ".join(b)}]'
    return f'[{" ".join(setup)}: {body}]' if setup else body


@lru_cache(maxsize=1)
def _known_forms():
    found = {}
    for _, _, notation in ALL_SUBMISSIONS:
        if notation.strip().casefold() in ('not found.', 'not found', ''): continue
        parts = _notation_parts(notation)
        if parts is None: continue
        setup, a, b = parts
        for left, right in ((a, b), (b, a)):
            expression = _format(setup, left, right)
            if expression is None: continue
            signature = execution_signature(parse_algorithm(expression).moves)
            if signature not in found or len(expression) < len(found[signature][0]):
                found[signature] = (expression, (setup, left, right))
    return found


def find_commutator(source, *, max_checks=5000, max_seconds=.45):
    original = parse_algorithm(source)
    target = execution_signature(original.moves)
    if not target: return None

    def verified(expression, method):
        if expression is None: return None
        candidate = parse_algorithm(expression)
        if (execution_signature(candidate.moves) == target
                and algorithm_states(candidate)[-1] == algorithm_states(original)[-1]):
            return CommutatorResult(expression, method)
        return None

    parts = _notation_parts(source)
    if parts is not None:
        return verified(_format(*parts), 'notation')
    known = _known_forms()
    if target in known:
        return verified(known[target][0], 'library')
    start = _normal_moves(target)
    if not 4 <= len(start) <= 80 or max_checks <= 0 or max_seconds <= 0: return None
    deadline, checks = time.perf_counter() + max_seconds, 0
    queue, seen, states = deque([(start, ())]), {target}, []

    def matches(moves, signature):
        nonlocal checks
        checks += 1
        return execution_signature(moves) == signature

    def exhausted():
        return checks >= max_checks or time.perf_counter() >= deadline

    while queue and len(states) < 64 and not exhausted():
        moves, setup = queue.popleft()
        signature = execution_signature(moves)
        states.append((moves, setup, signature))
        if signature in known:
            _, (prefix, a, b) = known[signature]
            result = verified(_format(setup + prefix, a, b), 'library')
            if result is not None: return result
        if len(moves) % 2 == 0:
            half = len(moves) // 2
            for split in range(1, half):
                a, b = moves[:split], moves[split:half]
                if matches(a + b + inverse_moves(a) + inverse_moves(b), signature):
                    result = verified(_format(setup, a, b), 'structure')
                    if result is not None: return result
        if len(setup) >= 6: continue
        children = []
        axes = {signature[0][0], signature[-1][0]}
        cost = (len(moves), sum(2 if m.endswith('2') else 1 for m in moves))
        for move in MOVES:
            if move_spec(move)[0] not in axes or exhausted(): continue
            core = execution_signature(inverse_moves((move,)) + moves + (move,))
            checks += 1
            if core in known:
                _, (prefix, a, b) = known[core]
                result = verified(_format(setup + (move,) + prefix, a, b), 'library')
                if result is not None: return result
            if not core or core in seen: continue
            candidate = _normal_moves(core)
            next_cost = (len(candidate), sum(2 if m.endswith('2') else 1 for m in candidate))
            if next_cost < cost:
                seen.add(core)
                children.append((next_cost, candidate, setup + (move,)))
        for _, moves, setup in sorted(children): queue.append((moves, setup))

    # Merging a half turn at an A/B boundary can hide an otherwise ordinary
    # commutator split. Try bounded partial-turn prefixes after quick peeling.
    def prefixes(moves):
        found = set()
        for length in range(1, min(10, len(moves)) + 1):
            prefix = moves[:length]
            base = prefix[-1].rstrip("2'")
            for last in (prefix[-1], base, base + "'", base + '2'):
                candidate = prefix[:-1] + (last,)
                if candidate not in found:
                    found.add(candidate)
                    yield candidate
    for moves, setup, signature in states:
        for a in prefixes(moves):
            if exhausted(): return None
            remainder = _normal_moves(execution_signature(inverse_moves(a) + moves))
            for b in prefixes(remainder):
                if exhausted(): return None
                if matches(a + b + inverse_moves(a) + inverse_moves(b), signature):
                    result = verified(_format(setup, a, b), 'structure')
                    if result is not None: return result
    return None
