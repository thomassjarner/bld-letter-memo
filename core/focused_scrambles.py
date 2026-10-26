"""Legal category scrambles in the scheme's memo frame, with 3-style parity.

The web runtime solves uniformly sampled restricted states with a bundled
solver. Native Python uses Node when available. Without a JavaScript runtime,
random conjugated pure cycles provide a legal, longer construction fallback.
No network access or extra Python dependency is needed for generation.
"""
from __future__ import annotations

from collections import deque
from functools import lru_cache

from core.cube_definitions import EDGE_PIECES, EDGE_STICKER_ORDER, face_groups, find_piece_for_sticker
from core.tracer import COLOR_FACE, VEC, _apply, _at, _solved, simulate


SOLVED = ''.join(face * 9 for face in 'URFDLB')
CORNER_FACELETS = ((8, 9, 20), (6, 18, 38), (0, 36, 47), (2, 45, 11),
                   (29, 26, 15), (27, 44, 24), (33, 53, 42), (35, 17, 51))
EDGE_FACELETS = ((5, 10), (7, 19), (3, 37), (1, 46), (32, 16), (28, 25),
                 (30, 43), (34, 52), (23, 12), (21, 41), (50, 39), (48, 14))
EDGE_NAMES = ('UR', 'UF', 'UL', 'UB', 'DR', 'DF', 'DL', 'DB', 'FR', 'FL', 'BL', 'BR')
MOVES = tuple(face + suffix for face in 'URFDLB' for suffix in ('', "'", '2'))
PURE_CYCLES = {
    'corners': "R U' L' U R' U' L U",
    'edges': "R2 U R U R' U' R' U' R' U R'",
}
PARITY = "R U R' U' R' F R2 U' R' U' R U R' F'"  # UR/UL edge swap
_web_solver = None


def permutation_parity(permutation):
    return sum(a > b for i, a in enumerate(permutation) for b in permutation[i + 1:]) % 2


def parity_edges(scheme):
    buffer = scheme.edges.buffer_sticker or scheme.edges.buffer_piece
    piece = find_piece_for_sticker(buffer, EDGE_PIECES) if buffer else None
    helper = scheme.edge_parity_partner or 'UR'
    if piece is None or helper not in EDGE_PIECES or piece == helper:
        raise ValueError('For 3-style corner practice, choose an edge buffer and a different parity helper edge in Letter Schemes.')
    return piece, helper


def sample_state(category, rng, scheme=None):
    """Sample a legal restricted state and return (facelets, odd corners)."""
    if category not in PURE_CYCLES:
        raise ValueError('Unknown focused scramble category')
    three_style = category == 'corners' and scheme is not None and scheme.three_style_enabled
    pair = parity_edges(scheme) if three_style else None
    odd = bool(rng.randrange(2)) if three_style else False
    cp, ep = list(range(8)), list(range(12))
    co, eo = [0] * 8, [0] * 12
    permutation = ep if category == 'edges' else cp
    rng.shuffle(permutation)
    if permutation_parity(permutation) != int(odd):
        permutation[0], permutation[1] = permutation[1], permutation[0]
    orientations, base = (eo, 2) if category == 'edges' else (co, 3)
    for i in range(len(orientations) - 1):
        orientations[i] = rng.randrange(base)
    orientations[-1] = -sum(orientations[:-1]) % base
    if odd:
        a, b = (EDGE_NAMES.index(piece) for piece in pair)
        ep[a], ep[b] = ep[b], ep[a]
    facelets = list(SOLVED)
    for positions, permutation, orientations in ((CORNER_FACELETS, cp, co), (EDGE_FACELETS, ep, eo)):
        size = len(positions[0])
        for slot, home in enumerate(permutation):
            for n in range(size):
                facelets[positions[slot][(n + orientations[slot]) % size]] = SOLVED[positions[home][n]]
    return ''.join(facelets), odd


def inverse(algorithm):
    return ' '.join(move if move.endswith('2') else move[0] if move.endswith("'") else move + "'"
                    for move in reversed(algorithm.split()))


@lru_cache(maxsize=1)
def facelet_positions():
    corners, edges = dict(face_groups('corners')), dict(face_groups('edges'))
    return tuple(sticker for face in 'URFDLB' for sticker in (
        corners[face][0], edges[face][0], corners[face][1], edges[face][3], face,
        edges[face][1], corners[face][3], edges[face][2], corners[face][2]))


def state_facelets(state):
    return ''.join(_at(state, position)[0] for position in facelet_positions())


