"""Conservative bracket assistance for the commutator text field only.

Offsets here are Python string indexes. The Flet adapter converts UTF-16
selection offsets at the boundary. No moves, parser rules or saved data change.
"""
from dataclasses import dataclass
import re

from core.algorithms import MAX_INPUT, parse_algorithm


PAIRS = {'[': ']', '(': ')'}
CLOSERS = {value: key for key, value in PAIRS.items()}


def _visible(text):
    # Keep indexes stable while excluding // comments from delimiter scanning.
    return re.sub(r'//[^\n]*', lambda match: ' ' * len(match.group()), text)


def empty_commutator(text):
    return not re.sub(r'[\[\]()\s]', '', _visible(text or ''))


def contains_square_bracket(text):
    return '[' in _visible(text)


def utf16_to_index(text, offset):
    if offset is None or offset < 0:
        return None
    units = 0
    for index, char in enumerate(text):
        width = 2 if ord(char) > 0xFFFF else 1
        if units + width > offset:
            return index
        units += width
    return len(text)


def index_to_utf16(text, index):
    return len(text[:max(0, min(len(text), index))].encode('utf-16-le', errors='surrogatepass')) // 2


@dataclass(frozen=True)
class BracketEdit:
    text: str
    selection: tuple[int, int] | None = None


def _difference(old, new, caret=None):
    start = 0
    while start < min(len(old), len(new)) and old[start] == new[start]:
        start += 1
    end = 0
    while end < min(len(old) - start, len(new) - start) and old[-1 - end] == new[-1 - end]:
        end += 1
    stop = len(old) - end
    inserted = new[start:len(new) - end if end else len(new)]
    # A run of repeated closers has several possible text diffs. The client's
    # post-edit caret identifies the actual insertion point in that run.
    if len(new) == len(old) + 1 and caret is not None and 0 < caret <= len(new):
        point = caret - 1
        if old[:point] + new[point:point + 1] + old[point:] == new:
            start, stop, inserted = point, point, new[point:point + 1]
    return start, stop, inserted


def _groups(text):
    stack, groups = [], []
    masked = _visible(text)
    for index, char in enumerate(masked):
        if char in PAIRS:
            stack.append((char, index))
            if len(stack) > 16:
                return masked, stack, groups, True
        elif char in CLOSERS:
            if not stack or stack[-1][0] != CLOSERS[char]:
                return masked, stack, groups, True
            opener, start = stack.pop()
            if opener == '[':
                groups.append((start, index))
    return masked, stack, groups, False


def _complete_expression(text):
    try:
        return '[' in _visible(text) and bool(parse_algorithm(text).moves)
    except ValueError:
        return False


