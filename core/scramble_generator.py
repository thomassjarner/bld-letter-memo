"""Scramble generation for practice.

The current desktop build has no cube-solving dependency bundled, so this
module produces long competition-style random-move scrambles while avoiding
same-face / same-axis redundancies.  It is deliberately isolated behind one
class so a true uniform random-state generator can replace it without changing
the Practice UI or saved solve format.
"""
from __future__ import annotations

import random


class ScrambleGenerator:
    FACES = ("U", "D", "L", "R", "F", "B")
    AXIS = {"U": "UD", "D": "UD", "L": "LR", "R": "LR", "F": "FB", "B": "FB"}
    SUFFIXES = ("", "'", "2")

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.SystemRandom()

    def generate(self, length: int = 22, add_bld_orientation: bool = True) -> str:
        moves: list[str] = []
        last_face = None
        last_axis = None
        same_axis_run = 0

        for _ in range(length):
            candidates = []
            for face in self.FACES:
                if face == last_face:
                    continue
                axis = self.AXIS[face]
                # Avoid three consecutive moves on the same axis. Two can occur
                # (e.g. R L2), matching normal-looking competition scrambles.
                if axis == last_axis and same_axis_run >= 2:
                    continue
                candidates.append(face)

            face = self.rng.choice(candidates)
            axis = self.AXIS[face]
            if axis == last_axis:
                same_axis_run += 1
            else:
                last_axis = axis
                same_axis_run = 1
            last_face = face
            moves.append(face + self.rng.choice(self.SUFFIXES))

        if add_bld_orientation:
            # BLD scrambles commonly end with wide turns that randomize the
            # physical orientation. Keep these separate at the end so the
            # existing memo-orientation logic can handle them naturally.
            orientation_endings = (
                (), ("Rw",), ("Rw'",), ("Rw2",),
                ("Uw",), ("Uw'",), ("Uw2",),
                ("Fw",), ("Fw'",), ("Fw2",),
                ("Rw", "Uw"), ("Rw'", "Uw"), ("Rw", "Uw'"),
                ("Fw", "Uw"), ("Fw'", "Uw'"),
            )
            moves.extend(self.rng.choice(orientation_endings))

        return " ".join(moves)
