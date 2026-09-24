"""Persistent data model for BLD Letter Memo."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

CURRENT_VERSION = 10


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
    # Scheme-specific memo display preferences.
    show_cycle_colors: bool = False
    highlight_orientation_targets: bool = False
    # Optional 3-style parity handling. When enabled and the corner trace is
    # odd, the edge buffer piece and this partner are memo-swapped before
    # tracing edges. UR is the standard suggested partner.
    three_style_enabled: bool = False
    edge_parity_partner: str = "UR"

    def to_dict(self) -> dict:
        return {
            "corners": self.corners.to_dict(),
            "edges": self.edges.to_dict(),
            "memo_up": self.memo_up,
            "memo_front": self.memo_front,
            "memo_order": self.memo_order,
            "execution_order": self.execution_order,
            "show_cycle_colors": bool(self.show_cycle_colors),
            "highlight_orientation_targets": bool(self.highlight_orientation_targets),
            "three_style_enabled": bool(self.three_style_enabled),
            "edge_parity_partner": self.edge_parity_partner or "UR",
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
            show_cycle_colors=bool(d.get("show_cycle_colors", False)),
            highlight_orientation_targets=bool(d.get("highlight_orientation_targets", False)),
            three_style_enabled=bool(d.get("three_style_enabled", False)),
            edge_parity_partner=str(d.get("edge_parity_partner", "UR") or "UR"),
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
    # Optional display aliases for canonical pair IDs. Example: AB -> ØB.
    # Logic/search can still address the canonical AB pair.
    pair_aliases: Dict[str, str] = field(default_factory=dict)
    practice_sessions: Dict[str, List[PracticeSolve]] = field(
        default_factory=lambda: {"Session 1": [], "Session 2": [], "Session 3": []}
    )
    active_practice_session: str = "Session 1"
    dark_mode: bool = False

    def ensure_default_sessions(self) -> None:
        for name in ("Session 1", "Session 2", "Session 3"):
            self.practice_sessions.setdefault(name, [])
        if self.active_practice_session not in self.practice_sessions:
            self.active_practice_session = "Session 1"

    @property
    def practice_solves(self) -> List[PracticeSolve]:
        self.ensure_default_sessions()
        return self.practice_sessions[self.active_practice_session]

    @practice_solves.setter
    def practice_solves(self, solves: List[PracticeSolve]) -> None:
        self.ensure_default_sessions()
        self.practice_sessions[self.active_practice_session] = list(solves)

    def to_dict(self) -> dict:
        self.ensure_default_sessions()
        return {
            "version": CURRENT_VERSION,
            "active_scheme": self.active_scheme,
            "schemes": {name: s.to_dict() for name, s in self.schemes.items()},
            "global_words": dict(self.global_words),
            "pair_aliases": dict(self.pair_aliases),
            "practice_sessions": {
                name: [solve.to_dict() for solve in solves]
                for name, solves in self.practice_sessions.items()
            },
            "active_practice_session": self.active_practice_session,
            "dark_mode": bool(self.dark_mode),
        }

    @staticmethod
    def from_dict(d: dict) -> "AppData":
        schemes = {name: LetterScheme.from_dict(name, sd) for name, sd in d.get("schemes", {}).items()}

        raw_sessions = d.get("practice_sessions")
        sessions: Dict[str, List[PracticeSolve]] = {}
        if isinstance(raw_sessions, dict):
            for name, values in raw_sessions.items():
                if not isinstance(name, str) or not isinstance(values, list):
                    continue
                sessions[name] = [
                    PracticeSolve.from_dict(x) for x in values if isinstance(x, dict)
                ]
        else:
            # Migration from pre-session builds.
            sessions["Session 1"] = [
                PracticeSolve.from_dict(x)
                for x in d.get("practice_solves", [])
                if isinstance(x, dict)
            ]

        data = AppData(
            version=CURRENT_VERSION,
            active_scheme=d.get("active_scheme"),
            schemes=schemes,
            global_words=dict(d.get("global_words", {})),
            pair_aliases={
                str(k): str(v)
                for k, v in dict(d.get("pair_aliases", {})).items()
                if str(k) and str(v)
            },
            practice_sessions=sessions,
            active_practice_session=str(d.get("active_practice_session", "Session 1")),
            dark_mode=bool(d.get("dark_mode", False)),
        )
        data.ensure_default_sessions()
        return data
