"""Read-only commutator components and move-to-notation tracking."""
from dataclasses import dataclass
from functools import lru_cache

from core.algorithms import _Parser, inverse_moves, move_spec, parse_algorithm
from core.commutator_finder import execution_signature, find_commutator


@dataclass(frozen=True)
class NotationToken:
    text: str
    reference: int = -1


@dataclass(frozen=True)
class TrackedMove:
    move: str
    references: frozenset = frozenset()
    components: frozenset = frozenset()


@dataclass(frozen=True)
class Component:
    label: str
    start: int
    end: int


@dataclass(frozen=True)
class CommutatorStudy:
    tokens: tuple
    tracked: tuple
    components: tuple

    @property
    def source(self): return ''.join(t.text for t in self.tokens)

    @property
    def moves(self): return tuple(t.move for t in self.tracked)


def _structured(node):
    kind, parts = node
    if kind in ('comm', 'conj'): return True
    if kind == 'seq': return any(_structured(n) for n in parts)
    if kind == 'inverse': return _structured(parts)
    if kind == 'repeat': return _structured(parts[0])
    return False


@lru_cache(maxsize=256)
def commutator_study(source):
    """Retain written structure, or recover only execution-equivalent notation."""
    try:
        parsed = parse_algorithm(source)
        node = _Parser(source).sequence()
        if not _structured(node):
            found = find_commutator(source, max_checks=1500, max_seconds=.08)
            if found is None: return None
            node = _Parser(found.expression).sequence()
        tokens, references = [], {}

        def add(text, reference=-1): tokens.append(NotationToken(text, reference))

        def render(n, path=()):
            kind, parts = n
            if kind == 'move':
                reference = len(references)
                references[path] = reference
                add(parts, reference)
            elif kind == 'seq':
                for i, child in enumerate(parts):
                    if i: add(' ')
                    render(child, path + (i,))
            elif kind in ('comm', 'conj'):
                add('['); render(parts[0], path + (0,))
                add(', ' if kind == 'comm' else ': ')
                render(parts[1], path + (1,)); add(']')
            elif kind == 'inverse':
                add('('); render(parts, path + (0,)); add(")'")
            else:
                add('('); render(parts[0], path + (0,)); add(')' + str(parts[1]))

        def undo(items):
            return tuple(TrackedMove(inverse_moves((m.move,))[0], m.references) for m in reversed(items))

        def items(n, path):
            kind, parts = n
            if kind == 'move': return (TrackedMove(parts, frozenset((references[path],))),)
            if kind == 'seq': return tuple(m for i, child in enumerate(parts) for m in items(child, path + (i,)))
            if kind == 'inverse': return undo(items(parts, path + (0,)))
            if kind == 'repeat': return items(parts[0], path + (0,)) * parts[1]
            a, b = items(parts[0], path + (0,)), items(parts[1], path + (1,))
            return a + b + undo(a) + (undo(b) if kind == 'comm' else ())

        def sections(n, path=()):
            kind, parts = n
            if kind == 'conj':
                a = items(parts[0], path + (0,))
                return [('Setup', a)] + sections(parts[1], path + (1,)) + [('Undo setup', undo(a))]
            if kind == 'comm':
                a, b = items(parts[0], path + (0,)), items(parts[1], path + (1,))
                return [('A', a), ('B', b), ('Undo A', undo(a)), ('Undo B', undo(b))]
            if kind == 'inverse':
                return [((label[5:6].upper() + label[6:]) if label.startswith('Undo ') else
                         'Undo setup' + label[5:] if label.startswith('Setup') else 'Undo ' + label, undo(m))
                        for label, m in reversed(sections(parts, path + (0,)))]
            if kind == 'repeat':
                return [(f'{label} · {i + 1}/{parts[1]}', m) for i in range(parts[1])
                        for label, m in sections(parts[0], path + (0,))]
            if kind == 'seq' and _structured(n):
                result, pending = [], ()
                for i, child in enumerate(parts):
                    if _structured(child):
                        if pending: result.append(('Moves', pending)); pending = ()
                        result.extend(sections(child, path + (i,)))
                    else: pending += items(child, path + (i,))
                if pending: result.append(('Moves', pending))
                return result
            return [('Algorithm', items(n, path))]

        render(node)
        tracked, components = [], []
        for label, moves in sections(node):
            if not moves: continue
            index, start = len(components), len(tracked)
            tracked.extend(TrackedMove(m.move, m.references, frozenset((index,))) for m in moves)
            components.append(Component(label, start, len(tracked)))
        study = CommutatorStudy(tuple(tokens), tuple(tracked), tuple(components))
        if execution_signature(study.moves) != execution_signature(parsed.moves): return None
        return study
    except (ValueError, KeyError):
        return None


def _clean_tracking(tracked):
    """Carry token ownership through the existing same-axis move cleanup."""
    result = []
    for item in tracked:
        base, axis = item.move.rstrip("2'"), move_spec(item.move)[0]
        amount = 2 if item.move.endswith('2') else 3 if item.move.endswith("'") else 1
        for index in range(len(result) - 1, -1, -1):
            previous, count, previous_axis, refs, comps = result[index]
            if previous_axis != axis: break
            if previous == base:
                count = (count + amount) % 4
                if count: result[index] = (base, count, axis, refs | item.references, comps | item.components)
                else: result.pop(index)
                break
        else:
            result.append((base, amount, axis, item.references, item.components)); continue
        if previous_axis != axis: result.append((base, amount, axis, item.references, item.components))
    return tuple(TrackedMove(base + ('2' if count == 2 else "'" if count == 3 else ''), refs, comps)
                 for base, count, axis, refs, comps in result)


def _axis_groups(tracked):
    groups = []
    for item in tracked:
        axis, layers, quarter = move_spec(item.move)
        vector = tuple(quarter % 4 if layer in layers else 0 for layer in (-1, 0, 1))
        refs, comps = item.references, item.components
        if groups and groups[-1][0] == axis:
            _, old, old_refs, old_comps = groups.pop()
            vector = tuple((a + b) % 4 for a, b in zip(vector, old))
            refs, comps = refs | old_refs, comps | old_comps
        if any(vector): groups.append((axis, vector, refs, comps))
    return groups


def align_notation(study, moves):
    """Track exact leaves, or all contributors to a combined same-axis turn."""
    moves = tuple(moves)
    if study is None or execution_signature(study.moves) != execution_signature(moves): return None
    if moves == study.moves: return study.tracked
    cleaned = _clean_tracking(study.tracked)
    if moves == tuple(m.move for m in cleaned): return cleaned
    source = _axis_groups(study.tracked)
    target = _axis_groups(tuple(TrackedMove(m, frozenset((i,))) for i, m in enumerate(moves)))
    if len(source) != len(target): return None
    result = [TrackedMove(m) for m in moves]
    for a, b in zip(source, target):
        if a[:2] != b[:2]: return None
        for index in b[2]: result[index] = TrackedMove(moves[index], a[2], a[3])
    return tuple(result)
