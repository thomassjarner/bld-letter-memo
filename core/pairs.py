"""
Logic for determining which letter pairs are valid, and which pairs are
"active" across a set of saved schemes.

Deliberately has zero dependency on Flet or the storage layer, per the
requirement to be able to improve BLD rules later without touching the GUI.

Current validity rules (documented so they're easy to extend later):
  1. A sticker only produces a letter if it has been assigned one AND it is
     not part of the buffer piece for that category.
  2. AA, BB, ... (a letter paired with itself) is never valid.
  3. Two letters that both resolve to stickers on the SAME physical piece
     are never valid as a pair together (this also transitively excludes
     the buffer, since buffer stickers never receive a normal letter).
"""

from itertools import product
from typing import Dict, List, Set, Tuple

from core.cube_definitions import CATEGORY_PIECES, find_piece_for_sticker
from data.models import CategoryScheme, LetterScheme

BUFFER_MARKER = "BUFFER"


def valid_letters(category_scheme: CategoryScheme, category: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Returns (letter_to_sticker, letter_to_piece) for all non-buffer,
    assigned stickers in this category scheme.
    """
    pieces = CATEGORY_PIECES[category]
    buffer_piece = category_scheme.buffer_piece

    letter_to_sticker: Dict[str, str] = {}
    letter_to_piece: Dict[str, str] = {}

    for sticker, letter in category_scheme.stickers.items():
        if letter == BUFFER_MARKER:
            continue
        piece = find_piece_for_sticker(sticker, pieces)
        if piece is None or piece == buffer_piece:
            continue
        letter_to_sticker[letter] = sticker
        letter_to_piece[letter] = piece

    return letter_to_sticker, letter_to_piece


def find_duplicate_letters(category_scheme: CategoryScheme, category: str) -> Dict[str, List[str]]:
    """
    Returns letter -> list of stickers, for any letter assigned to more
    than one non-buffer sticker. Empty dict means no conflicts.
    Used by the GUI to warn the user; the prototype had no such check.
    """
    pieces = CATEGORY_PIECES[category]
    buffer_piece = category_scheme.buffer_piece

    letter_to_stickers: Dict[str, List[str]] = {}
    for sticker, letter in category_scheme.stickers.items():
        if letter == BUFFER_MARKER:
            continue
        piece = find_piece_for_sticker(sticker, pieces)
        if piece is None or piece == buffer_piece:
            continue
        letter_to_stickers.setdefault(letter, []).append(sticker)

    return {letter: stickers for letter, stickers in letter_to_stickers.items() if len(stickers) > 1}


def generate_letter_pairs(category_scheme: CategoryScheme, category: str) -> Set[str]:
    letter_to_sticker, letter_to_piece = valid_letters(category_scheme, category)
    letters = sorted(letter_to_sticker)

    pairs = set()
    for first, second in product(letters, repeat=2):
        if first == second:
            continue
        if letter_to_piece[first] == letter_to_piece[second]:
            continue
        pairs.add(first + second)
    return pairs


def get_active_pairs(schemes: Dict[str, LetterScheme]) -> Dict[str, List[str]]:
    """
    Returns pair -> compact source labels. Categories are grouped per scheme:
    ``My Scheme (C)``, ``My Scheme (E)``, or ``My Scheme (CE)``.
    """
    pair_sources: Dict[str, Dict[str, Set[str]]] = {}

    for scheme_name, scheme in schemes.items():
        for category, category_scheme, code in (
            ("corners", scheme.corners, "C"),
            ("edges", scheme.edges, "E"),
        ):
            if not category_scheme.buffer_piece:
                continue
            for pair in generate_letter_pairs(category_scheme, category):
                pair_sources.setdefault(pair, {}).setdefault(scheme_name, set()).add(code)

    active: Dict[str, List[str]] = {}
    for pair, schemes_for_pair in pair_sources.items():
        labels = []
        for scheme_name in sorted(schemes_for_pair):
            codes = schemes_for_pair[scheme_name]
            suffix = "CE" if codes == {"C", "E"} else ("C" if "C" in codes else "E")
            labels.append(f"{scheme_name} ({suffix})")
        active[pair] = labels
    return active
