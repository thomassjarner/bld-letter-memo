"""
Static 3x3 cube definitions: sticker display order and physical-piece groupings.

This module is pure data with no I/O and no dependency on the storage layer
or the UI. It is the single source of truth for "which stickers exist,
in what order, and which physical piece each one belongs to."
"""

from typing import Dict, List, Set, Tuple

FACE_ORDER = ["U", "L", "F", "R", "B", "D"]

# Exact order requested: corners grouped by face, 4 stickers per face.
CORNER_STICKER_ORDER: List[str] = [
    "UBL", "UBR", "UFR", "UFL",
    "LUB", "LUF", "LDF", "LDB",
    "FUL", "FUR", "FDR", "FDL",
    "RUF", "RUB", "RDB", "RDF",
    "BUR", "BUL", "BDL", "BDR",
    "DFL", "DFR", "DBR", "DBL",
]

CORNER_PIECES: Dict[str, Set[str]] = {
    "UBL": {"UBL", "LUB", "BUL"},
    "UBR": {"UBR", "RUB", "BUR"},
    "UFR": {"UFR", "RUF", "FUR"},
    "UFL": {"UFL", "FUL", "LUF"},
    "DFL": {"DFL", "LDF", "FDL"},
    "DFR": {"DFR", "RDF", "FDR"},
    "DBR": {"DBR", "RDB", "BDR"},
    "DBL": {"DBL", "BDL", "LDB"},
}

# Confirmed with user: mirrors the corner grouping, face by face.
EDGE_STICKER_ORDER: List[str] = [
    "UB", "UR", "UF", "UL",
    "LU", "LF", "LD", "LB",
    "FU", "FR", "FD", "FL",
    "RU", "RB", "RD", "RF",
    "BU", "BL", "BD", "BR",
    "DF", "DR", "DB", "DL",
]

EDGE_PIECES: Dict[str, Set[str]] = {
    "UB": {"UB", "BU"},
    "UR": {"UR", "RU"},
    "UF": {"UF", "FU"},
    "UL": {"UL", "LU"},
    "FR": {"FR", "RF"},
    "FL": {"FL", "LF"},
    "BL": {"BL", "LB"},
    "BR": {"BR", "RB"},
    "DF": {"DF", "FD"},
    "DR": {"DR", "RD"},
    "DB": {"DB", "BD"},
    "DL": {"DL", "LD"},
}

CATEGORY_STICKER_ORDER = {
    "corners": CORNER_STICKER_ORDER,
    "edges": EDGE_STICKER_ORDER,
}

CATEGORY_PIECES = {
    "corners": CORNER_PIECES,
    "edges": EDGE_PIECES,
}


def find_piece_for_sticker(sticker: str, pieces: Dict[str, Set[str]]) -> str | None:
    for piece_name, stickers in pieces.items():
        if sticker in stickers:
            return piece_name
    return None


def get_all_stickers(pieces: Dict[str, Set[str]]) -> Set[str]:
    return {s for stickers in pieces.values() for s in stickers}


def face_groups(category: str) -> List[Tuple[str, List[str]]]:
    """
    Split a category's sticker order into (face_letter, [4 stickers]) groups,
    in FACE_ORDER, for grouped GUI display.
    """
    order = CATEGORY_STICKER_ORDER[category]
    groups = []
    for i, face in enumerate(FACE_ORDER):
        chunk = order[i * 4:(i + 1) * 4]
        groups.append((face, chunk))
    return groups
