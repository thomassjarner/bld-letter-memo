"""General algorithm effects, independent of a case or tracing buffer."""
from dataclasses import dataclass

from core.algorithms import algorithm_states, normalized_state, parse_algorithm, simplify_moves
from core.corner_cases import identify_case_state
from core.cube_definitions import CORNER_PIECES, EDGE_PIECES, find_piece_for_sticker
from core.tracer import _solved


@dataclass(frozen=True)
class AlgorithmEffect:
    moves: tuple
    corner_cycles: tuple
    edge_cycles: tuple
    twisted_in_place: tuple
    flipped_in_place: tuple
    affected_corners: tuple
    affected_edges: tuple
    sticker_changes: tuple
    ufr_case: str | None
    reorients_cube: bool


def analyze_algorithm(algorithm):
    if isinstance(algorithm, str): algorithm = parse_algorithm(algorithm)
    final = algorithm_states(algorithm)[-1]
    net = normalized_state(algorithm)
    solved = _solved()
    destinations = {home: solved[position] for position, home in net.items()}

    def category(pieces):
        permutation = {piece: find_piece_for_sticker(destinations[piece], pieces) for piece in pieces}
        affected = tuple(piece for piece, stickers in pieces.items() if any(destinations[s] != s for s in stickers))
        orientation_only = tuple(piece for piece in affected if permutation[piece] == piece)
        seen, cycles = set(), []
        for piece in pieces:
            if piece in seen or permutation[piece] == piece: continue
            cycle, current = [], piece
            while current not in seen:
                seen.add(current)
                cycle.append(current)
                current = permutation[current]
            cycles.append(tuple(cycle))
        return tuple(cycles), orientation_only, affected

    corner_cycles, twisted, corners = category(CORNER_PIECES)
    edge_cycles, flipped, edges = category(EDGE_PIECES)
    try: ufr_case = identify_case_state(net)
    except ValueError: ufr_case = None
    return AlgorithmEffect(simplify_moves(algorithm.moves), corner_cycles, edge_cycles,
        twisted, flipped, corners, edges,
        tuple((home, destinations[home]) for home in destinations if len(home) > 1 and destinations[home] != home),
        ufr_case, any(final[position] != home for position, home in solved.items() if len(home) == 1))
