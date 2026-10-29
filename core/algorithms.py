"""Bounded algorithm notation and sticker simulation for learning tools.

The scramble tracer retains its original parser and behavior. This engine
adds slices, rotations, lowercase/wide turns and structured alg notation.
"""
from dataclasses import dataclass
import re

from core.tracer import MOVES, _at, _key, _orient, _rot, _solved

MAX_MOVES = 600
MAX_INPUT = 8000


def inverse_moves(moves):
    return tuple(m if m.endswith('2') else m[:-1] if m.endswith("'") else m + "'"
                 for m in reversed(moves))


def move_spec(move):
    face = move[0]
    amount = 2 if move.endswith('2') else -1 if move.endswith("'") else 1
    if face in MOVES:
        axis, layer, direction = MOVES[face]
        layers = (layer, 0) if 'w' in move else (layer,)
    elif face in 'MES':
        axis, direction = {'M': ('x', 1), 'E': ('y', 1), 'S': ('z', -1)}[face]
        layers = (0,)
    else:
        axis, direction = {'x': ('x', -1), 'y': ('y', -1), 'z': ('z', -1)}[face]
        layers = (-1, 0, 1)
    return axis, layers, direction * amount


def apply_move(state, move):
    axis, layers, quarter = move_spec(move)
    index = 'xyz'.index(axis)
    return {(_rot(p, axis, quarter), _rot(n, axis, quarter)) if p[index] in layers else (p, n): home
            for (p, n), home in state.items()}


@dataclass(frozen=True)
class Stage:
    label: str
    start: int
    end: int


@dataclass(frozen=True)
class Algorithm:
    source: str
    moves: tuple[str, ...]
    stages: tuple[Stage, ...]

    @property
    def expanded(self):
        return ' '.join(self.moves)


def _expand(node):
    kind, parts = node
    if kind == 'move':
        return (parts,)
    if kind == 'seq':
        result = ()
        for child in parts:
            result += _expand(child)
            if len(result) > MAX_MOVES:
                raise ValueError(f'Use at most {MAX_MOVES} expanded moves.')
        return result
    if kind == 'inverse':
        return inverse_moves(_expand(parts))
    if kind == 'repeat':
        child, count = parts
        moves = _expand(child)
        if len(moves) * count > MAX_MOVES:
            raise ValueError(f'Use at most {MAX_MOVES} expanded moves.')
        return moves * count
    a, b = (_expand(child) for child in parts)
    result = a + b + inverse_moves(a)
    if kind == 'comm':
        result += inverse_moves(b)
    if len(result) > MAX_MOVES:
        raise ValueError(f'Use at most {MAX_MOVES} expanded moves.')
    return result


