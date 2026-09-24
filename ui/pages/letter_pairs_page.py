import flet as ft

from core.pairs import get_active_pairs
from ui.state import AppState


@ft.control
class LetterPairsPage(ft.Column):
    @property
    def state(self):
        # BaseControl.data is a Flet skip_field(), so Python-only AppState
        # never enters the browser serialization protocol.
        return self.data

    def init(self):
        self.expand = True
        self.spacing = 0

        self.search_field = ft.TextField(
            hint_text="Search letter pairs (AC, A-, -S)...",
            expand=True,
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._on_search_change,
        )
        self.search_pairs = ft.Checkbox(
            label="Search letter pairs", value=True, on_change=self._on_search_mode_change
        )
        self.search_words = ft.Checkbox(
            label="Search within words", value=False, on_change=self._on_search_mode_change
        )
        self.scheme_filter = ft.Dropdown(
            width=210,
            value="__all__",
            label="Letter scheme",
            options=[ft.DropdownOption("__all__", "All letter schemes")],
            on_select=self._on_search_change,
        )
        self.status_filter = ft.Dropdown(
            width=175,
            value="all",
            options=[
                ft.DropdownOption("all", "All pairs"),
                ft.DropdownOption("active", "Active"),
                ft.DropdownOption("inactive", "Inactive"),
                ft.DropdownOption("missing", "Missing words"),
            ],
            on_select=self._on_search_change,
        )
        self.progress_text = ft.Text(size=12, weight=ft.FontWeight.BOLD)
        self.duplicate_warning = ft.Text(size=12, color=ft.Colors.ORANGE_700)
        self.progress_bar = ft.ProgressBar(width=220, value=0)
        self.count_text = ft.Text(size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        # Letter pairs are paged by their canonical first letter (A pairs, B pairs, ...),
        # so this page never needs a scrollable pair list.
        self.rows_view = ft.Column(spacing=0)
        self.current_group: str | None = "A"
        self.available_groups: list[str] = []
        self.group_label = ft.Text("A pairs", weight=ft.FontWeight.BOLD)
        self.prev_group = ft.IconButton(ft.Icons.CHEVRON_LEFT, tooltip="Previous letter", on_click=self._previous_group)
        self.next_group = ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Next letter", on_click=self._next_group)
        self._word_fields: list[ft.TextField] = []
        self._editing_alias_pair: str | None = None

        self.filters_area = ft.Column(
            [
                ft.Row(
                    [
                        self.search_field,
                        self.search_pairs,
                        self.search_words,
                    ],
                    wrap=False,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row([self.scheme_filter, self.status_filter], wrap=True),
                ft.Row([self.progress_text, self.progress_bar, self.count_text], wrap=True),
                self.duplicate_warning,
                ft.Text(
                    "Tip: double-click a pair label to edit how it is displayed (for example AB → ØB).",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=8,
        )
        compact_header = lambda: ft.Container(
            content=ft.Row(
                [
                    ft.Container(ft.Text("Pair", weight=ft.FontWeight.BOLD), width=54),
                    ft.Container(ft.Text("Word", weight=ft.FontWeight.BOLD), expand=True),
                    ft.Container(ft.Text("Status", weight=ft.FontWeight.BOLD), width=72),
                    ft.Container(ft.Text("Active in", weight=ft.FontWeight.BOLD), width=105),
                ],
                spacing=6,
            ),
            padding=ft.Padding.symmetric(horizontal=6),
            expand=True,
        )
        self.table_header = ft.Row(
            [compact_header(), ft.VerticalDivider(width=8), compact_header()],
            spacing=0,
        )
        self.group_controls = ft.Row(
            [self.prev_group, self.group_label, self.next_group],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.controls = [
            self.filters_area,
            self.group_controls,
            self.table_header,
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
        self.scheme_filter.options = [ft.DropdownOption("__all__", "All letter schemes")] + [
            ft.DropdownOption(name, name) for name in scheme_names
        ]

        if selected_scheme == "__all__":
            active_pairs = get_active_pairs(self.state.data.schemes)
            all_pairs = (
                set(active_pairs)
                | set(self.state.data.global_words.keys())
                | set(self.state.data.pair_aliases.keys())
            )
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

        # Search/filter the entire dictionary first. Only after that do we
        # split matches into A/B/C... display pages, so searches are global.
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

        # Group the filtered result by the pair's canonical first letter.
        # An alias such as ØB for canonical AB therefore remains on the A page,
        # while searches for either AB or ØB still find it.
        groups = sorted({pair[0].upper() for pair, *_ in rows if pair})
        self.available_groups = groups
        if not groups:
            self.current_group = None
            page_rows = []
            self.group_label.value = "No matching pairs"
            self.prev_group.disabled = True
            self.next_group.disabled = True
        else:
            if self.current_group not in groups:
                self.current_group = groups[0]
            group_index = groups.index(self.current_group)
            page_rows = [row for row in rows if row[0].upper().startswith(self.current_group)]
            self.group_label.value = f"{self.current_group} pairs"
            self.prev_group.disabled = group_index == 0
            self.next_group.disabled = group_index == len(groups) - 1

        self.count_text.value = f"{len(rows)} matching across all pages · {len(page_rows)} on this page"

        # Use the screen horizontally: each letter page is rendered in two
        # compact columns.  This keeps a full A/B/C... group visible even on
        # shorter laptop screens without relying on browser scrolling.
        cells = [
            self._build_compact_row(pair, word, is_active, sources)
            for pair, word, is_active, sources in page_rows
        ]
        split_at = (len(cells) + 1) // 2
        left = cells[:split_at]
        right = cells[split_at:]
        visual_rows = []
        for i in range(split_at):
            right_cell = right[i] if i < len(right) else ft.Container(expand=True)
            visual_rows.append(
                ft.Row(
                    [left[i], ft.VerticalDivider(width=8), right_cell],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        self.rows_view.controls = visual_rows
        if update and self.page is not None:
            self.update()

    def _pair_search_match(self, value: str, query: str) -> bool:
        """Match exact/canonical/alias pair text including A-, -B wildcards."""
        value = (value or "").upper()
        q = (query or "").upper()
        if not q:
            return True
        if q.endswith("-") and len(q) > 1:
            return value.startswith(q[:-1])
        if q.startswith("-") and len(q) > 1:
            return value.endswith(q[1:])
        if len(q) == 1:
            return value.startswith(q)
        return value == q

    def _matches_search(self, pair: str, word: str, query: str) -> bool:
        pair_match = False
        word_match = False

        if self.search_pairs.value:
            display = self.state.get_pair_display(pair)
            # Search both the canonical pair (AB) and its visible alias (ØB).
            pair_match = self._pair_search_match(pair, query) or self._pair_search_match(display, query)

        if self.search_words.value:
            word_match = query.casefold() in word.casefold()

        return pair_match or word_match

    def _build_compact_row(self, pair: str, word: str, is_active: bool, sources: list[str]) -> ft.Control:
        field = ft.TextField(
            value=word,
            hint_text=None,
            dense=True,
            height=34,
            border=ft.InputBorder.UNDERLINE,
            expand=True,
            on_submit=self._focus_next,
            on_change=lambda e, p=pair: self._word_changed(p, e.control.value),
        )
        self._word_fields.append(field)

        display_pair = self.state.get_pair_display(pair)
        if self._editing_alias_pair == pair:
            pair_label = ft.Container(
                ft.TextField(
                    value=display_pair,
                    width=52,
                    dense=True,
                    autofocus=True,
                    max_length=8,
                    capitalization=ft.TextCapitalization.CHARACTERS,
                    tooltip=f"Underlying pair: {pair}",
                    on_blur=lambda e, p=pair: self._save_pair_alias_inline(p, e.control.value),
                    on_submit=lambda e, p=pair: self._save_pair_alias_inline(p, e.control.value),
                ),
                width=54,
            )
        else:
            pair_label = ft.GestureDetector(
                content=ft.Container(
                    ft.Text(display_pair, weight=ft.FontWeight.BOLD, tooltip=f"Underlying pair: {pair}"),
                    width=54,
                ),
                on_double_tap=lambda e, p=pair: self._edit_pair_alias(p),
            )

        status_chip = ft.Container(
            content=ft.Text("Active" if is_active else "Inactive", size=12, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.GREEN_600 if is_active else ft.Colors.GREY_500,
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=12,
        )

        return ft.Container(
            expand=True,
            content=ft.Row(
                [
                    pair_label,
                    ft.Container(field, expand=True),
                    ft.Container(status_chip, width=72),
                    ft.Container(
                        ft.Text(", ".join(sources), size=11, color=ft.Colors.ON_SURFACE_VARIANT, no_wrap=False),
                        width=105,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
            ),
            padding=ft.Padding.symmetric(horizontal=6, vertical=0),
            bgcolor=None if is_active else ft.Colors.SURFACE_CONTAINER_LOW,
            opacity=1.0 if is_active else 0.75,
        )

    def _edit_pair_alias(self, pair: str):
        self._editing_alias_pair = pair
        self.refresh()

    def _save_pair_alias_inline(self, pair: str, value: str):
        # on_submit can be followed by on_blur; guard against saving twice.
        if self._editing_alias_pair != pair:
            return
        self._editing_alias_pair = None
        self.state.set_pair_alias(pair, (value or "").upper())
        self.refresh()

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
                shown_pairs = ", ".join(self.state.get_pair_display(pair) for pair, _ in items)
                examples.append(f"{items[0][1]}: {shown_pairs}")
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


    def _previous_group(self, e):
        if not self.available_groups or self.current_group not in self.available_groups:
            return
        idx = self.available_groups.index(self.current_group)
        if idx > 0:
            self.current_group = self.available_groups[idx - 1]
            self.refresh()

    def _next_group(self, e):
        if not self.available_groups or self.current_group not in self.available_groups:
            return
        idx = self.available_groups.index(self.current_group)
        if idx + 1 < len(self.available_groups):
            self.current_group = self.available_groups[idx + 1]
            self.refresh()

    def _on_search_mode_change(self, e):
        # Keep at least one search mode enabled.
        if not self.search_pairs.value and not self.search_words.value:
            e.control.value = True
        self.search_field.hint_text = (
            "Search pair or word..." if self.search_words.value else "Search letter pairs (AC, A-, -S)..."
        )
        self.current_group = None
        self.refresh()

    def _on_search_change(self, e):
        self.current_group = None
        self.refresh()
