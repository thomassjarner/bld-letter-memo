import flet as ft
from ui.theme_colors import ThemeAwarePage, show_themed_dialog

from core.tracer import ScrambleTracer, ScrambleError
from ui.design import page_heading, panel, eyebrow


# Chosen for legibility in both themes. The dark palette is intentionally
# lighter because it is used as foreground text on a dark surface.
# Separate palettes are used because the same foreground colors do not have
# equal contrast on light and dark surfaces.  Orientation targets deliberately
# use blue rather than teal so they cannot be confused with cycle 1 green.
LIGHT_CYCLE_COLORS = ("#2E7D32", "#A85D00", "#C62828", "#6A1B9A")
DARK_CYCLE_COLORS = ("#66BB6A", "#FFD54F", "#EF5350", "#BA68C8")
LIGHT_ORIENTATION_COLOR = "#1565C0"
DARK_ORIENTATION_COLOR = "#42A5F5"


@ft.control
class ScrambleMemoPage(ThemeAwarePage, ft.Column):
    @property
    def state(self):
        # BaseControl.data is a Flet skip_field(), so Python-only AppState
        # never enters the browser serialization protocol.
        return self.data

    def init(self):
        self.expand = True
        self.spacing = 12
        self.scroll = ft.ScrollMode.AUTO
        self.tracer = ScrambleTracer()
        self.scramble = ft.TextField(
            label="Scramble",
            multiline=True,
            min_lines=2,
            max_lines=4,
            hint_text="Paste a 3x3 scramble here",
        color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT), hint_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT))
        self.error = ft.Text("", color=ft.Colors.ERROR)
        self.details = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, selectable=True)
        self.result_area = ft.Column(spacing=10)
        self.show_words = False
        self.last_result = None
        self.last_scheme_signature = None
        # Temporary, scramble-only cycle-break choices. They are never saved to
        # the letter scheme and therefore never alter the user's priority list.
        self.corner_break_overrides: dict[int, str] = {}
        self.edge_break_overrides: dict[int, str] = {}
        self.last_trace_input_key = None
        self.toggle_button = ft.OutlinedButton("Show words", icon=ft.Icons.TRANSLATE, on_click=self._toggle_words)
        self.reset_breaks_button = ft.OutlinedButton(
            "Reset to priority",
            icon=ft.Icons.RESTART_ALT,
            on_click=self._reset_cycle_breaks,
            visible=False,
        )

        self.controls = [
            page_heading("Scramble Memo", "Trace a real scramble through your own letter scheme.", "04 / Understanding"),
            panel(ft.Column([
                eyebrow("Scramble input"),
                ft.Text("Uses White-top / Green-front unless your scheme enables its own orientation.",
                        size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                self.scramble,
                ft.Row([
                    ft.FilledButton("Generate memo", icon=ft.Icons.PLAY_ARROW, on_click=self.generate),
                    self.toggle_button, self.reset_breaks_button,
                ], wrap=True),
                self.error,
            ], spacing=12)),
            panel(ft.Column([
                eyebrow("Memo output"),
                ft.Text("Click an underlined cycle-break target to try another valid break for this scramble. Your saved priorities stay unchanged.",
                        size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                self.result_area,
            ], spacing=12)),
            ft.ExpansionTile(title=ft.Text("Diagnostic trace", size=13, color=ft.Colors.ON_SURFACE), controls=[self.details]),
        ]
        self._render_result()

    def _scheme_signature(self, scheme):
        if scheme is None:
            return None
        return (
            scheme.name,
            scheme.memo_up,
            scheme.memo_front,
            scheme.corners.buffer_sticker,
            scheme.edges.buffer_sticker,
            scheme.corners.orientation_memo,
            scheme.edges.orientation_memo,
            tuple(scheme.corners.cycle_break_priority),
            tuple(scheme.edges.cycle_break_priority),
            tuple(sorted(scheme.corners.cycle_break_stickers.items())),
            tuple(sorted(scheme.edges.cycle_break_stickers.items())),
            tuple(sorted(scheme.corners.stickers.items())),
            tuple(sorted(scheme.edges.stickers.items())),
            scheme.three_style_enabled,
            scheme.edge_parity_partner,
            scheme.scramble_from_own_orientation,
        )

    def refresh(self, update: bool = True):
        scheme = self.state.active_scheme
        signature = self._scheme_signature(scheme)
        if (
            self.last_result is not None
            and signature != self.last_scheme_signature
            and scheme is not None
            and (self.scramble.value or "").strip()
        ):
            # Scheme orientation/tracing changed while a memo was already on
            # screen. Recalculate it rather than leaving stale White/Green or
            # previous-scheme output visible. A one-off cycle-break override is
            # tied to the exact scheme configuration, so drop it here.
            self._clear_cycle_break_overrides()
            self._generate_result(scheme)
        elif scheme is None:
            self.last_result = None
            self.details.value = ""
            self.error.value = ""
        self.last_scheme_signature = signature
        self._render_result()
        if update and self.page is not None:
            self.update()

    def _generate_result(self, scheme):
        try:
            r = self.tracer.trace(
                self.scramble.value or "",
                scheme,
                corner_cycle_break_overrides=self.corner_break_overrides,
                edge_cycle_break_overrides=self.edge_break_overrides,
            )
            self.error.value = ""
            self.last_result = r
            self.last_scheme_signature = self._scheme_signature(scheme)
            self.details.value = (
                f"Corner targets: {' '.join(r.corner_targets) or '—'}\n"
                f"Corner letters: {' '.join(r.corner_letters) or '—'}\n"
                f"Corner cycles: {' '.join('—' if x is None else str(x + 1) for x in r.corner_cycle_ids) or '—'}\n"
                f"Edge targets: {' '.join(r.edge_targets) or '—'}\n"
                f"Edge letters: {' '.join(r.edge_letters) or '—'}\n"
                f"Edge cycles: {' '.join('—' if x is None else str(x + 1) for x in r.edge_cycle_ids) or '—'}\n"
                f"Corner cycle breaks: {', '.join(f'{b.chosen_sticker} ({b.chosen_piece})' for b in r.corner_cycle_breaks) or '—'}\n"
                f"Edge cycle breaks: {', '.join(f'{b.chosen_sticker} ({b.chosen_piece})' for b in r.edge_cycle_breaks) or '—'}\n"
                f"3-style parity memo-swap: {'yes' if r.three_style_parity_applied else 'no'}"
            )
            self.reset_breaks_button.visible = bool(self.corner_break_overrides or self.edge_break_overrides)
        except (ScrambleError, ValueError) as ex:
            self.error.value = str(ex)
            self.last_result = None
            self.details.value = ""
            self.reset_breaks_button.visible = bool(self.corner_break_overrides or self.edge_break_overrides)

    def _clear_cycle_break_overrides(self):
        self.corner_break_overrides.clear()
        self.edge_break_overrides.clear()
        self.reset_breaks_button.visible = False

    def _reset_cycle_breaks(self, e=None):
        self._clear_cycle_break_overrides()
        scheme = self.state.active_scheme
        if scheme and (self.scramble.value or "").strip():
            self._generate_result(scheme)
        self._render_result()
        if self.page is not None:
            self.update()

    def generate(self, e):
        scheme = self.state.active_scheme
        if not scheme:
            self.error.value = "Create or select a letter scheme first."
            self.last_result = None
            self._render_result()
            self.update()
            return
        input_key = ((self.scramble.value or "").strip(), self._scheme_signature(scheme))
        if input_key != self.last_trace_input_key:
            self._clear_cycle_break_overrides()
        self.last_trace_input_key = input_key
        self._generate_result(scheme)
        self._render_result()
        self.update()

    def _toggle_words(self, e):
        self.show_words = not self.show_words
        self.toggle_button.text = "Show letters" if self.show_words else "Show words"
        self._render_result()
        self.update()

    def _palette(self):
        if self.state.data.dark_mode:
            return DARK_CYCLE_COLORS, DARK_ORIENTATION_COLOR
        return LIGHT_CYCLE_COLORS, LIGHT_ORIENTATION_COLOR

    def _target_color(self, cycle_id, orientation_target, scheme):
        cycle_palette, orientation_color = self._palette()
        if scheme.highlight_orientation_targets and orientation_target:
            return orientation_color
        if scheme.show_cycle_colors and cycle_id is not None:
            return cycle_palette[cycle_id % len(cycle_palette)]
        return None

    def _open_cycle_break_picker(self, category: str, break_info):
        """Open a temporary cycle-break chooser sorted by saved priority."""
        overrides = self.corner_break_overrides if category == "corners" else self.edge_break_overrides

        def choose(piece: str | None):
            if piece is None or piece == break_info.recommended_piece:
                overrides.pop(break_info.break_index, None)
            else:
                overrides[break_info.break_index] = piece
            if self.page is not None:
                self.page.pop_dialog()
            scheme = self.state.active_scheme
            if scheme is not None:
                self._generate_result(scheme)
                self._render_result()
                self.update()

        option_controls = []
        for piece, sticker in break_info.options:
            recommended = piece == break_info.recommended_piece
            selected = piece == break_info.chosen_piece
            suffix = " · priority" if recommended else ""
            option_controls.append(
                ft.ListTile(
                    title=ft.Text(f"{sticker}  ({piece}){suffix}", color=ft.Colors.ON_SURFACE),
                    leading=ft.Icon(ft.Icons.CHECK_CIRCLE if selected else ft.Icons.RADIO_BUTTON_UNCHECKED),
                    on_click=lambda e, p=piece: choose(p),
                )
            )
        option_controls.append(ft.Divider())
        option_controls.append(
            ft.TextButton(
                "Reset to priority",
                icon=ft.Icons.RESTART_ALT,
                on_click=lambda e: choose(None),
            )
        )
        dialog = ft.AlertDialog(
            title=ft.Text(f"Temporary {category[:-1]} cycle break", color=ft.Colors.ON_SURFACE),
            content=ft.Column(
                [
                    ft.Text(
                        "Choose any valid unsolved piece for this cycle break. "
                        "The list follows your saved priority order; this choice only affects this scramble.",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    *option_controls,
                ],
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
        )
        if self.page is not None:
            show_themed_dialog(self.page, dialog, self.state.data.dark_mode)

    def _memo_control(self, category, letters, pairs, orientation, cycle_ids, orientation_flags, cycle_breaks):
        if not letters and not orientation:
            return ft.Text("(solved)", size=18, selectable=True, color=ft.Colors.ON_SURFACE)

        scheme = self.state.active_scheme
        if scheme is None:
            return ft.Text("—", size=18, selectable=True, color=ft.Colors.ON_SURFACE)

        breaks_by_target = {b.target_index: b for b in cycle_breaks}
        spans = []
        index = 0
        for pair in pairs:
            target_count = len(pair)
            target_cycles = cycle_ids[index:index + target_count]
            target_flags = orientation_flags[index:index + target_count]
            pair_breaks = [
                breaks_by_target[i]
                for i in range(index, index + target_count)
                if i in breaks_by_target
            ]

            display_pair = self.state.get_pair_display(pair) if len(pair) == 2 and "?" not in pair else pair
            word = self.state.get_word(pair) if len(pair) == 2 and "?" not in pair else ""
            display = word if self.show_words and word else display_pair

            # When we are displaying letters/aliases and the visible value has
            # one glyph per target, color each target independently. Cycle-break
            # starts are also clickable individually in this mode.
            can_split = (not (self.show_words and word)) and len(display) == target_count
            if can_split:
                for j, char in enumerate(display):
                    absolute_index = index + j
                    color = self._target_color(target_cycles[j], target_flags[j], scheme)
                    break_info = breaks_by_target.get(absolute_index)
                    style = ft.TextStyle(
                        color=color,
                        decoration=ft.TextDecoration.UNDERLINE if break_info else None,
                        weight=ft.FontWeight.BOLD if break_info else None,
                    )
                    kwargs = {}
                    if break_info is not None:
                        kwargs["on_click"] = lambda e, c=category, b=break_info: self._open_cycle_break_picker(c, b)
                    spans.append(ft.TextSpan(text=char, style=style, **kwargs))
            else:
                chosen_color = None
                if scheme.highlight_orientation_targets and any(target_flags):
                    _, chosen_color = self._palette()
                elif scheme.show_cycle_colors:
                    first_cycle = next((x for x in target_cycles if x is not None), None)
                    if first_cycle is not None:
                        chosen_color = self._palette()[0][first_cycle % 4]
                style = ft.TextStyle(
                    color=chosen_color,
                    decoration=ft.TextDecoration.UNDERLINE if pair_breaks else None,
                    weight=ft.FontWeight.BOLD if pair_breaks else None,
                )
                kwargs = {}
                if pair_breaks:
                    kwargs["on_click"] = lambda e, c=category, b=pair_breaks[0]: self._open_cycle_break_picker(c, b)
                spans.append(ft.TextSpan(text=display, style=style, **kwargs))

            spans.append(ft.TextSpan(text=" "))
            index += target_count

        for annotation in orientation:
            spans.append(ft.TextSpan(text=f"{annotation} "))

        return ft.Text(spans=spans, size=18, selectable=True, color=ft.Colors.ON_SURFACE)

    def _render_result(self):
        if self.last_result is None:
            order = "EC"
        else:
            scheme = self.state.active_scheme
            order = (scheme.execution_order if scheme else "") or "EC"

        if self.last_result is None:
            sections = {
                "C": ("Corners", ft.Text("—", size=18, selectable=True, color=ft.Colors.ON_SURFACE)),
                "E": ("Edges", ft.Text("—", size=18, selectable=True, color=ft.Colors.ON_SURFACE)),
            }
        else:
            r = self.last_result
            sections = {
                "C": ("Corners", self._memo_control(
                    "corners", r.corner_letters, r.corner_pairs, r.corner_orientation,
                    r.corner_cycle_ids, r.corner_orientation_target_flags, r.corner_cycle_breaks,
                )),
                "E": ("Edges", self._memo_control(
                    "edges", r.edge_letters, r.edge_pairs, r.edge_orientation,
                    r.edge_cycle_ids, r.edge_orientation_target_flags, r.edge_cycle_breaks,
                )),
            }

        controls = []
        for key in order:
            title, memo_control = sections[key]
            controls.extend([
                ft.Text(title, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                memo_control,
            ])
        self.result_area.controls = controls
