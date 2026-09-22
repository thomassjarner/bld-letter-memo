"""
AppState: the single place the UI talks to for reading/mutating data.
Every mutating method saves via the repository immediately afterward, so
the app is always autosaved. Pages register on_change callbacks so they
can refresh when something they don't own changes.
"""

from typing import Callable, List, Optional

from core.cube_definitions import CATEGORY_PIECES
from data.models import AppData, CategoryScheme, LetterScheme
from data.repository import AppDataRepository

BUFFER_MARKER = "BUFFER"


class AppState:
    def __init__(self, repository: AppDataRepository):
        self._repo = repository
        self.data: AppData = self._repo.load()
        self._listeners: List[Callable[[], None]] = []
        self._save_status_listeners: List[Callable[[str], None]] = []

    # ---- change notification -------------------------------------------------

    def on_change(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        for cb in self._listeners:
            cb()

    def on_save_status(self, callback: Callable[[str], None]) -> None:
        self._save_status_listeners.append(callback)

    def _set_save_status(self, status: str) -> None:
        for cb in self._save_status_listeners:
            cb(status)

    def _save(self, notify: bool = True) -> None:
        self._set_save_status("Saving…")
        self._repo.save(self.data)
        self._set_save_status("Saved")
        if notify:
            self._notify()

    def replace_data(self, data: AppData) -> None:
        """Replace all app data, used by Settings -> Import Backup."""
        self.data = data
        self._save()

    # ---- scheme CRUD -----------------------------------------------------

    @property
    def scheme_names(self) -> List[str]:
        return sorted(self.data.schemes.keys())

    @property
    def active_scheme(self) -> Optional[LetterScheme]:
        if self.data.active_scheme and self.data.active_scheme in self.data.schemes:
            return self.data.schemes[self.data.active_scheme]
        return None

    def create_scheme(self, name: str) -> LetterScheme:
        name = self._unique_name(name)
        scheme = LetterScheme(name=name)
        self.data.schemes[name] = scheme
        if self.data.active_scheme is None:
            self.data.active_scheme = name
        self._save()
        return scheme

    def rename_scheme(self, old_name: str, new_name: str) -> None:
        if old_name not in self.data.schemes or old_name == new_name:
            return
        new_name = self._unique_name(new_name)
        scheme = self.data.schemes.pop(old_name)
        scheme.name = new_name
        self.data.schemes[new_name] = scheme
        if self.data.active_scheme == old_name:
            self.data.active_scheme = new_name
        self._save()

    def duplicate_scheme(self, name: str) -> Optional[LetterScheme]:
        if name not in self.data.schemes:
            return None
        new_name = self._unique_name(f"{name} copy")
        new_scheme = self.data.schemes[name].duplicate(new_name)
        self.data.schemes[new_name] = new_scheme
        self._save()
        return new_scheme

    def delete_scheme(self, name: str) -> None:
        if name not in self.data.schemes:
            return
        del self.data.schemes[name]
        if self.data.active_scheme == name:
            remaining = self.scheme_names
            self.data.active_scheme = remaining[0] if remaining else None
        self._save()

    def switch_scheme(self, name: str) -> None:
        if name in self.data.schemes:
            self.data.active_scheme = name
            self._save()

    def _unique_name(self, base: str) -> str:
        if base not in self.data.schemes:
            return base
        i = 2
        while f"{base} ({i})" in self.data.schemes:
            i += 1
        return f"{base} ({i})"

    # ---- editing a scheme's stickers/buffer -------------------------------

    def _category_scheme(self, scheme: LetterScheme, category: str) -> CategoryScheme:
        return scheme.corners if category == "corners" else scheme.edges

    def set_buffer(self, scheme: LetterScheme, category: str, buffer_sticker: str) -> None:
        cat = self._category_scheme(scheme, category)
        pieces = CATEGORY_PIECES[category]

        if cat.buffer_piece and cat.buffer_piece in pieces:
            for sticker in pieces[cat.buffer_piece]:
                if cat.stickers.get(sticker) == BUFFER_MARKER:
                    del cat.stickers[sticker]

        piece_name = next((p for p, stickers in pieces.items() if buffer_sticker in stickers), None)
        if piece_name is None:
            return
        cat.buffer_piece = piece_name
        cat.buffer_sticker = buffer_sticker
        for sticker in pieces[piece_name]:
            cat.stickers[sticker] = BUFFER_MARKER
        self._save()

    def set_sticker_letter(self, scheme: LetterScheme, category: str, sticker: str, letter: str) -> None:
        cat = self._category_scheme(scheme, category)
        letter = letter.strip().upper()
        if not letter:
            cat.stickers.pop(sticker, None)
        else:
            cat.stickers[sticker] = letter[0]
        self._save()


    # ---- BLD scheme settings -----------------------------------------------

    def set_memo_orientation(self, scheme: LetterScheme, up: str, front: str) -> bool:
        """Set the scheme's memo orientation. Returns False for an invalid pair."""
        colors = {"W", "Y", "G", "B", "R", "O"}
        opposite = {"W": "Y", "Y": "W", "G": "B", "B": "G", "R": "O", "O": "R"}
        if up not in colors or front not in colors or front in {up, opposite[up]}:
            return False
        scheme.memo_up = up
        scheme.memo_front = front
        self._save()
        return True

    def set_order(self, scheme: LetterScheme, kind: str, value: str) -> bool:
        """Save CE/EC, or blank to use the standard placeholder/default."""
        value = (value or "").strip().upper()
        if value not in {"", "CE", "EC"}:
            return False
        if kind == "memo":
            scheme.memo_order = value
        else:
            scheme.execution_order = value
        self._save()
        return True

    def set_orientation_memo_mode(self, scheme: LetterScheme, category: str, mode: str) -> None:
        if mode not in {"visual", "trace"}:
            return
        cat = self._category_scheme(scheme, category)
        cat.orientation_memo = mode
        cat.tracing_mode = "custom"
        self._save()

    def set_cycle_break_sticker(self, scheme: LetterScheme, category: str, piece: str, sticker: str) -> None:
        cat = self._category_scheme(scheme, category)
        pieces = CATEGORY_PIECES[category]
        if piece not in pieces or sticker not in pieces[piece]:
            return
        cat.cycle_break_stickers[piece] = sticker
        cat.tracing_mode = "custom"
        self._save()

    def set_cycle_break_priority(self, scheme: LetterScheme, category: str, priority: list[str]) -> None:
        cat = self._category_scheme(scheme, category)
        pieces = CATEGORY_PIECES[category]
        seen = set()
        clean = []
        for piece in priority:
            if piece in pieces and piece not in seen:
                clean.append(piece)
                seen.add(piece)
        cat.cycle_break_priority = clean
        cat.tracing_mode = "custom"
        self._save()

    def reset_tracing_preferences(self, scheme: LetterScheme, category: str) -> None:
        cat = self._category_scheme(scheme, category)
        cat.tracing_mode = "standard"
        cat.cycle_break_stickers.clear()
        cat.cycle_break_priority.clear()
        cat.orientation_memo = "visual"
        self._save()


    # ---- general settings -------------------------------------------------

    def set_dark_mode(self, enabled: bool) -> None:
        self.data.dark_mode = bool(enabled)
        self._save(notify=False)

    # ---- global words ------------------------------------------------------

    def set_word(self, pair: str, word: str) -> None:
        word = word.strip()
        if word:
            self.data.global_words[pair] = word
        else:
            self.data.global_words.pop(pair, None)
        # Editing a mnemonic does not change pair activation, so avoid a
        # full page refresh that would steal focus from the word field.
        self._save(notify=False)

    def get_word(self, pair: str) -> str:
        return self.data.global_words.get(pair, "")

    # ---- practice timer ---------------------------------------------------

    def add_practice_solve(self, centiseconds: int, scramble: str, dnf: bool = False, plus2: bool = False) -> int:
        from data.models import PracticeSolve
        solve = PracticeSolve(
            centiseconds=max(0, int(centiseconds)),
            scramble=scramble,
            dnf=bool(dnf),
            plus2=bool(plus2) and not bool(dnf),
        )
        self.data.practice_solves.append(solve)
        self._save(notify=False)
        return len(self.data.practice_solves) - 1

    def set_practice_solve_result(self, index: int, dnf: bool = False, plus2: bool = False) -> None:
        if 0 <= index < len(self.data.practice_solves):
            solve = self.data.practice_solves[index]
            solve.dnf = bool(dnf)
            solve.plus2 = bool(plus2) and not solve.dnf
            self._save(notify=False)

    def set_practice_solve_dnf(self, index: int, dnf: bool) -> None:
        # Kept for backwards compatibility with older UI code.
        self.set_practice_solve_result(index, dnf=dnf, plus2=False)

    def delete_practice_solve(self, index: int) -> None:
        if 0 <= index < len(self.data.practice_solves):
            del self.data.practice_solves[index]
            self._save(notify=False)

    def reset_practice_session(self) -> None:
        self.data.practice_solves.clear()
        self._save(notify=False)
