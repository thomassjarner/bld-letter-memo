"""Execution-equivalent notation and compact statistics for walkthrough cards."""
from functools import lru_cache

from core.algorithms import parse_algorithm
from core.commutator_finder import execution_signature, find_commutator, has_commutator_structure


@lru_cache(maxsize=256)
def step_commutator(step):
    # Reuse the selected algorithm's structure before attempting bounded
    # recovery. Never substitute another algorithm that only has the same effect.
    if len(step.parts) == 1:
        part = step.parts[0]
        if not part.orientation_reset:
            recovered = (part.source if has_commutator_structure(part.source) else
                         _recover(part.source))
            if recovered:
                expression = f'[{" ".join(part.setup)}: {recovered}]' if part.setup else recovered
                try:
                    if execution_signature(parse_algorithm(expression).moves) == execution_signature(step.moves):
                        return expression
                except ValueError:
                    pass  # A buffer setup can put the combined form over parser bounds.
    return _recover(' '.join(step.moves))


@lru_cache(maxsize=512)
def _recover(source):
    try:
        result = find_commutator(source, max_checks=1500, max_seconds=.08)
    except ValueError:
        return None
    return result.expression if result else None


def move_statistics(moves):
    turns = tuple(move for move in moves if move[0] not in 'xyz')
    return len(turns), sum(2 if move.endswith('2') else 1 for move in turns), len(moves) - len(turns)
