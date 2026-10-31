"""Verified, read-only corner execution plans using the existing tracer/library."""
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache

from core.algorithms import Algorithm, Stage, apply_move, inverse_moves, inverse_state, parse_algorithm, simplify_moves
from core.corner_algorithms import builtin_algorithms
from core.cube_definitions import CORNER_PIECES, CORNER_STICKER_ORDER, EDGE_PIECES, EDGE_STICKER_ORDER, find_piece_for_sticker
from core.tracer import (TraceResult, STANDARD_CORNER_PRIORITY, STANDARD_CORNER_STICKER,
                         _at, _key, _memo_swap_edge_identities, _physical_correct, _solved, _trace_category, simulate)
from data.models import LetterScheme

MAX_WALKTHROUGH_MOVES = 2400
SOLVED = _solved()


def apply_moves(state, moves):
    for move in moves:
        state = apply_move(state, move)
    return state


@dataclass(frozen=True)
class Rotation:
    moves: tuple
    state: dict
    positions: dict
    stickers: dict


@lru_cache(maxsize=1)
def rotations():
    queue, seen, result = deque([((), SOLVED)]), set(), []
    while queue:
        moves, state = queue.popleft()
        signature = tuple(_at(state, face) for face in 'ULFRBD')
        if signature in seen: continue
        seen.add(signature)
        result.append(Rotation(moves, state,
            {_key(home): position for position, home in state.items()},
            {home: SOLVED[position] for position, home in state.items()}))
        for face in 'xyz':
            for suffix in ('', "'", '2'):
                move = face + suffix
                queue.append((moves + (move,), apply_move(state, move)))
    return tuple(result)


@lru_cache(maxsize=576)
def _shot_positions(buffer, target):
    if set(buffer) == set(target):
        raise ValueError('A target must be outside the physical buffer piece.')
    rotation = next(r for r in rotations() if r.stickers[buffer] == target)
    reverse = {destination: source for source, destination in rotation.positions.items()}
    bp, tp = _key(buffer)[0], _key(target)[0]
    return {position: rotation.positions[position] if position[0] == bp else
            reverse[position] if position[0] == tp else position for position in SOLVED}


def corner_shot(state, buffer, target):
    """Oriented virtual two-corner swap, used only to verify paired execution."""
    positions = _shot_positions(buffer, target)
    return {positions[position]: home for position, home in state.items()}


def _pair_effect(buffer, first, second):
    return corner_shot(corner_shot(SOLVED, buffer, first), buffer, second)


@lru_cache(maxsize=2048)
def _normalized_execution(source):
    algorithm = parse_algorithm(source)
    end = apply_moves(SOLVED, algorithm.moves)
    centers = tuple(_at(end, face) for face in 'ULFRBD')
    frame = next(r for r in rotations() if tuple(_at(r.state, f) for f in 'ULFRBD') == centers)
    reset = inverse_moves(frame.moves)
    moves = simplify_moves(algorithm.moves + reset)
    return moves, apply_moves(end, reset), reset


@dataclass(frozen=True)
class AlgorithmPart:
    case_id: str
    name: str
    source: str
    algorithm_id: str
    setup: tuple
    orientation_reset: tuple


@dataclass(frozen=True)
class CornerStep:
    first: str
    second: str
    letters: str
    moves: tuple
    parts: tuple[AlgorithmPart, ...]
    start: int
    end: int
    correction: bool = False


@dataclass(frozen=True)
class CornerPlan:
    scramble: str
    scheme_name: str
    scheme_snapshot: dict
    buffer: str
    trace: TraceResult
    initial: dict
    final: dict
    steps: tuple[CornerStep, ...]
    algorithm: Algorithm
    parity_target: str | None
    warnings: tuple[str, ...]
    remaining_twists: tuple[str, ...] = ()


def target_letter(scheme, sticker):
    value = scheme.corners.stickers.get(sticker, '')
    return value if value and value != 'BUFFER' else '?'


