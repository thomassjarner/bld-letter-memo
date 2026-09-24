import flet as ft

from core.pairs import get_active_pairs


@ft.control
class LetterPairsPage(ft.Column):
    @property
    def state(self):
        return self.data

    def init(self):
        self.expand = True
        self.spacing = 0
        self.selected_view = "dictionary"

        self.tabbar = ft.Tabs(
            length=2,
            selected_index=0,
            on_change=self._on_tab_change,
            content=ft.TabBar(tabs=[ft.Tab(label="Dictionary"), ft.Tab(label="Stats")]),
        )
        self.content_area = ft.Column(expand=True, spacing=0)

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
            width=175, value="all", label="Status", options=[], on_select=self._on_search_change
        )
        self.grade_sort = ft.Dropdown(
            width=190, value="default", label="Sort by grade", options=[], on_select=self._on_search_change
        )
        self.progress_text = ft.Text(size=12, weight=ft.FontWeight.BOLD)
        self.duplicate_warning = ft.Text(size=12, color=ft.Colors.ORANGE_700)
        self.progress_bar = ft.ProgressBar(width=220, value=0)
        self.count_text = ft.Text(size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.filter_average_text = ft.Text(size=12, weight=ft.FontWeight.BOLD)
        self.overall_average_text = ft.Text(size=12, color=ft.Colors.ON_SURFACE_VARIANT)

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
                ft.Row([self.search_field, self.search_pairs, self.search_words],
                       wrap=False, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([self.scheme_filter, self.status_filter, self.grade_sort], wrap=True),
                ft.Row([self.progress_text, self.progress_bar, self.count_text], wrap=True),
                ft.Row([self.filter_average_text, self.overall_average_text], wrap=True, spacing=18),
                self.duplicate_warning,
                ft.Text(
                    "Tip: double-click a pair label to edit how it is displayed (for example AB → ØB).",
                    size=11, color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=8,
        )
        self.table_header = ft.Row(
            [self._compact_header(), ft.VerticalDivider(width=8), self._compact_header()],
            spacing=0,
        )
        self.group_controls = ft.Row(
            [self.prev_group, self.group_label, self.next_group],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.controls = [self.tabbar, self.content_area]
        self.refresh(update=False)

    def _compact_header(self):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(ft.Text("Pair", weight=ft.FontWeight.BOLD), width=54),
                    ft.Container(ft.Text("Word", weight=ft.FontWeight.BOLD), expand=True),
                    ft.Container(ft.Text("Rating", weight=ft.FontWeight.BOLD), width=128),
                    ft.Container(ft.Text("Status", weight=ft.FontWeight.BOLD), width=72),
                    ft.Container(ft.Text("Active in", weight=ft.FontWeight.BOLD), width=90),
                ],
                spacing=6,
            ),
            padding=ft.Padding.symmetric(horizontal=6),
            expand=True,
        )

    def _on_tab_change(self, e):
        self.selected_view = "stats" if int(e.control.selected_index or 0) == 1 else "dictionary"
        self.refresh()

    def refresh(self, update: bool = True):
        self._sync_filters()
        if self.selected_view == "stats":
            self.content_area.controls = [self._build_stats_view()]
        else:
            self._refresh_dictionary()
            self.content_area.controls = [
                self.filters_area, self.group_controls, self.table_header,
                ft.Divider(height=1), self.rows_view,
            ]
        if update and self.page is not None:
            self.update()

    def _sync_filters(self):
        selected_scheme = self.scheme_filter.value or "__all__"
        if selected_scheme != "__all__" and selected_scheme not in self.state.data.schemes:
            self.scheme_filter.value = "__all__"
        self.scheme_filter.options = [ft.DropdownOption("__all__", "All letter schemes")] + [
            ft.DropdownOption(name, name) for name in self.state.scheme_names
        ]

        status_options = [
            ft.DropdownOption("all", "All pairs"),
            ft.DropdownOption("active", "Active"),
            ft.DropdownOption("inactive", "Inactive"),
            ft.DropdownOption("missing", "Missing words"),
        ]
        if self.state.has_outdated_pair_ratings:
            status_options.append(ft.DropdownOption("update_grades", "Update grades"))
        self.status_filter.options = status_options
        if self.status_filter.value == "update_grades" and not self.state.has_outdated_pair_ratings:
            self.status_filter.value = "all"

        # Grade sorting is based on grades that actually exist in saved data,
        # not on the currently-selected presentation system. This preserves old
        # ratings when users switch between numerical/color/qualitative modes.
        stored_grades = sorted(
            {round(float(v), 6) for v in self.state.data.pair_ratings.values()},
            reverse=True,
        )
        grade_options = [
            ft.DropdownOption("default", "Default"),
            ft.DropdownOption("highest", "Highest first"),
            ft.DropdownOption("lowest", "Lowest first"),
            ft.DropdownOption("ungraded", "Ungraded"),
        ]
        grade_options += [
            ft.DropdownOption(f"grade:{grade}", f"{grade:g}")
            for grade in stored_grades
        ]
        self.grade_sort.options = grade_options
        valid_values = {"default", "highest", "lowest", "ungraded"}
        valid_values.update(f"grade:{grade}" for grade in stored_grades)
        if self.grade_sort.value not in valid_values:
            self.grade_sort.value = "default"

    def _base_rows(self):
        selected_scheme = self.scheme_filter.value or "__all__"
        if selected_scheme == "__all__":
            active_pairs = get_active_pairs(self.state.data.schemes)
            all_pairs = (
                set(active_pairs)
                | set(self.state.data.global_words)
                | set(self.state.data.pair_aliases)
                | set(self.state.data.pair_ratings)
            )
        else:
            active_pairs = get_active_pairs(
                {selected_scheme: self.state.data.schemes[selected_scheme]}
            )
            all_pairs = set(active_pairs)

        query = (self.search_field.value or "").strip()
        status = self.status_filter.value or "all"
        rows = []
        for pair in sorted(all_pairs):
            is_active = pair in active_pairs
            word = self.state.get_word(pair)
            if status == "active" and not is_active:
                continue
            if status == "inactive" and is_active:
                continue
            if status == "missing" and (not is_active or bool(word.strip())):
                continue
            if status == "update_grades" and not self.state.pair_rating_needs_update(pair):
                continue
            if query and not self._matches_search(pair, word, query):
                continue
            rows.append((pair, word, is_active, active_pairs.get(pair, [])))

        grade_mode = self.grade_sort.value or "default"
        if grade_mode == "ungraded":
            rows = [
                row for row in rows
                if row[1].strip() and self.state.get_pair_rating(row[0]) is None
            ]
        elif grade_mode.startswith("grade:"):
            try:
                target = float(grade_mode.split(":", 1)[1])
            except ValueError:
                target = None
            if target is not None:
                rows = [
                    row for row in rows
                    if self.state.get_pair_rating(row[0]) is not None
                    and abs(float(self.state.get_pair_rating(row[0])) - target) < 0.011
                ]
        elif grade_mode in {"highest", "lowest"}:
            reverse = grade_mode == "highest"
            rated = [r for r in rows if self.state.get_pair_rating(r[0]) is not None]
            unrated = [r for r in rows if self.state.get_pair_rating(r[0]) is None]
            rated.sort(
                key=lambda r: float(self.state.get_pair_rating(r[0])),
                reverse=reverse,
            )
            rows = rated + unrated
        return rows, active_pairs

    def _refresh_dictionary(self):
        rows, active_pairs = self._base_rows()
        query = (self.search_field.value or "").strip()

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

        grouped_disabled = (
            bool(query)
            or (self.grade_sort.value or "default") != "default"
            or self.status_filter.value == "update_grades"
        )
        groups = sorted({pair[0].upper() for pair, *_ in rows if pair})
        self.available_groups = groups
        self._word_fields = []

        if grouped_disabled:
            page_rows = rows
            self.group_label.value = "Filtered results" if rows else "No matching pairs"
            self.prev_group.disabled = True
            self.next_group.disabled = True
            self.count_text.value = f"{len(rows)} matching across all letter groups"
        elif not groups:
            self.current_group = None
            page_rows = []
            self.group_label.value = "No matching pairs"
            self.prev_group.disabled = True
            self.next_group.disabled = True
            self.count_text.value = "0 matching pairs"
        else:
            if self.current_group not in groups:
                self.current_group = groups[0]
            group_index = groups.index(self.current_group)
            page_rows = [row for row in rows if row[0].upper().startswith(self.current_group)]
            self.group_label.value = f"{self.current_group} pairs"
            self.prev_group.disabled = group_index == 0
            self.next_group.disabled = group_index == len(groups) - 1
            self.count_text.value = f"{len(rows)} total · {len(page_rows)} on this page"

        filter_avg, filter_n = self._average_for_rows(page_rows)
        overall_rows = [
            (pair, word, True, [])
            for pair, word in self.state.data.global_words.items()
            if word.strip()
        ]
        overall_avg, overall_n = self._average_for_rows(overall_rows)
        self.filter_average_text.value = (
            f"Filter average: {filter_avg:.2f} ({filter_n} rated)"
            if filter_avg is not None else "Filter average: —"
        )
        self.overall_average_text.value = (
            f"Overall average: {overall_avg:.2f} ({overall_n} rated)"
            if overall_avg is not None else "Overall average: —"
        )

        cells = [self._build_compact_row(*row) for row in page_rows]
        split_at = (len(cells) + 1) // 2
        left, right = cells[:split_at], cells[split_at:]
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

    def _average_for_rows(self, items):
        values = []
        for pair, word, *_ in items:
            rating = self.state.get_pair_rating(pair)
            if word.strip() and rating is not None:
                values.append(float(rating))
        return (sum(values) / len(values), len(values)) if values else (None, 0)

    def _pair_search_match(self, value: str, query: str) -> bool:
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
            pair_match = (
                self._pair_search_match(pair, query)
                or self._pair_search_match(display, query)
            )
        if self.search_words.value:
            word_match = query.casefold() in word.casefold()
        return pair_match or word_match

    def _rating_control(self, pair: str, word: str):
        has_word = bool((word or "").strip())
        mode = self.state.data.letter_pair_rating_mode
        rating = self.state.get_pair_rating(pair)

        # A pair without a mnemonic cannot be graded yet. Render a simple
        # placeholder instead of disabled interactive controls. In current
        # Flet, GestureDetector must have at least one gesture handler, so a
        # handler-less disabled detector causes the red runtime error seen on web.
        if not has_word:
            return ft.Container(
                ft.Text("—", color=ft.Colors.ON_SURFACE_VARIANT),
                width=128,
                alignment=ft.Alignment.CENTER_LEFT,
            )

        if mode == "colors":
            grades = list(self.state.data.rating_color_grades)
            closest_grade = (
                min(grades, key=lambda grade: abs(float(rating) - float(grade)))
                if rating is not None and grades else None
            )
            controls = []
            for color, grade in zip(self.state.data.rating_color_hexes, grades):
                selected = (
                    closest_grade is not None
                    and abs(float(grade) - float(closest_grade)) < 0.001
                )
                controls.append(
                    ft.GestureDetector(
                        content=ft.Container(
                            width=17,
                            height=17,
                            bgcolor=color,
                            border_radius=9,
                            opacity=1.0,
                            border=(
                                ft.Border.all(2, ft.Colors.ON_SURFACE)
                                if selected else None
                            ),
                            tooltip=f"Grade {grade:g}",
                        ),
                        on_tap=lambda e, p=pair, g=grade: self._rating_changed(p, g),
                    )
                )
            controls.append(
                ft.IconButton(
                    ft.Icons.RESTART_ALT,
                    icon_size=16,
                    tooltip="Ungraded",
                    disabled=False,
                    on_click=lambda e, p=pair: self._rating_changed(p, None),
                )
            )
            return ft.Row(controls, spacing=2, width=128)

        if mode == "qualitative":
            value = "__none__"
            if rating is not None:
                value = "bad" if rating < 2 else ("mid" if rating < 4 else "good")
            return ft.Dropdown(
                width=112,
                dense=True,
                value=value,
                disabled=not has_word,
                options=[
                    ft.DropdownOption("__none__", "—"),
                    ft.DropdownOption("bad", "Bad"),
                    ft.DropdownOption("mid", "Mid"),
                    ft.DropdownOption("good", "Good"),
                ],
                on_select=lambda e, p=pair: self._rating_changed(
                    p, {"bad": 1, "mid": 3, "good": 5}.get(e.control.value)
                ),
            )

        value = "__none__" if rating is None else str(int(round(float(rating))))
        return ft.Dropdown(
            width=92,
            dense=True,
            value=value,
            disabled=not has_word,
            options=[ft.DropdownOption("__none__", "—")]
            + [ft.DropdownOption(str(i), str(i)) for i in range(1, 6)],
            on_select=lambda e, p=pair: self._rating_changed(p, e.control.value),
        )

    def _rating_changed(self, pair: str, value):
        self.state.set_pair_rating(pair, value)
        self.refresh()

    def _build_compact_row(self, pair: str, word: str, is_active: bool, sources: list[str]):
        field = ft.TextField(
            value=word,
            dense=True,
            height=34,
            border=ft.InputBorder.UNDERLINE,
            expand=True,
            on_change=lambda e, p=pair: self._word_changed(p, e.control.value),
            on_blur=lambda e, p=pair: self._word_committed(p, e.control.value),
            on_submit=lambda e, p=pair: self._word_submitted(p, e.control.value),
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
                    ft.Text(
                        display_pair,
                        weight=ft.FontWeight.BOLD,
                        tooltip=f"Underlying pair: {pair}",
                    ),
                    width=54,
                ),
                on_double_tap=lambda e, p=pair: self._edit_pair_alias(p),
            )

        status_chip = ft.Container(
            content=ft.Text(
                "Active" if is_active else "Inactive", size=12, color=ft.Colors.WHITE
            ),
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
                    ft.Container(self._rating_control(pair, word), width=128),
                    ft.Container(status_chip, width=72),
                    ft.Container(
                        ft.Text(
                            ", ".join(sources),
                            size=11,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            no_wrap=False,
                        ),
                        width=90,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
            ),
            padding=ft.Padding.symmetric(horizontal=6, vertical=0),
            bgcolor=None if is_active else ft.Colors.SURFACE_CONTAINER_LOW,
            opacity=1.0 if is_active else 0.75,
        )

    def _build_stats_view(self):
        rated = []
        for pair, word in self.state.data.global_words.items():
            if not word.strip():
                continue
            rating = self.state.get_pair_rating(pair)
            if rating is not None:
                rated.append((pair, word, float(rating)))

        by_letter = {}
        for pair, _, rating in rated:
            display = self.state.get_pair_display(pair).upper()
            for letter in set(ch for ch in display if ch.isalpha()):
                by_letter.setdefault(letter, []).append(rating)
        letter_stats = [
            (letter, sum(vals) / len(vals), len(vals))
            for letter, vals in by_letter.items() if vals
        ]
        strongest_letters = sorted(letter_stats, key=lambda x: (-x[1], x[0]))[:8]
        weakest_letters = sorted(letter_stats, key=lambda x: (x[1], x[0]))[:8]

        def letter_list(title, items):
            rows = [ft.Text(title, size=16, weight=ft.FontWeight.BOLD)]
            if not items:
                rows.append(ft.Text("No rated words yet.", color=ft.Colors.ON_SURFACE_VARIANT))
            for letter, avg, count in items:
                rows.append(
                    ft.Row([
                        ft.Text(letter, width=42, weight=ft.FontWeight.BOLD),
                        ft.Text(f"{avg:.2f}", width=50),
                        ft.Text(f"{count} rated pairs", color=ft.Colors.ON_SURFACE_VARIANT),
                    ])
                )
            return ft.Container(ft.Column(rows, spacing=5), expand=True, padding=10)

        return ft.Column(
            [
                ft.Text("Stats", size=20, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Letter statistics average every rated mnemonic whose displayed pair contains that letter.",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Row([
                    letter_list("Strongest letters", strongest_letters),
                    letter_list("Weakest letters", weakest_letters),
                ], vertical_alignment=ft.CrossAxisAlignment.START),
            ],
            spacing=10,
        )

    def _edit_pair_alias(self, pair: str):
        self._editing_alias_pair = pair
        self.refresh()

    def _save_pair_alias_inline(self, pair: str, value: str):
        if self._editing_alias_pair != pair:
            return
        self._editing_alias_pair = None
        self.state.set_pair_alias(pair, (value or "").upper())
        self.refresh()


    def _word_committed(self, pair: str, value: str):
        # Save one final time and rebuild the row so the Rating control appears
        # immediately when a mnemonic has been entered (or disappears again if
        # the word was cleared).  We intentionally do not rebuild on every
        # keystroke, which keeps browser typing responsive.
        self.state.set_word(pair, value)
        self.refresh()

    def _word_submitted(self, pair: str, value: str):
        # Enter commits the word, refreshes the row/rating UI, then advances to
        # the next word field when possible.
        self.state.set_word(pair, value)
        self.refresh()
        # The refresh rebuilds the field list, so move focus using the current
        # pair's rebuilt position rather than the old TextField control.
        try:
            rows, _ = self._base_rows()
            pair_order = [p for p, *_ in rows]
            idx = pair_order.index(pair)
            if idx + 1 < len(pair_order):
                next_pair = pair_order[idx + 1]
                # Only focus if the next pair is currently rendered on this page.
                rendered = [f for f in self._word_fields]
                # In normal A/B/C pages, rendered order matches current page rows.
                if rendered:
                    page_pairs = [p for p, *_ in rows if (
                        (self.current_group is None) or p.upper().startswith(self.current_group)
                    )]
                    if next_pair in page_pairs:
                        rendered[page_pairs.index(next_pair)].focus()
        except Exception:
            pass

    def _word_changed(self, pair: str, value: str):
        self.state.set_word(pair, value)
        self._update_duplicate_warning()
        self._refresh_average_labels_only()
        self.progress_text.update()
        self.progress_bar.update()
        self.duplicate_warning.update()
        self.filter_average_text.update()
        self.overall_average_text.update()

    def _refresh_average_labels_only(self):
        rows, active_pairs = self._base_rows()
        query = (self.search_field.value or "").strip()
        if (
            query
            or (self.grade_sort.value or "default") != "default"
            or self.status_filter.value == "update_grades"
        ):
            page_rows = rows
        elif self.current_group:
            page_rows = [r for r in rows if r[0].upper().startswith(self.current_group)]
        else:
            page_rows = rows

        active_total = len(active_pairs)
        completed = sum(1 for pair in active_pairs if self.state.get_word(pair).strip())
        remaining = active_total - completed
        percent = int(round((completed / active_total) * 100)) if active_total else 0
        self.progress_text.value = (
            f"Letter-pair dictionary: {completed} / {active_total} complete — "
            f"{remaining} remaining ({percent}%)"
        )
        self.progress_bar.value = completed / active_total if active_total else 0

        avg, n = self._average_for_rows(page_rows)
        overall_rows = [
            (pair, word, True, [])
            for pair, word in self.state.data.global_words.items()
            if word.strip()
        ]
        oavg, on = self._average_for_rows(overall_rows)
        self.filter_average_text.value = (
            f"Filter average: {avg:.2f} ({n} rated)" if avg is not None else "Filter average: —"
        )
        self.overall_average_text.value = (
            f"Overall average: {oavg:.2f} ({on} rated)" if oavg is not None else "Overall average: —"
        )

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
                shown_pairs = ", ".join(
                    self.state.get_pair_display(pair) for pair, _ in items
                )
                examples.append(f"{items[0][1]}: {shown_pairs}")
            more = " …" if len(duplicates) > 4 else ""
            self.duplicate_warning.value = (
                "⚠ Duplicate mnemonic words — " + "; ".join(examples) + more
            )
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
        if not self.search_pairs.value and not self.search_words.value:
            e.control.value = True
        self.search_field.hint_text = (
            "Search pair or word..."
            if self.search_words.value
            else "Search letter pairs (AC, A-, -S)..."
        )
        self.current_group = None
        self.refresh()

    def _on_search_change(self, e):
        self.current_group = None
        self.refresh()
