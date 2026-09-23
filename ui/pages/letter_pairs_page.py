import flet as ft

from core.pairs import get_active_pairs
from ui.state import AppState


class LetterPairsPage(ft.Column):
    def __init__(self, state: AppState):
        super().__init__(expand=True, spacing=12)
        self.state = state
        self.search_field = ft.TextField(
            hint_text="Search letter pairs...",
            width=260,
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._on_search_change,
        )
        self.search_pairs = ft.Checkbox(
            label="Show letter pairs", value=True, on_change=self._on_search_mode_change
        )
        self.search_words = ft.Checkbox(
            label="Search within words", value=False, on_change=self._on_search_mode_change
        )
        self.scheme_filter = ft.Dropdown(
            width=210,
            value="__all__",
            label="Letter scheme",
            options=[ft.DropdownOption(key="__all__", text="All letter schemes")],
            on_select=self._on_search_change,
        )
        self.status_filter = ft.Dropdown(
            width=175,
            value="all",
            options=[
                ft.DropdownOption(key="all", text="All pairs"),
                ft.DropdownOption(key="active", text="Active"),
                ft.DropdownOption(key="inactive", text="Inactive"),
                ft.DropdownOption(key="missing", text="Missing words"),
            ],
            on_select=self._on_search_change,
        )
        self.progress_text = ft.Text(size=12, weight=ft.FontWeight.BOLD)
        self.duplicate_warning = ft.Text(size=12, color=ft.Colors.ORANGE_700)
        self.progress_bar = ft.ProgressBar(width=220, value=0)
        self.count_text = ft.Text(size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.rows_view = ft.ListView(expand=True, spacing=2)
        self._word_fields: list[ft.TextField] = []

        self.controls = [
            ft.Row(
                [
                    self.search_field,
                    self.search_pairs,
                    self.search_words,
                    self.scheme_filter,
                    self.status_filter,
                ],
                wrap=True,
            ),
            ft.Row([self.progress_text, self.progress_bar, self.count_text], wrap=True),
            self.duplicate_warning,
            ft.Container(
                content=ft.Row(
                    [
                        ft.Container(ft.Text("Pair", weight=ft.FontWeight.BOLD), width=70),
                        ft.Container(ft.Text("Word", weight=ft.FontWeight.BOLD), expand=True),
                        ft.Container(ft.Text("Status", weight=ft.FontWeight.BOLD), width=90),
                        ft.Container(ft.Text("Active in", weight=ft.FontWeight.BOLD), width=220),
                    ]
                ),
                padding=ft.Padding.symmetric(horizontal=8),
            ),
            ft.Divider(height=1),
            self.rows_view,
        ]
        self.refresh(update=False)

    def refresh(self, update: bool = True):
        # Keep the scheme selector synchronized with saved schemes.
        scheme_names = self.state.scheme_names
        selected_scheme = self.scheme_filter.value or "__all__"
        if selected_scheme != "__all__" and selected_scheme not in self.state.data.schemes:
            selected_scheme = "__all__"
            self.scheme_filter.value = "__all__"
        self.scheme_filter.options = [ft.DropdownOption(key="__all__", text="All letter schemes")] + [
            ft.DropdownOption(key=name, text=name) for name in scheme_names
        ]

        if selected_scheme == "__all__":
            active_pairs = get_active_pairs(self.state.data.schemes)
            all_pairs = set(active_pairs) | set(self.state.data.global_words.keys())
        else:
            active_pairs = get_active_pairs({selected_scheme: self.state.data.schemes[selected_scheme]})
            # "Show only from this scheme" is intentionally strict: unrelated
            # stored/inactive dictionary entries are not included.
            all_pairs = set(active_pairs)

        query = (self.search_field.value or "").strip()
        status = self.status_filter.value

        active_total = len(active_pairs)
        completed = sum(1 for pair in active_pairs if self.state.get_word(pair).strip())
        remaining = active_total - completed
        percent = int(round((completed / active_total) * 100)) if active_total else 0
        self.progress_text.value = (
            f"Letter-pair dictionary: {completed} / {active_total} complete — "
            f"{remaining} remaining ({percent}%)"
        )
        self.progress_bar.value = completed / active_total if active_total else 0

        self._update_duplicate_warning()

        rows = []
        self._word_fields = []
        for pair in sorted(all_pairs):
            is_active = pair in active_pairs
            word = self.state.get_word(pair)

            if status == "active" and not is_active:
                continue
            if status == "inactive" and is_active:
                continue
            if status == "missing" and (not is_active or bool(word.strip())):
                continue
            if query and not self._matches_search(pair, word, query):
                continue

            rows.append((pair, word, is_active, active_pairs.get(pair, [])))

        self.count_text.value = f"{len(rows)} shown"
        self.rows_view.controls = [
            self._build_row(pair, word, is_active, sources) for pair, word, is_active, sources in rows
        ]
        if update:
            self.update()

    def _matches_search(self, pair: str, word: str, query: str) -> bool:
        pair_match = False
        word_match = False

        if self.search_pairs.value:
            q = query.upper()
            if len(q) == 1 and q.isalpha():
                pair_match = pair.startswith(q)
            elif len(q) == 2 and q[0].isalpha() and q[1] == "-":
                pair_match = pair.startswith(q[0])
            elif len(q) == 2 and q[0] == "-" and q[1].isalpha():
                pair_match = pair.endswith(q[1])
            else:
                pair_match = pair == q

        if self.search_words.value:
            word_match = query.lower() in word.lower()

        return pair_match or word_match

    def _build_row(self, pair: str, word: str, is_active: bool, sources: list[str]) -> ft.Control:
        field = ft.TextField(
            value=word,
            hint_text=None,
            dense=True,
            border=ft.InputBorder.UNDERLINE,
            expand=True,
            on_submit=self._focus_next,
            on_change=lambda e, p=pair: self._word_changed(p, e.control.value),
        )
        self._word_fields.append(field)

        status_chip = ft.Container(
            content=ft.Text("Active" if is_active else "Inactive", size=12, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.GREEN_600 if is_active else ft.Colors.GREY_500,
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=12,
        )

        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(ft.Text(pair, weight=ft.FontWeight.BOLD), width=70),
                    ft.Container(field, expand=True),
                    ft.Container(status_chip, width=90),
                    ft.Container(
                        ft.Text(", ".join(sources), size=11, color=ft.Colors.ON_SURFACE_VARIANT, no_wrap=False),
                        width=220,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            bgcolor=None if is_active else ft.Colors.GREY_100,
            opacity=1.0 if is_active else 0.75,
        )

    def _word_changed(self, pair: str, value: str):
        self.state.set_word(pair, value)
        # Update progress/count without rebuilding the list and stealing focus.
        active_pairs = get_active_pairs(self.state.data.schemes)
        total = len(active_pairs)
        completed = sum(1 for p in active_pairs if self.state.get_word(p).strip())
        remaining = total - completed
        percent = int(round((completed / total) * 100)) if total else 0
        self.progress_text.value = (
            f"Letter-pair dictionary: {completed} / {total} complete — {remaining} remaining ({percent}%)"
        )
        self.progress_bar.value = completed / total if total else 0
        self._update_duplicate_warning()
        self.progress_text.update()
        self.progress_bar.update()
        self.duplicate_warning.update()

    def _update_duplicate_warning(self):
        by_word = {}
        for pair, word in self.state.data.global_words.items():
            clean = word.strip()
            if clean:
                by_word.setdefault(clean.casefold(), []).append((pair, clean))
        duplicates = [items for items in by_word.values() if len(items) > 1]
        if duplicates:
            examples = []
            for items in sorted(duplicates, key=lambda x: x[0][1].casefold())[:4]:
                examples.append(f"{items[0][1]}: {', '.join(pair for pair, _ in items)}")
            more = " …" if len(duplicates) > 4 else ""
            self.duplicate_warning.value = "⚠ Duplicate mnemonic words — " + "; ".join(examples) + more
        else:
            self.duplicate_warning.value = ""

    def _focus_next(self, e):
        try:
            idx = self._word_fields.index(e.control)
        except ValueError:
            return
        if idx + 1 < len(self._word_fields):
            self._word_fields[idx + 1].focus()
            self.update()

    def _on_search_mode_change(self, e):
        # Keep at least one search mode enabled.
        if not self.search_pairs.value and not self.search_words.value:
            e.control.value = True
        self.search_field.hint_text = (
            "Search pair or word..." if self.search_words.value else "Search letter pairs (AC, A-, -S)..."
        )
        self.refresh()

    def _on_search_change(self, e):
        self.refresh()