class CommutatorEditor:
    def __init__(self):
        self.reset('[]')

    def reset(self, text):
        self.text = text or '[]'
        self._reuse_frame = self.text.strip() == '[]'

    def edit(self, raw, selection=None):
        old = self.text
        anchor, extent = selection if selection is not None else (len(raw), len(raw))
        anchor = max(0, min(len(raw), anchor))
        extent = max(0, min(len(raw), extent))
        start, stop, inserted = _difference(old, raw, extent if anchor == extent else None)
        removed = old[start:stop]
        reuse = self._reuse_frame
        self._reuse_frame = False

        def finish(text, caret=None):
            self.text = text
            if text == '[]' and not raw.strip():
                self._reuse_frame = True
            return BracketEdit(text, (caret, caret) if caret is not None else None)

        if raw == old:
            return finish(raw)
        if not raw.strip():
            return finish('[]', 1)
        if len(raw) > MAX_INPUT:
            # Keep over-limit pastes intact for the existing parser to reject.
            return finish(raw)
        if old.strip() == '[]' and inserted == '[' and not removed and reuse:
            # Habitually typing an opening bracket at the empty field reuses
            # its existing frame. A second opening creates a nested pair.
            return finish(old, old.index('[') + 1)
        if inserted in CLOSERS and len(inserted) == 1 and not removed:
            if start < len(old) and old[start] == inserted:
                return finish(old, start + 1)
            if start == len(old) and old.endswith(inserted) and not _groups(old)[3] and not _groups(old)[1]:
                return finish(old, len(old))
        # The diff alone cannot distinguish a full-field paste from a paste
        # inside [] when both have the same outer brackets. The native caret
        # distinguishes them: inside is before the original final bracket.
        if (old.strip() == '[]' and start == 1 and stop == 1 and len(inserted) > 1
                and selection is not None and anchor == extent == len(raw) - 1):
            if _complete_expression(inserted):
                return finish(inserted, len(inserted))
            if inserted.strip() == '[]':
                return finish('[]', 1)
        if (len(inserted) > 1 or len(removed) > 1) and _complete_expression(raw):
            return finish(raw)

        text = raw
        changed = False

        def add(index, value, *, closing=False):
            nonlocal text, anchor, extent, changed
            text = text[:index] + value + text[index:]
            if index < anchor or index == anchor and not closing:
                anchor += len(value)
            if index < extent or index == extent and not closing:
                extent += len(value)
            changed = True

        # Removing an empty nested pair removes its other half too. Root []
        # remains available, and deleting brackets never deletes move text.
        if not inserted and len(removed) == 1 and start > 0:
            if removed in PAIRS and old[start:start + 2] == removed + PAIRS[removed]:
                text = text[:start] + text[start + 1:]
                anchor, extent, changed = start, start, True
            elif removed in CLOSERS and old[start - 1:start + 1] == CLOSERS[removed] + removed and start > 1:
                text = text[:start - 1] + text[start:]
                anchor, extent, changed = start - 1, start - 1, True

        if len(inserted) == 1 and inserted in PAIRS and not removed:
            add(start + 1, PAIRS[inserted], closing=True)

        masked = _visible(text)
        if '[' not in masked:
            # A body-only paste such as R,U gets the required outer frame.
            add(0, '[')
            if not text.rstrip().endswith(']'):
                tail_comment = '//' in text.rsplit('\n', 1)[-1]
                add(len(text), ('\n' if tail_comment else '') + ']', closing=True)
        elif removed == '[' and start == len(old) - len(old.lstrip()) and old.lstrip().startswith('['):
            add(start, '[')

        masked, stack, _, invalid = _groups(text)
        if not invalid and stack:
            tail_comment = '//' in text.rsplit('\n', 1)[-1]
            closers = ''.join(PAIRS[opener] for opener, _ in reversed(stack))
            add(len(text), ('\n' if tail_comment else '') + closers, closing=True)

        # Do not fight deletion/undo of automatically added inner brackets.
        # Re-infer nesting only when the body text, not just brackets, changes.
        body = lambda value: re.sub(r'[\[\]()]', '', _visible(value))
        infer = body(raw) != body(old)
        if infer:
            for _ in range(16):
                masked, stack, groups, invalid = _groups(text)
                if invalid or stack:
                    break
                target = None
                for left, right in groups:  # Inner groups are visited first.
                    depth, separators = 0, []
                    for index in range(left + 1, right):
                        char = masked[index]
                        if char in PAIRS:
                            depth += 1
                        elif char in CLOSERS:
                            depth -= 1
                        elif depth == 0 and char in ':,':
                            separators.append(index)
                    if len(separators) > 1 and masked[separators[0]] == ':':
                        begin = separators[0] + 1
                        while begin < right and text[begin].isspace():
                            begin += 1
                        target = begin, right
                        break
                if target is None:
                    break
                begin, end = target
                add(end, ']', closing=True)
                add(begin, '[')

        self.text = text
        if text == '[]' and removed and inserted != '[':
            self._reuse_frame = True
        return BracketEdit(text, (anchor, extent) if changed else None)