def solve_facelets(facelets):
    """Return a solution from the bundled JS solver, or None for native fallback."""
    from core.vendor.min2phase_source import JS_SOURCE
    try:
        from pyodide.code import run_js
    except ImportError:
        import shutil
        import subprocess
        node = shutil.which('node')
        if node is None:
            return None
        try:
            result = subprocess.run(
                [node, '-e', JS_SOURCE + '\nprocess.stdout.write(min2phase.solve(process.argv[1]));', facelets],
                capture_output=True, text=True, timeout=12, check=True,
            )
            return result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    global _web_solver
    if _web_solver is None:
        _web_solver = run_js('(function(){\n' + JS_SOURCE + '\nreturn min2phase;})()')
    return str(_web_solver.solve(facelets)).strip()


@lru_cache(maxsize=132)
def parity_algorithm(buffer, helper):
    """Conjugate the UR/UL swap onto the configured *oriented* edge pair."""
    # Track the two target stickers through setup moves. Matching their exact
    # orientation ensures the resulting swap cancels the tracer's memo swap.
    transitions = {}
    for move in MOVES:
        state = _apply(_solved(), move)
        transitions[move] = {_at(state, position): position for position in EDGE_STICKER_ORDER}
    queue = deque([((buffer, helper), ())])
    seen = {(buffer, helper)}
    while queue:
        pair, setup = queue.popleft()
        if pair == ('UR', 'UL'):
            sequence = ' '.join(setup)
            return ' '.join(part for part in (sequence, PARITY, inverse(sequence)) if part)
        for move, mapping in transitions.items():
            target = tuple(mapping[sticker] for sticker in pair)
            if target not in seen:
                seen.add(target)
                queue.append((target, setup + (move,)))
    raise ValueError('Could not construct the configured parity edge swap')


def constructed_scramble(category, rng, odd=False, scheme=None):
    """Portable fallback: conjugated pure cycles preserve the other category."""
    parts = []
    for _ in range(rng.randint(5, 8)):
        setup = []
        for _ in range(rng.randint(2, 5)):
            setup.append(rng.choice([m for m in MOVES if not setup or m[0] != setup[-1][0]]))
        sequence = ' '.join(setup)
        cycle = PURE_CYCLES[category]
        if rng.randrange(2):
            cycle = inverse(cycle)
        parts.extend((sequence, cycle, inverse(sequence)))
    if odd:
        parts.append(parity_algorithm(*parity_edges(scheme)))
    # Cancel adjacent turns of the same face without changing the state.
    simplified = []
    for move in ' '.join(parts).split():
        amount = 2 if move.endswith('2') else 3 if move.endswith("'") else 1
        if simplified and simplified[-1][0] == move[0]:
            _, previous = simplified.pop()
            amount = (amount + previous) % 4
        if amount:
            simplified.append((move[0], amount))
    return ' '.join(face + ('', '', '2', "'")[amount] for face, amount in simplified)


def in_scramble_frame(algorithm, scheme=None):
    if scheme is None or scheme.scramble_from_own_orientation:
        return algorithm
    up, front = COLOR_FACE.get(scheme.memo_up), COLOR_FACE.get(scheme.memo_front)
    if up is None or front is None or sum(a * b for a, b in zip(VEC[up], VEC[front])) != 0:
        raise ValueError('Choose adjacent top and front colors in Letter Schemes.')
    u, f = VEC[up], VEC[front]
    right = (u[1] * f[2] - u[2] * f[1], u[2] * f[0] - u[0] * f[2], u[0] * f[1] - u[1] * f[0])
    opposite = {'U': 'D', 'D': 'U', 'R': 'L', 'L': 'R', 'F': 'B', 'B': 'F'}
    r = next(face for face, vector in VEC.items() if vector == right)
    mapping = {'U': up, 'D': opposite[up], 'F': front, 'B': opposite[front], 'R': r, 'L': opposite[r]}
    return ' '.join(mapping[move[0]] + move[1:] for move in algorithm.split())


def generate_focused(category, rng, scheme=None):
    for _ in range(5):
        facelets, odd = sample_state(category, rng, scheme)
        if facelets == SOLVED:
            continue
        try:
            solution = solve_facelets(facelets)
        except Exception:
            # A legal constructive scramble is preferable to breaking timing
            # when a browser cannot initialize the optional shortening engine.
            solution = None
        if solution and all(move in MOVES for move in solution.split()):
            scramble = inverse(solution)
            if state_facelets(simulate(scramble)) == facelets:
                return in_scramble_frame(scramble, scheme)
        scramble = constructed_scramble(category, rng, odd, scheme)
        if scramble and state_facelets(simulate(scramble)) != SOLVED:
            return in_scramble_frame(scramble, scheme)
    raise ValueError('Could not generate a focused scramble. Try again.')