class _Parser:
    def __init__(self, source):
        self.text = re.sub(r'//[^\n]*', '', source).replace('’', "'").replace('′', "'")
        self.index = 0

    def space(self):
        while self.index < len(self.text) and self.text[self.index].isspace():
            self.index += 1

    def sequence(self, stops='', depth=0):
        if depth > 16:
            raise ValueError('Algorithm groups are nested too deeply.')
        children = []
        while True:
            self.space()
            if self.index == len(self.text) or self.text[self.index] in stops:
                break
            char = self.text[self.index]
            self.index += 1
            if char in '([':
                left = self.sequence(')' if char == '(' else ',:]', depth + 1)
                if self.index >= len(self.text):
                    raise ValueError('Close every algorithm group.')
                separator = self.text[self.index]
                self.index += 1
                if char == '(':
                    node = left
                else:
                    if separator not in ',:':
                        raise ValueError('Use [A, B] or [setup: algorithm].')
                    right = self.sequence(']', depth + 1)
                    if self.index >= len(self.text) or self.text[self.index] != ']':
                        raise ValueError('Close every algorithm group.')
                    self.index += 1
                    if not _expand(left) or not _expand(right):
                        raise ValueError('Both parts of a commutator/setup must contain moves.')
                    node = ('comm' if separator == ',' else 'conj', (left, right))
                # Group repetition and inverse suffixes, without expanding a
                # large repetition before checking its size.
                if self.index < len(self.text) and self.text[self.index].isdigit():
                    end = self.index
                    while end < len(self.text) and self.text[end].isdigit():
                        end += 1
                    digits = self.text[self.index:end]
                    if len(digits) > 4:
                        raise ValueError(f'Use at most {MAX_MOVES} expanded moves.')
                    node = ('repeat', (node, int(digits)))
                    self.index = end
                if self.index < len(self.text) and self.text[self.index] == "'":
                    node = ('inverse', node)
                    self.index += 1
            elif char == ':' and children:
                # Also accept setup:[A,B], the common shorthand used by the
                # supplied alg sheet. Colons belonging to [setup: alg] are
                # already consumed by that group's separator handling.
                left = children[0] if len(children) == 1 else ('seq', tuple(children))
                right = self.sequence(stops, depth + 1)
                if not _expand(left) or not _expand(right):
                    raise ValueError('Both parts of a setup must contain moves.')
                return ('conj', (left, right))
            elif char in 'URFDLBurfdlbMESxyz':
                move = char.upper() + 'w' if char in 'urfdlb' else char
                if self.index < len(self.text) and self.text[self.index] == 'w':
                    if char not in 'URFDLB':
                        raise ValueError('Use w only after a face turn, such as Rw.')
                    move += 'w'
                    self.index += 1
                if self.index < len(self.text) and self.text[self.index] in "2'":
                    suffix = self.text[self.index]
                    move += suffix
                    self.index += 1
                    if suffix == '2' and self.index < len(self.text) and self.text[self.index] == "'":
                        self.index += 1
                node = ('move', move)
            else:
                raise ValueError(f'Unexpected notation: {char}. Use face/slice/rotation moves, (groups), or [A, B].')
            children.append(node)
            if len(children) > MAX_MOVES:
                raise ValueError(f'Use at most {MAX_MOVES} expanded moves.')
        return children[0] if len(children) == 1 else ('seq', tuple(children))


def parse_algorithm(source):
    if not isinstance(source, str) or len(source) > MAX_INPUT:
        raise ValueError(f'Use at most {MAX_INPUT} characters.')
    parser = _Parser(source)
    node = parser.sequence()
    parser.space()
    if parser.index != len(parser.text):
        raise ValueError('Unexpected closing group.')
    moves = _expand(node)
    if not moves:
        raise ValueError('Enter an algorithm first.')
    if len(moves) > MAX_MOVES:
        raise ValueError(f'Use at most {MAX_MOVES} expanded moves.')
    setup, core = (), node
    if node[0] == 'conj':
        setup, core = _expand(node[1][0]), node[1][1]
    sections = [('Setup', setup)] if setup else []
    if core[0] == 'comm':
        a, b = (_expand(child) for child in core[1])
        sections += [('A', a), ('B', b), ('Undo A', inverse_moves(a)), ('Undo B', inverse_moves(b))]
    else:
        sections += [('Algorithm', _expand(core))]
    if setup:
        sections.append(('Undo setup', inverse_moves(setup)))
    stages, index = [], 0
    for label, section in sections:
        if section:
            stages.append(Stage(label, index, index + len(section)))
            index += len(section)
    return Algorithm(source.strip(), moves, tuple(stages))


def algorithm_states(algorithm, initial=None):
    states = [dict(_solved() if initial is None else initial)]
    for move in algorithm.moves:
        states.append(apply_move(states[-1], move))
    return states


def normalized_state(algorithm):
    return _orient(algorithm_states(algorithm)[-1], 'W', 'G')


def inverse_state(state):
    solved = _solved()
    return {_key(home): solved[position] for position, home in state.items()}


def changed_stickers(state):
    return tuple(home for position, home in _solved().items() if state[position] != home)
