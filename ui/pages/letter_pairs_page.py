import flet as ft
from ui.theme_colors import ThemeAwarePage, show_themed_dialog

from core.pairs import get_active_pairs
from ui.design import panel


@ft.control
class LetterPairsPage(ThemeAwarePage, ft.Column):
    @property
    def state(self):
        return self.data

    def init(self):
        self.expand = True
        self.spacing = 8
        self._viewport = (1400.0, 760.0)
        self._table_columns = 2
        self._compact_cells = False
        self.selected_view = "dictionary"
        # Stats sub-sort: mnemonic length defaults to longest -> shortest.
        self.word_length_sort = "length_desc"

        self.tabbar = ft.Tabs(
            length=2,
            selected_index=0,
            on_change=self._on_tab_change,
            content=ft.TabBar(tabs=[ft.Tab(label="Dictionary"), ft.Tab(label="Stats")]),
        )
        self.tabbar.height = 40
        self.content_area = ft.Column(spacing=8)
        self.stats_scroll = ft.ListView(spacing=12, scroll=ft.ScrollMode.ALWAYS,
                                        build_controls_on_demand=False)

        self.search_field = ft.TextField(
            hint_text="Search letter pairs (AC, A-, -S)...",
            expand=True,
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._on_search_change,
            dense=True, height=42,
            border_radius=7,
        color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT), hint_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT))
        self.search_pairs = ft.Checkbox(
            label="Pairs", label_style=ft.TextStyle(size=12),
            visual_density=ft.VisualDensity.COMPACT,
            tooltip="Search letter pairs", value=True, on_change=self._on_search_mode_change
        )
        self.search_words = ft.Checkbox(
            label="Words", label_style=ft.TextStyle(size=12),
            visual_density=ft.VisualDensity.COMPACT,
            tooltip="Search within mnemonic words", value=False, on_change=self._on_search_mode_change
        )
        self.scheme_filter = ft.Dropdown(
            width=210, height=42, dense=True,
            value="__all__",
            label="Letter scheme",
            options=[ft.DropdownOption("__all__", "All schemes")],
            on_select=self._on_search_change,
        color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT), hint_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT))
        self.status_filter = ft.Dropdown(
            width=154, height=42, dense=True, value="all", label="Status", options=[], on_select=self._on_search_change
        , color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT), hint_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT))
        self.grade_sort = ft.Dropdown(
            width=164, height=42, dense=True, value="default", label="Sort by grade", options=[], on_select=self._on_search_change
        , color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT), hint_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT))
        self.progress_text = ft.Text(size=11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)
        self.duplicate_warning = ft.Text(size=11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.TERTIARY)
        self.progress_bar = ft.ProgressBar(width=100, value=0)
        self.count_text = ft.Text(size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.filter_average_text = ft.Text(size=11, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)
        self.overall_average_text = ft.Text(size=11, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.ON_SURFACE_VARIANT)

        # A stable ListView with an explicit height prevents rows from extending
        # past the browser viewport, including long filtered result sets.
        self.rows_view = ft.ListView(spacing=0, scroll=ft.ScrollMode.ALWAYS,
                                    build_controls_on_demand=False)
        self.current_group: str | None = "A"
        self.available_groups: list[str] = []
        self.group_label = ft.Text("A pairs", weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)
        self.prev_group = ft.IconButton(ft.Icons.CHEVRON_LEFT, tooltip="Previous letter", on_click=self._previous_group)
        self.next_group = ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Next letter", on_click=self._next_group)
        self._word_fields: list[ft.TextField] = []
        self._editing_alias_pair: str | None = None

        self.search_modes = ft.Row([
            ft.Text("Search in", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            self.search_pairs, self.search_words,
        ], spacing=4, width=240, height=32)
        self.progress_line = ft.Row([self.progress_text, self.progress_bar], spacing=12, height=22)
        self.summary_line = ft.Row([
            self.filter_average_text, self.overall_average_text,
            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT,
                    tooltip="Double-click a pair label to edit its display alias (for example AB → ØB)."),
        ], spacing=12, height=22)
        self.filters_area = ft.Column(spacing=6)
        self.filters_panel = panel(self.filters_area, padding=10)
        self.table_header = ft.Row(spacing=16, height=28)
        self.group_controls = ft.Row([
            ft.Row([self.prev_group, self.group_label, self.next_group], spacing=4, tight=True),
            self.count_text,
        ], height=32, alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
           vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.heading_description = ft.Text("Build, rate, and refine your mnemonic dictionary.",
                                           size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.heading = ft.Container(ft.Row([
            ft.Text("Letter Pairs", size=24, weight=ft.FontWeight.W_600,
                    color=ft.Colors.ON_SURFACE, expand=True),
            self.heading_description,
        ], spacing=16), height=42)
        self.controls = [self.heading, self.tabbar, self.content_area]
        self._layout_viewport()
        self.refresh(update=False)

    def set_viewport(self, width, height):
        old_mode = (self._table_columns, self._compact_cells)
        self._viewport = (max(280.0, float(width)), max(320.0, float(height)))
        self._table_columns = 2 if self._viewport[0] >= 1100 else 1
        self._compact_cells = self._viewport[0] < 600
        if self.selected_view == "stats" or old_mode != (self._table_columns, self._compact_cells):
            self.refresh(update=False)
        else:
            self._layout_viewport()

    def _layout_viewport(self):
        width, height = self._viewport
        self.width = width
        self.heading.width = width
        self.heading_description.visible = width >= 800
        self.tabbar.width = width
        self.content_area.width = width
        self.content_area.height = height - 98
        self.filters_panel.width = width
        inner = width - 20
        self.search_field.expand = True
        self.search_modes.expand = False
        self.progress_line.expand = True
        for control in (self.scheme_filter, self.status_filter, self.grade_sort):
            control.expand = False
        if width >= 800:
            self.scheme_filter.width, self.status_filter.width, self.grade_sort.width = 210, 154, 164
            self.filters_area.controls = [
                ft.Row([self.search_field, self.scheme_filter, self.status_filter, self.grade_sort],
                       spacing=10, height=42),
                ft.Row([self.search_modes, self.progress_line], spacing=16, height=32),
                self.summary_line,
            ]
            filter_height = 128
        else:
            self.progress_line.expand = False
            for control in (self.scheme_filter, self.status_filter, self.grade_sort):
                control.width = (inner - 16) / 3
            self.filters_area.controls = [
                ft.Row([self.search_field], height=42),
                ft.Row([self.scheme_filter, self.status_filter, self.grade_sort], spacing=8, height=42),
                self.search_modes, self.progress_line, self.summary_line,
            ]
            filter_height = 204
        self.duplicate_warning.visible = bool(self.duplicate_warning.value)
        if self.duplicate_warning.visible:
            self.filters_area.controls.append(self.duplicate_warning)
            filter_height += 22
        self.duplicate_warning.tooltip = self.duplicate_warning.value or None
        self.progress_text.tooltip = self.progress_text.value or None
        self.filter_average_text.tooltip = self.filter_average_text.value or None
        self.overall_average_text.tooltip = self.overall_average_text.value or None
        self.filters_panel.height = filter_height
        self.filters_area.width = inner
        self.summary_line.width = inner
        self.group_controls.width = width
        self.table_header.width = width
        self.rows_view.width = width
        self.rows_view.height = max(24, self.content_area.height - filter_height - 32 - 28 - 24)
        self.stats_scroll.width = width
        self.stats_scroll.height = self.content_area.height
        if self.selected_view == "stats":
            self.content_area.controls = [self.stats_scroll]
        else:
            self.content_area.controls = [self.filters_panel, self.group_controls, self.table_header, self.rows_view]

    def _compact_header(self):
        if self._compact_cells:
            return ft.Text("Pair / mnemonic", size=12, weight=ft.FontWeight.W_600,
                           color=ft.Colors.ON_SURFACE)
        return ft.Container(
            ft.Row([
                ft.Container(ft.Text("Pair", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE), width=48),
                ft.Container(ft.Text("Word", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE), expand=True),
                ft.Container(ft.Text("Rating", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE), width=122),
                ft.Container(ft.Text("Status", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE), width=72),
                ft.Container(ft.Text("Active in", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE), width=110),
            ], spacing=6), expand=True,
            padding=ft.Padding.symmetric(horizontal=6),
        )

    def _on_tab_change(self, e):
        self.selected_view = "stats" if int(e.control.selected_index or 0) == 1 else "dictionary"
        self.refresh()

    def refresh(self, update: bool = True):
        self._sync_filters()
        if self.selected_view == "stats":
            self.stats_scroll.controls = [self._build_stats_view()]
        else:
            self._refresh_dictionary()
        self._layout_viewport()
        if update and self.page is not None:
            self.update()

    def _sync_filters(self):
        selected_scheme = self.scheme_filter.value or "__all__"
        if selected_scheme != "__all__" and selected_scheme not in self.state.data.schemes:
            self.scheme_filter.value = "__all__"
        self.scheme_filter.options = [ft.DropdownOption("__all__", "All schemes")] + [
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
            f"{completed}/{active_total} complete · {percent}% · {remaining} left"
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
            f"Filtered rating average: {filter_avg:.2f} ({filter_n} rated)"
            if filter_avg is not None else "Filtered rating average: —"
        )
        self.overall_average_text.value = (
            f"Overall rating average: {overall_avg:.2f} ({overall_n} rated)"
            if overall_avg is not None else "Overall rating average: —"
        )

        cells = [self._build_compact_row(*row) for row in page_rows]
        self.table_header.controls = [self._compact_header() for _ in range(self._table_columns)]
        if self._table_columns == 2:
            split_at = (len(cells) + 1) // 2
            left, right = cells[:split_at], cells[split_at:]
            visual_rows = [
                ft.Row([left[i], right[i] if i < len(right) else ft.Container(expand=True)],
                       spacing=16, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                for i in range(split_at)
            ]
        else:
            for cell in cells:
                cell.expand = False
            visual_rows = cells
        self.rows_view.controls = visual_rows or [
            ft.Container(ft.Text("No matching letter pairs.", color=ft.Colors.ON_SURFACE_VARIANT), padding=16)
        ]

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
                ft.Text("—", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                width=118,
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
                    icon_size=16, width=28, height=28,
                    tooltip="Ungraded",
                    disabled=False,
                    on_click=lambda e, p=pair: self._rating_changed(p, None),
                )
            )
            return ft.Row(controls, spacing=1, width=118)

        if mode == "qualitative":
            value = "__none__"
            if rating is not None:
                value = "bad" if rating < 2 else ("mid" if rating < 4 else "good")
            return ft.Dropdown(
                width=104, height=32, text_size=12,
                dense=True, content_padding=ft.Padding.symmetric(horizontal=8, vertical=0),
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
            color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT), hint_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT))

        value = "__none__" if rating is None else str(int(round(float(rating))))
        return ft.Dropdown(
            width=84, height=32, text_size=12,
            dense=True, content_padding=ft.Padding.symmetric(horizontal=8, vertical=0),
            value=value,
            disabled=not has_word,
            options=[ft.DropdownOption("__none__", "—")]
            + [ft.DropdownOption(str(i), str(i)) for i in range(1, 6)],
            on_select=lambda e, p=pair: self._rating_changed(p, e.control.value),
        color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT), hint_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT))

    def _rating_changed(self, pair: str, value):
        self.state.set_pair_rating(pair, value)
        self.refresh()

    def _build_compact_row(self, pair: str, word: str, is_active: bool, sources: list[str]):
        field = ft.TextField(
            value=word,
            dense=True,
            height=32,
            text_size=12,
            content_padding=ft.Padding.symmetric(horizontal=0, vertical=3),
            border=ft.InputBorder.UNDERLINE,
            expand=True,
            on_change=lambda e, p=pair: self._word_changed(p, e.control.value),
            on_blur=lambda e, p=pair: self._word_committed(p, e.control.value),
            on_submit=lambda e, p=pair: self._word_submitted(p, e.control.value),
        color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT), hint_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT))
        self._word_fields.append(field)

        display_pair = self.state.get_pair_display(pair)
        if self._editing_alias_pair == pair:
            pair_label = ft.Container(
                ft.TextField(
                    value=display_pair,
                    width=46,
                    dense=True,
                    autofocus=True,
                    max_length=8,
                    capitalization=ft.TextCapitalization.CHARACTERS,
                    tooltip=f"Underlying pair: {pair}",
                    on_blur=lambda e, p=pair: self._save_pair_alias_inline(p, e.control.value),
                    on_submit=lambda e, p=pair: self._save_pair_alias_inline(p, e.control.value),
                color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT), hint_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT)),
                width=48,
            )
        else:
            pair_label = ft.GestureDetector(
                content=ft.Container(
                    ft.Text(
                        display_pair,
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        tooltip=f"Underlying pair: {pair}",
                    color=ft.Colors.ON_SURFACE),
                    width=48,
                ),
                on_double_tap=lambda e, p=pair: self._edit_pair_alias(p),
            )

        status_chip = ft.Container(
            content=ft.Text(
                "Active" if is_active else "Inactive", size=10, color=ft.Colors.ON_PRIMARY_CONTAINER if is_active else ft.Colors.ON_SURFACE_VARIANT
            ),
            bgcolor=ft.Colors.PRIMARY_CONTAINER if is_active else ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=ft.Padding.symmetric(horizontal=6, vertical=1),
            border_radius=12,
        )
        sources_text = ft.Text(
            ", ".join(sources), size=10, max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.ON_SURFACE_VARIANT,
            tooltip=", ".join(sources) or "Not active in a scheme",
        )
        rating = self._rating_control(pair, word)
        if self._compact_cells:
            body = ft.Column([
                ft.Row([pair_label, ft.Container(field, expand=True)], spacing=8),
                ft.Row([ft.Container(rating, width=122), status_chip,
                        ft.Container(sources_text, expand=True)], spacing=8),
            ], spacing=3)
        else:
            body = ft.Row([
                pair_label, ft.Container(field, expand=True),
                ft.Container(rating, width=122),
                ft.Container(status_chip, width=72),
                ft.Container(sources_text, width=110),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6)
        return ft.Container(
            expand=True, content=body,
            padding=ft.Padding.symmetric(horizontal=6, vertical=3),
            border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
            bgcolor=None if is_active else ft.Colors.SURFACE_CONTAINER_LOW,
            opacity=1.0 if is_active else 0.75,
        )

    def _scheme_letters(self, scheme):
        return sorted({
            (letter or "").strip().upper()
            for category in (scheme.corners, scheme.edges)
            for letter in category.stickers.values()
            if (letter or "").strip() and (letter or "").strip().upper() != "BUFFER"
        }, key=self._letter_sort_key)

    @staticmethod
    def _letter_sort_key(letter: str):
        """Stable alphabetic ordering with Danish Æ/Ø/Å after Z.

        Other characters fall back to Unicode/casefold ordering, so custom
        alphabets remain deterministic without needing browser locale support.
        """
        order = "ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅ"
        upper = (letter or "").upper()
        if upper in order:
            return (0, order.index(upper))
        return (1, upper.casefold())

    @staticmethod
    def _mnemonic_length(word: str) -> int:
        # Spaces and punctuation do not inflate the statistic. Unicode letters
        # and digits (including Æ/Ø/Å) count naturally through isalnum().
        return sum(1 for ch in (word or "") if ch.isalnum())

    def _toggle_length_sort(self, e):
        self.word_length_sort = (
            "length_asc" if self.word_length_sort == "length_desc" else "length_desc"
        )
        self.refresh()

    def _toggle_alpha_sort(self, e):
        self.word_length_sort = (
            "alpha_desc" if self.word_length_sort == "alpha_asc" else "alpha_asc"
        )
        self.refresh()

    def _rank_rows_two_columns(self, items, row_builder):
        if not items:
            return ft.Text("No data yet.", color=ft.Colors.ON_SURFACE_VARIANT)
        cells = [row_builder(index, item) for index, item in enumerate(items, start=1)]
        split_at = (len(cells) + 1) // 2
        left = ft.Column(cells[:split_at], spacing=1, expand=True)
        right = ft.Column(cells[split_at:], spacing=1, expand=True)
        return ft.Row(
            [left, ft.VerticalDivider(width=12), right],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    def _build_stats_view(self):
        scheme = self.state.active_scheme
        if scheme is None:
            return ft.Column([
                ft.Text("Stats", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Text("Create or select a letter scheme to see letter statistics.", color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=10)

        scheme_letters = self._scheme_letters(scheme)

        # --- Average quality rating by scheme letter -----------------------
        by_letter_rating = {letter: [] for letter in scheme_letters}
        for pair, word in self.state.data.global_words.items():
            if not word.strip():
                continue
            rating = self.state.get_pair_rating(pair)
            if rating is None:
                continue
            canonical = (pair or "").upper()
            for letter in scheme_letters:
                if letter in canonical:
                    by_letter_rating[letter].append(float(rating))

        rating_ranked = []
        for letter in scheme_letters:
            values = by_letter_rating.get(letter, [])
            avg = (sum(values) / len(values)) if values else None
            rating_ranked.append((letter, avg, len(values)))
        rating_ranked.sort(
            key=lambda item: (
                item[1] is None,
                -(item[1] or 0),
                self._letter_sort_key(item[0]),
            )
        )

        def rating_row(index, item):
            letter, avg, count = item
            return ft.Container(
                content=ft.Row([
                    ft.Text(f"{index}.", width=28, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(letter, width=36, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Text(f"{avg:.2f}" if avg is not None else "—", width=48, color=ft.Colors.ON_SURFACE),
                    ft.Text(f"{count}" if count else "—", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=4),
                padding=ft.Padding.symmetric(horizontal=4, vertical=1),
            )

        # --- Average mnemonic-word length by scheme letter -----------------
        by_letter_length = {letter: [] for letter in scheme_letters}
        for pair, word in self.state.data.global_words.items():
            clean = (word or "").strip()
            if not clean:
                continue
            canonical = (pair or "").upper()
            length = self._mnemonic_length(clean)
            for letter in scheme_letters:
                if letter in canonical:
                    by_letter_length[letter].append(length)

        length_rows = []
        for letter in scheme_letters:
            values = by_letter_length.get(letter, [])
            avg = (sum(values) / len(values)) if values else None
            length_rows.append((letter, avg, len(values)))

        if self.word_length_sort == "length_desc":
            length_rows.sort(key=lambda x: (x[1] is None, -(x[1] or 0), self._letter_sort_key(x[0])))
        elif self.word_length_sort == "length_asc":
            length_rows.sort(key=lambda x: (x[1] is None, x[1] if x[1] is not None else 0, self._letter_sort_key(x[0])))
        elif self.word_length_sort == "alpha_desc":
            length_rows.sort(key=lambda x: self._letter_sort_key(x[0]), reverse=True)
        else:  # alpha_asc
            length_rows.sort(key=lambda x: self._letter_sort_key(x[0]))

        def length_row(index, item):
            letter, avg, count = item
            return ft.Container(
                content=ft.Row([
                    ft.Text(f"{index}.", width=28, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(letter, width=36, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Text(f"{avg:.2f}" if avg is not None else "—", width=48, color=ft.Colors.ON_SURFACE),
                    ft.Text(f"{count}" if count else "—", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=4),
                padding=ft.Padding.symmetric(horizontal=4, vertical=1),
            )

        length_label = "Length ↓" if self.word_length_sort == "length_desc" else "Length ↑"
        alpha_label = "Alphabetical Z–A" if self.word_length_sort == "alpha_desc" else "Alphabetical A–Z"
        if self.word_length_sort.startswith("alpha"):
            # Keep the inactive length button's label showing its default direction.
            length_label = "Length ↓"
        if self.word_length_sort.startswith("length"):
            alpha_label = "Alphabetical A–Z"

        rating_section = ft.Container(
            content=ft.Column([
                ft.Text("Letter ratings", weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Text(
                    "All letters used in the active scheme, ranked by average pair rating.",
                    size=11, color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                self._rank_rows_two_columns(rating_ranked, rating_row),
            ], spacing=4),
            expand=True,
            padding=ft.Padding.all(8),
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
        )

        length_section = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Average mnemonic length", weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.OutlinedButton(length_label, on_click=self._toggle_length_sort),
                    ft.OutlinedButton(alpha_label, on_click=self._toggle_alpha_sort),
                ], wrap=True, spacing=6),
                ft.Text(
                    "Average letters/numbers in mnemonic words for pairs containing each scheme letter.",
                    size=11, color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                self._rank_rows_two_columns(length_rows, length_row),
            ], spacing=4),
            expand=True,
            padding=ft.Padding.all(8),
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
        )

        width = self._viewport[0]
        if width >= 900:
            sections = ft.Row([rating_section, length_section], spacing=12,
                              vertical_alignment=ft.CrossAxisAlignment.START)
        else:
            for section in (rating_section, length_section):
                section.expand = False
                section.width = width
            sections = ft.Column([rating_section, length_section], spacing=12)
        return ft.Column([
            ft.Text(f"Statistics for {scheme.name}.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            sections,
        ], spacing=12, width=width)

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
        # Only sizing/labels change during typing; keep the current fields
        # mounted and preserve their focus while counters or warnings update.
        self._layout_viewport()
        if self.page is not None:
            self.update()

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
            f"{completed}/{active_total} complete · {percent}% · {remaining} left"
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
            f"Filtered rating average: {avg:.2f} ({n} rated)" if avg is not None else "Filtered rating average: —"
        )
        self.overall_average_text.value = (
            f"Overall rating average: {oavg:.2f} ({on} rated)" if oavg is not None else "Overall rating average: —"
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
