from dataclasses import field
import flet as ft

from core.cube_definitions import CATEGORY_PIECES, CATEGORY_STICKER_ORDER
from core.tracer import STANDARD_CORNER_PRIORITY, STANDARD_EDGE_PRIORITY
from ui.components.buffer_picker import build_buffer_picker
from ui.components.sticker_grid import build_sticker_grid
from ui.state import AppState


COLOR_LABELS = {
    "W": "White",
    "Y": "Yellow",
    "G": "Green",
    "B": "Blue",
    "R": "Red",
    "O": "Orange",
}
OPPOSITE = {"W": "Y", "Y": "W", "G": "B", "B": "G", "R": "O", "O": "R"}


@ft.control
class LetterSchemesPage(ft.Column):
    state: AppState | None = field(default=None, metadata={"skip": True})

    def init(self):
        self.expand = True
        self.spacing = 0
        # Edges first is only a UI/data-entry preference. It does not affect
        # memo/execution order.
        self.selected_category = "edges"
        self.new_scheme_field = ft.TextField(hint_text="New scheme name", width=200, on_submit=self._create_scheme)
        self.rename_field = ft.TextField(hint_text="Rename active scheme", width=200, on_submit=self._rename_scheme)
        self.scheme_list_view = ft.ListView(expand=True, spacing=2)
        # Keep one scrollable body control mounted for the lifetime of the
        # page. Replacing the whole Column on every setting change reset its
        # scroll position to the top, which made Advanced settings painful to
        # edit. Updating its controls in place preserves the viewport.
        self.body_scroll = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
        self.body_area = ft.Container(expand=True, padding=16, content=self.body_scroll)
        self.settings_message = ft.Text("", size=12, color=ft.Colors.ERROR)
        self._advanced_expanded = False
        self._category_advanced_expanded = {"corners": False, "edges": False}
        self.controls = [self._build_layout()]
        self.refresh(update=False)

    # ---- layout -------------------------------------------------------------

    def _build_layout(self) -> ft.Control:
        sidebar = ft.Container(
            width=260,
            padding=12,
            border=ft.Border.only(right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
            content=ft.Column(
                [
                    ft.Text("Schemes", weight=ft.FontWeight.BOLD, size=16),
                    ft.Row([self.new_scheme_field, ft.IconButton(ft.Icons.ADD, on_click=self._create_scheme, tooltip="Create scheme")]),
                    ft.Divider(),
                    self.scheme_list_view,
                ],
                expand=True,
            ),
        )
        return ft.Row([sidebar, self.body_area], expand=True)

    # ---- refresh ------------------------------------------------------------

    def refresh(self, update: bool = True):
        self._refresh_scheme_list()
        self._refresh_body()
        if update:
            self.update()

    def _refresh_scheme_list(self):
        active = self.state.active_scheme
        self.scheme_list_view.controls = []
        for name in self.state.scheme_names:
            is_active = active is not None and active.name == name
            self.scheme_list_view.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(name, weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL, expand=True),
                            ft.IconButton(ft.Icons.CONTENT_COPY, icon_size=16, tooltip="Duplicate",
                                          on_click=lambda e, n=name: self._duplicate_scheme(n)),
                            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=16, tooltip="Delete",
                                          on_click=lambda e, n=name: self._delete_scheme(n)),
                        ],
                        spacing=0,
                    ),
                    padding=8,
                    border_radius=6,
                    bgcolor=ft.Colors.PRIMARY_CONTAINER if is_active else None,
                    on_click=lambda e, n=name: self._switch_scheme(n),
                )
            )

    def _refresh_body(self):
        scheme = self.state.active_scheme
        if scheme is None:
            self.body_scroll.controls = [ft.Text("Create a scheme to get started.", italic=True)]
            return

        cat = scheme.corners if self.selected_category == "corners" else scheme.edges

        tabs = ft.Tabs(
            length=2,
            selected_index=0 if self.selected_category == "corners" else 1,
            on_change=self._on_tab_change,
            content=ft.TabBar(
                tabs=[
                    ft.Tab(label="Corners"),
                    ft.Tab(label="Edges"),
                ]
            ),
        )

        buffer_picker = build_buffer_picker(
            self.selected_category, cat.buffer_sticker,
            lambda sticker: self._set_buffer(sticker),
        )

        grid = build_sticker_grid(
            self.selected_category, cat,
            lambda sticker, value: self._set_letter(sticker, value),
        )

        self.body_scroll.controls = [
            ft.Row(
                [
                    ft.Text(scheme.name, size=20, weight=ft.FontWeight.BOLD),
                    self.rename_field,
                    ft.IconButton(ft.Icons.CHECK, tooltip="Rename", on_click=self._rename_scheme),
                ]
            ),
            self._build_orientation_settings(scheme),
            tabs,
            ft.Row([buffer_picker]),
            ft.Container(content=grid, padding=ft.Padding.only(top=12)),
            ft.Divider(),
            self._build_advanced_settings(scheme),
            self.settings_message,
        ]

    def _build_orientation_settings(self, scheme):
        front_options = [c for c in COLOR_LABELS if c not in {scheme.memo_up, OPPOSITE[scheme.memo_up]}]
        if scheme.memo_front not in front_options:
            # Old/invalid data should never strand the UI.
            front_options = [c for c in COLOR_LABELS if c not in {scheme.memo_up, OPPOSITE[scheme.memo_up]}]

        up = ft.Dropdown(
            label="Top color",
            width=150,
            value=scheme.memo_up,
            options=[ft.DropdownOption(c, COLOR_LABELS[c]) for c in COLOR_LABELS],
            on_select=self._orientation_up_changed,
        )
        front = ft.Dropdown(
            label="Front color",
            width=150,
            value=scheme.memo_front if scheme.memo_front in front_options else front_options[0],
            options=[ft.DropdownOption(c, COLOR_LABELS[c]) for c in front_options],
            on_select=self._orientation_front_changed,
        )
        return ft.Row([
            ft.Text("Memo orientation", weight=ft.FontWeight.BOLD),
            up,
            front,
        ], wrap=True)

    def _build_advanced_settings(self, scheme):
        memo_field = ft.TextField(
            label="Memo",
            hint_text="CE",
            value=scheme.memo_order,
            width=90,
            max_length=2,
            on_submit=lambda e: self._save_order("memo", e.control),
            on_blur=lambda e: self._save_order("memo", e.control),
        )
        exec_field = ft.TextField(
            label="Exec",
            hint_text="EC",
            value=scheme.execution_order,
            width=90,
            max_length=2,
            on_submit=lambda e: self._save_order("execution", e.control),
            on_blur=lambda e: self._save_order("execution", e.control),
        )

        return ft.ExpansionTile(
            initially_expanded=self._advanced_expanded,
            title=ft.Text("Advanced settings"),
            subtitle=ft.Text("Cycle breaks, twist/flip handling, and memo/execution order", size=12),
            controls=[
                ft.Container(
                    padding=ft.Padding.only(left=16, right=16, bottom=12),
                    content=ft.Column([
                        ft.Row([
                            ft.Text("Order", weight=ft.FontWeight.BOLD),
                            memo_field,
                            ft.Text("/"),
                            exec_field,
                            ft.Text("Blank = standard CE / EC", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], wrap=True),
                        self._build_category_advanced(scheme, "corners"),
                        self._build_category_advanced(scheme, "edges"),
                    ], spacing=8),
                )
            ],
        )

    def _build_category_advanced(self, scheme, category: str):
        cat = scheme.corners if category == "corners" else scheme.edges
        title = "Corners" if category == "corners" else "Edges"
        noun = "twists" if category == "corners" else "flips"
        mode = ft.Dropdown(
            label=f"{noun.capitalize()} handling",
            width=235,
            value=cat.orientation_memo,
            options=[
                ft.DropdownOption("visual", f"Visualize {noun}"),
                ft.DropdownOption("trace", f"Trace / shoot {noun}"),
            ],
            on_select=lambda e, c=category: self._orientation_mode_changed(c, e.control.value),
        )

        mode_label = "Standard" if cat.tracing_mode == "standard" else "Custom"
        rows = self._build_cycle_break_rows(scheme, category)
        return ft.ExpansionTile(
            initially_expanded=self._category_advanced_expanded.get(category, False),
            title=ft.Text(f"{title} tracing — {mode_label}"),
            controls=[
                ft.Container(
                    padding=ft.Padding.only(left=16, right=16, bottom=12),
                    content=ft.Column([
                        ft.Row([
                            mode,
                            ft.OutlinedButton(
                                "Reset to Standard",
                                icon=ft.Icons.RESTART_ALT,
                                on_click=lambda e, c=category: self._reset_tracing(c),
                            ),
                        ], wrap=True),
                        ft.Text(
                            "For each physical piece, choose the sticker you prefer to shoot to, then rank the pieces. "
                            "When a cycle break is needed, the first still-unsolved piece in this list is chosen.",
                            size=11,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Column(rows, spacing=4),
                    ], spacing=8),
                )
            ],
        )

    def _effective_priority(self, scheme, category: str):
        cat = scheme.corners if category == "corners" else scheme.edges
        standard = STANDARD_CORNER_PRIORITY if category == "corners" else STANDARD_EDGE_PRIORITY
        pieces = CATEGORY_PIECES[category]
        buffer_piece = cat.buffer_piece
        base = list(cat.cycle_break_priority) if cat.cycle_break_priority else list(standard)
        result = []
        for p in base + list(pieces.keys()):
            if p in pieces and p != buffer_piece and p not in result:
                result.append(p)
        return result

    def _build_cycle_break_rows(self, scheme, category: str):
        cat = scheme.corners if category == "corners" else scheme.edges
        pieces = CATEGORY_PIECES[category]
        order = CATEGORY_STICKER_ORDER[category]
        priority = self._effective_priority(scheme, category)
        rows = []
        for i, piece in enumerate(priority):
            stickers = sorted(pieces[piece], key=lambda s: order.index(s))
            preferred = cat.cycle_break_stickers.get(piece, piece)
            if preferred not in pieces[piece]:
                preferred = stickers[0]
            options = []
            for sticker in stickers:
                letter = cat.stickers.get(sticker, "")
                label = f"{sticker} ({letter})" if letter and letter != "BUFFER" else sticker
                options.append(ft.DropdownOption(sticker, label))
            rows.append(
                ft.Row([
                    ft.Container(ft.Text(f"{i + 1}. {piece}", weight=ft.FontWeight.BOLD), width=85),
                    ft.Dropdown(
                        label="Preferred sticker",
                        width=170,
                        value=preferred,
                        options=options,
                        on_select=lambda e, c=category, p=piece: self._cycle_sticker_changed(c, p, e.control.value),
                    ),
                    ft.IconButton(
                        ft.Icons.ARROW_UPWARD,
                        tooltip="Higher priority",
                        disabled=i == 0,
                        on_click=lambda e, c=category, idx=i: self._move_priority(c, idx, -1),
                    ),
                    ft.IconButton(
                        ft.Icons.ARROW_DOWNWARD,
                        tooltip="Lower priority",
                        disabled=i == len(priority) - 1,
                        on_click=lambda e, c=category, idx=i: self._move_priority(c, idx, 1),
                    ),
                ], spacing=4)
            )
        return rows

    # ---- event handlers -----------------------------------------------------

    def _create_scheme(self, e):
        name = self.new_scheme_field.value.strip()
        if not name:
            return
        self.state.create_scheme(name)
        self.selected_category = "edges"
        self.new_scheme_field.value = ""
        self.refresh()

    def _rename_scheme(self, e):
        scheme = self.state.active_scheme
        new_name = self.rename_field.value.strip()
        if scheme is None or not new_name:
            return
        self.state.rename_scheme(scheme.name, new_name)
        self.rename_field.value = ""
        self.refresh()

    def _duplicate_scheme(self, name: str):
        self.state.duplicate_scheme(name)
        self.refresh()

    def _delete_scheme(self, name: str):
        self.state.delete_scheme(name)
        self.refresh()

    def _switch_scheme(self, name: str):
        self.state.switch_scheme(name)
        self.refresh()

    def _on_tab_change(self, e):
        self.selected_category = "corners" if e.control.selected_index == 0 else "edges"
        self._refresh_body()
        self.update()

    def _set_buffer(self, buffer_sticker: str):
        scheme = self.state.active_scheme
        if scheme is None:
            return
        self.state.set_buffer(scheme, self.selected_category, buffer_sticker)
        self._refresh_body()
        self.update()

    def _set_letter(self, sticker: str, value: str):
        scheme = self.state.active_scheme
        if scheme is None:
            return
        # Deliberately does NOT rebuild the grid here: rebuilding on every
        # keystroke would steal focus from the field the user is typing in.
        self.state.set_sticker_letter(scheme, self.selected_category, sticker, value)

    def _orientation_up_changed(self, e):
        scheme = self.state.active_scheme
        if scheme is None:
            return
        up = e.control.value
        front = scheme.memo_front
        if front in {up, OPPOSITE[up]}:
            front = next(c for c in COLOR_LABELS if c not in {up, OPPOSITE[up]})
        self.state.set_memo_orientation(scheme, up, front)
        self.settings_message.value = ""
        self._refresh_body()
        self.update()

    def _orientation_front_changed(self, e):
        scheme = self.state.active_scheme
        if scheme is None:
            return
        if not self.state.set_memo_orientation(scheme, scheme.memo_up, e.control.value):
            self.settings_message.value = "Top and front colors must be adjacent."
        else:
            self.settings_message.value = ""
        self._refresh_body()
        self.update()

    def _save_order(self, kind: str, control: ft.TextField):
        scheme = self.state.active_scheme
        if scheme is None:
            return
        value = (control.value or "").strip().upper()
        control.value = value
        if not self.state.set_order(scheme, kind, value):
            self.settings_message.value = "Order must be CE, EC, or left blank for the standard."
            control.error_text = "Use CE or EC"
        else:
            self.settings_message.value = ""
            control.error_text = None
        if control.page is not None:
            control.update()
        if self.settings_message.page is not None:
            self.settings_message.update()

    def _orientation_mode_changed(self, category: str, value: str):
        scheme = self.state.active_scheme
        if scheme is None:
            return
        self._advanced_expanded = True
        self._category_advanced_expanded[category] = True
        self.state.set_orientation_memo_mode(scheme, category, value)
        self.refresh()

    def _cycle_sticker_changed(self, category: str, piece: str, sticker: str):
        scheme = self.state.active_scheme
        if scheme is None:
            return
        self._advanced_expanded = True
        self._category_advanced_expanded[category] = True
        self.state.set_cycle_break_sticker(scheme, category, piece, sticker)
        self.refresh()

    def _move_priority(self, category: str, index: int, delta: int):
        scheme = self.state.active_scheme
        if scheme is None:
            return
        priority = self._effective_priority(scheme, category)
        other = index + delta
        if other < 0 or other >= len(priority):
            return
        priority[index], priority[other] = priority[other], priority[index]
        self._advanced_expanded = True
        self._category_advanced_expanded[category] = True
        self.state.set_cycle_break_priority(scheme, category, priority)
        self.refresh()

    def _reset_tracing(self, category: str):
        scheme = self.state.active_scheme
        if scheme is None:
            return
        self._advanced_expanded = True
        self._category_advanced_expanded[category] = True
        self.state.reset_tracing_preferences(scheme, category)
        self.refresh()