def build_corner_plan(scramble, scheme, records=None, corner_cycle_break_overrides=None):
    if scheme is None:
        raise ValueError('Choose a letter scheme first.')
    buffer = scheme.corners.buffer_sticker or scheme.corners.buffer_piece
    if buffer not in CORNER_STICKER_ORDER:
        raise ValueError('Set a valid corner buffer in Letter Schemes first.')
    snapshot = deepcopy(scheme.to_dict())
    initial = simulate(scramble, scheme.memo_up, scheme.memo_front, scheme.scramble_from_own_orientation)
    # Reuse the exact corner tracer, without requiring any edge buffer or
    # applying the virtual edge memo parity swap to the physical cube.
    targets, orientation, cycles, flags, breaks = _trace_category(initial, scheme.corners,
        CORNER_STICKER_ORDER, CORNER_PIECES, STANDARD_CORNER_PRIORITY, STANDARD_CORNER_STICKER,
        corner_cycle_break_overrides)
    letters = [target_letter(scheme, target) for target in targets]
    trace = TraceResult(targets, [], letters, [],
        [''.join(letters[i:i + 2]) for i in range(0, len(letters), 2)], [],
        corner_orientation=orientation, corner_cycle_ids=cycles,
        corner_orientation_target_flags=flags, corner_cycle_breaks=breaks)
    frame = next(r for r in rotations() if r.stickers[buffer] == 'UFR')
    records, warnings, steps, all_moves, stages = records or {}, [], [], [], []

    def resolve_distinct(first, second):
        a, b = frame.stickers[first], frame.stickers[second]
        key = a + ':' + b
        builtins = builtin_algorithms(key)
        record = records.get(key)
        preferred = record.preferred_algorithm if record else ''
        personal = next((alg for alg in record.algorithms if alg.id == preferred), None) if record else None
        selected = personal or next((alg for alg in builtins if alg.id == preferred), builtins[0])
        candidates = [selected] + ([builtins[0]] if selected is not builtins[0] else [])
        for candidate in candidates:
            try:
                moves, effect, reset = _normalized_execution(candidate.alg)
                if effect != _pair_effect('UFR', a, b):
                    raise ValueError('Wrong corner effect')
                result = simplify_moves(frame.moves + moves + inverse_moves(frame.moves))
                if apply_moves(SOLVED, result) != _pair_effect(buffer, first, second):
                    raise ValueError('Wrong buffer setup')
                part = AlgorithmPart(key, candidate.name, candidate.alg, candidate.id, frame.moves, reset)
                return result, (part,)
            except (ValueError, StopIteration):
                warnings.append(f'{key.replace(":", " / ")}: saved choice could not be verified; using the built-in recommendation.')
        raise ValueError('Could not verify an algorithm for ' + first + ' / ' + second)

    current = initial
    def add_pair(first, second):
        nonlocal current
        if first == second: return
        if set(first) == set(second):
            raise ValueError('Twist targets cannot be used as a permutation pair.')
        moves, parts = resolve_distinct(first, second)
        if len(all_moves) + len(moves) > MAX_WALKTHROUGH_MOVES:
            raise ValueError('This walkthrough exceeds 2400 moves. Choose shorter case algorithms first.')
        letters = target_letter(scheme, first) + target_letter(scheme, second)
        start = len(all_moves)
        all_moves.extend(moves)
        step = CornerStep(first, second, letters, moves, parts, start, len(all_moves))
        steps.append(step)
        label = f'{len(steps)} · {letters if "?" not in letters else first + " / " + second}'
        stages.append(Stage(label, start, len(all_moves)))
        current = apply_moves(current, moves)

    # Orientation targets are deliberately omitted before pairing. With odd
    # permutation parity, pairing the final permutation target with a twist
    # target would execute a different case and reserve the wrong parity shot.
    targets = [target for target, orientation_target in zip(trace.corner_targets, flags)
               if not orientation_target]
    parity = targets[-1] if len(targets) % 2 else None
    for i in range(0, len(targets) - 1, 2): add_pair(targets[i], targets[i + 1])

    # Verify permutation against the reserved parity shot, but leave all
    # residual orientation alone. No twist algorithms are synthesized.
    expected = corner_shot(SOLVED, buffer, parity) if parity else SOLVED
    reverse = inverse_state(expected)
    delta = dict(SOLVED)
    for sticker in CORNER_STICKER_ORDER:
        position = _key(sticker)
        delta[position] = reverse[_key(current[position])]
    if not all(_physical_correct(delta, piece, CORNER_STICKER_ORDER) for piece in CORNER_PIECES):
        raise ValueError('The corner target sequence could not be verified.')
    twists = tuple(piece for piece, stickers in CORNER_PIECES.items()
                   if any(_at(delta, sticker) != sticker for sticker in stickers))
    if any(_at(current, s) != _at(initial, s) for s in EDGE_STICKER_ORDER + list('ULFRBD')):
        raise ValueError('The corner algorithms unexpectedly changed edges or centers.')
    moves = tuple(all_moves)
    algorithm = Algorithm(' '.join(moves), moves, tuple(stages))
    return CornerPlan(scramble.strip(), scheme.name, snapshot, buffer, trace, initial, current,
                      tuple(steps), algorithm, parity, tuple(dict.fromkeys(warnings)), twists)


def edge_parity_pair(scheme):
    """Display parity at UF; the tracing buffer is deliberately independent."""
    helper = find_piece_for_sticker(scheme.edge_parity_partner or 'UR', EDGE_PIECES)
    # UF cannot be swapped with itself. Keep a legal preview even when the
    # chosen tracing helper is UF or an older import contains an invalid value.
    return 'UF', helper if helper and helper != 'UF' else 'UR'


def walkthrough_initial(plan, edge_view='scrambled'):
    """A display-only state; never modify the scramble or the saved scheme."""
    initial = dict(plan.initial)
    if edge_view == 'solved':
        for position, home in SOLVED.items():
            if len(home) == 2: initial[position] = home
        scheme = LetterScheme.from_dict(plan.scheme_name, plan.scheme_snapshot)
        pair = edge_parity_pair(scheme)
        if plan.parity_target and pair:
            initial = _memo_swap_edge_identities(initial, *pair)
    return initial
