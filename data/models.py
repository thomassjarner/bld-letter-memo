"""Persistent data model for BLD Letter Memo."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

CURRENT_VERSION = 6


@dataclass
class CategoryScheme:
    # Physical buffer piece (canonical piece name, e.g. UBL / DF).
    buffer_piece: Optional[str] = None
    # Exact sticker used as the tracing buffer (e.g. LUB / DF).
    buffer_sticker: Optional[str] = None
    stickers: Dict[str, str] = field(default_factory=dict)
    # Reserved for the BLD tracer. Empty means the Standard preset is used.
    tracing_mode: str = "standard"
    cycle_break_stickers: Dict[str, str] = field(default_factory=dict)
    cycle_break_priority: List[str] = field(default_factory=list)
    orientation_memo: str = "visual"

    def to_dict(self) -> dict:
        return {
            "buffer_piece": self.buffer_piece,
            "buffer_sticker": self.buffer_sticker,
            "stickers": dict(self.stickers),
            "tracing_mode": self.tracing_mode,
            "cycle_break_stickers": dict(self.cycle_break_stickers),
            "cycle_break_priority": list(self.cycle_break_priority),
            "orientation_memo": self.orientation_memo,
        }

    @staticmethod
    def from_dict(d: dict) -> "CategoryScheme":
        return CategoryScheme(
            buffer_piece=d.get("buffer_piece"),
            buffer_sticker=d.get("buffer_sticker") or d.get("buffer_piece"),
            stickers=dict(d.get("stickers", {})),
            tracing_mode=d.get("tracing_mode", "standard"),
            cycle_break_stickers=dict(d.get("cycle_break_stickers", {})),
            cycle_break_priority=list(d.get("cycle_break_priority", [])),
            orientation_memo=d.get("orientation_memo", "visual"),
        )


@dataclass
class LetterScheme:
    name: str
    corners: CategoryScheme = field(default_factory=CategoryScheme)
    edges: CategoryScheme = field(default_factory=CategoryScheme)
    # Scheme-level memo orientation. Standard default: white U / green F.
    memo_up: str = "W"
    memo_front: str = "G"
    # Blank means the standard defaults shown as placeholders in the UI.
    # Standard: memo corners->edges (CE), execute edges->corners (EC).
    memo_order: str = ""
    execution_order: str = ""

    def to_dict(self) -> dict:
        return {
            "corners": self.corners.to_dict(),
            "edges": self.edges.to_dict(),
            "memo_up": self.memo_up,
            "memo_front": self.memo_front,
            "memo_order": self.memo_order,
            "execution_order": self.execution_order,
        }

    @staticmethod
    def from_dict(name: str, d: dict) -> "LetterScheme":
        return LetterScheme(
            name=name,
            corners=CategoryScheme.from_dict(d.get("corners", {})),
            edges=CategoryScheme.from_dict(d.get("edges", {})),
            memo_up=d.get("memo_up", "W"),
            memo_front=d.get("memo_front", "G"),
            memo_order=d.get("memo_order", ""),
            execution_order=d.get("execution_order", ""),
        )

    def duplicate(self, new_name: str) -> "LetterScheme":
        copy = LetterScheme.from_dict(new_name, self.to_dict())
        copy.name = new_name
        return copy


@dataclass
class PracticeSolve:
    # Stored as centiseconds on purpose: the UI and statistics use two decimals.
    centiseconds: int
    scramble: str
    dnf: bool = False
    plus2: bool = False

    def to_dict(self) -> dict:
        return {
            "centiseconds": int(self.centiseconds),
            "scramble": self.scramble,
            "dnf": bool(self.dnf),
            "plus2": bool(self.plus2),
        }

    @staticmethod
    def from_dict(d: dict) -> "PracticeSolve":
        return PracticeSolve(
            centiseconds=max(0, int(d.get("centiseconds", 0))),
            scramble=str(d.get("scramble", "")),
            dnf=bool(d.get("dnf", False)),
            plus2=bool(d.get("plus2", False)),
        )


@dataclass
class AppData:
    version: int = CURRENT_VERSION
    active_scheme: Optional[str] = None
    schemes: Dict[str, LetterScheme] = field(default_factory=dict)
    global_words: Dict[str, str] = field(default_factory=dict)
    practice_solves: List[PracticeSolve] = field(default_factory=list)
    dark_mode: bool = False

    def to_dict(self) -> dict:
        return {
            "version": CURRENT_VERSION,
            "active_scheme": self.active_scheme,
            "schemes": {name: s.to_dict() for name, s in self.schemes.items()},
            "global_words": dict(self.global_words),
            "practice_solves": [solve.to_dict() for solve in self.practice_solves],
            "dark_mode": bool(self.dark_mode),
        }

    @staticmethod
    def from_dict(d: dict) -> "AppData":
        schemes = {name: LetterScheme.from_dict(name, sd) for name, sd in d.get("schemes", {}).items()}
        return AppData(
            version=CURRENT_VERSION,
            active_scheme=d.get("active_scheme"),
            schemes=schemes,
            global_words=dict(d.get("global_words", {})),
            practice_solves=[PracticeSolve.from_dict(x) for x in d.get("practice_solves", []) if isinstance(x, dict)],
            dark_mode=bool(d.get("dark_mode", False)),
        )
