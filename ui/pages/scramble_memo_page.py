import flet as ft

from core.tracer import ScrambleTracer, ScrambleError


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
class ScrambleMemoPage(ft.Column):
    @property
    def state(self):
        # BaseControl.data is a Flet skip_field(), so Python-only AppState
        # never enters the browser serialization protocol.
        return self.data

    def init(self):
        self.expand = True
        self.scroll = ft.ScrollMode.AUTO
        self.tracer = ScrambleTracer()
        self.scramble = ft.TextField(
            label="Scramble",
            multiline=True,
            min_lines=2,
            max_lines=4,
            hint_text="Paste a 3x3 scramble here",
        )
        self.error = ft.Text("", color=ft.Colors.ERROR)
        self.details = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, selectable=True)
        self.result_area = ft.Column(spacing=10)
        self.show_words = False
        self.last_result = None
        self.last_scheme_signature = None
        self.toggle_button = ft.OutlinedButton("Show words", icon=ft.Icons.TRANSLATE, on_click=self._toggle_words)

        self.controls = [
            ft.Text("Scramble → Memo", size=20, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Scramble interpretation follows the active scheme: fixed White-top / Green-front by default, or the scheme's own orientation when that preference is enabled."
            ),
            self.scramble,
            ft.Row([
                ft.ElevatedButton("Generate memo", icon=ft.Icons.PLAY_ARROW, on_click=self.generate),
                self.toggle_button,
            ]),
            self.error,
            ft.Divider(),
            self.result_area,
            ft.Divider(),
            ft.ExpansionTile(title=ft.Text("Diagnostic trace"), controls=[self.details]),
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
            # previous-scheme output visible.
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
            r = self.tracer.trace(self.scramble.value or "", scheme)
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
                f"3-style parity memo-swap: {'yes' if r.three_style_parity_applied else 'no'}"
            )
        except (ScrambleError, ValueError) as ex:
            self.error.value = str(ex)
            self.last_result = None
            self.details.value = ""

    def generate(self, e):
        scheme = self.state.active_scheme
        if not scheme:
            self.error.value = "Create or select a letter scheme first."
            self.last_result = None
            self._render_result()
            self.update()
            return
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

    def _memo_control(self, letters, pairs, orientation, cycle_ids, orientation_flags):
        if not letters and not orientation:
            return ft.Text("(solved)", size=18, selectable=True)

        scheme = self.state.active_scheme
        if scheme is None:
            return ft.Text("—", size=18, selectable=True)

        spans = []
        index = 0
        for pair in pairs:
            target_count = len(pair)
            target_cycles = cycle_ids[index:index + target_count]
            target_flags = orientation_flags[index:index + target_count]

            display_pair = self.state.get_pair_display(pair) if len(pair) == 2 and "?" not in pair else pair
            word = self.state.get_word(pair) if len(pair) == 2 and "?" not in pair else ""
            display = word if self.show_words and word else display_pair

            # When we are displaying letters/aliases and the visible value has
            # one glyph per target, color each target independently. This makes
            # cycle boundaries visible even when they fall in the middle of a
            # letter pair. A mnemonic word is indivisible, so it inherits the
            # most specific color in the pair (twist/flip first, otherwise the
            # first cycle color).
            can_split = (not (self.show_words and word)) and len(display) == target_count
            if can_split:
                for j, char in enumerate(display):
                    color = self._target_color(target_cycles[j], target_flags[j], scheme)
                    spans.append(ft.TextSpan(text=char, style=ft.TextStyle(color=color) if color else None))
            else:
                chosen_color = None
                # Twist/flip highlighting takes precedence if either target in
                # the displayed pair/word exists specifically for orientation.
                if scheme.highlight_orientation_targets and any(target_flags):
                    _, chosen_color = self._palette()
                elif scheme.show_cycle_colors:
                    first_cycle = next((x for x in target_cycles if x is not None), None)
                    if first_cycle is not None:
                        chosen_color = self._palette()[0][first_cycle % 4]
                spans.append(ft.TextSpan(text=display, style=ft.TextStyle(color=chosen_color) if chosen_color else None))

            spans.append(ft.TextSpan(text=" "))
            index += target_count

        for annotation in orientation:
            spans.append(ft.TextSpan(text=f"{annotation} "))

        return ft.Text(spans=spans, size=18, selectable=True)

    def _render_result(self):
        if self.last_result is None:
            order = "EC"
        else:
            scheme = self.state.active_scheme
            order = (scheme.execution_order if scheme else "") or "EC"

        if self.last_result is None:
            sections = {
                "C": ("Corners", ft.Text("—", size=18, selectable=True)),
                "E": ("Edges", ft.Text("—", size=18, selectable=True)),
            }
        else:
            r = self.last_result
            sections = {
                "C": ("Corners", self._memo_control(
                    r.corner_letters, r.corner_pairs, r.corner_orientation,
                    r.corner_cycle_ids, r.corner_orientation_target_flags,
                )),
                "E": ("Edges", self._memo_control(
                    r.edge_letters, r.edge_pairs, r.edge_orientation,
                    r.edge_cycle_ids, r.edge_orientation_target_flags,
                )),
            }

        controls = []
        for key in order:
            title, memo_control = sections[key]
            controls.extend([
                ft.Text(title, weight=ft.FontWeight.BOLD),
                memo_control,
            ])
        self.result_area.controls = controls
