"""Presentation-only grouping of consecutive, disjoint opposite-face turns."""
from dataclasses import dataclass


def can_turn_together(first, second):
    # Wide turns, slices and rotations deliberately retain individual playback.
    bases = first.rstrip("2'"), second.rstrip("2'")
    return len(bases[0]) == len(bases[1]) == 1 and frozenset(bases) in (
        frozenset('UD'), frozenset('RL'), frozenset('FB'))


@dataclass(frozen=True)
class PlaybackStep:
    start: int
    end: int
    moves: tuple[str, ...]

    @property
    def caption(self):
        text = ' '.join(self.moves)
        return '(' + text + ')' if len(self.moves) > 1 else text


def playback_steps(algorithm, simultaneous=False):
    """Keep the original atomic move indices and all explicit stage boundaries."""
    boundaries = {edge for stage in algorithm.stages for edge in (stage.start, stage.end)}
    steps, index = [], 0
    while index < len(algorithm.moves):
        count = 1
        if (simultaneous and index + 1 < len(algorithm.moves)
                and index + 1 not in boundaries
                and can_turn_together(algorithm.moves[index], algorithm.moves[index + 1])):
            count = 2
        steps.append(PlaybackStep(index, index + count, algorithm.moves[index:index + count]))
        index += count
    return tuple(steps)
