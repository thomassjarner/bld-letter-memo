import flet as ft

from core.tracer import ScrambleTracer, ScrambleError


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
        self.last_scheme_name = None
        self.toggle_button = ft.OutlinedButton("Show words", icon=ft.Icons.TRANSLATE, on_click=self._toggle_words)

        self.controls = [
            ft.Text("Scramble → Memo", size=20, weight=ft.FontWeight.BOLD),
            ft.Text("Uses the active letter scheme, including its orientation and tracing preferences."),
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

    def refresh(self, update: bool = True):
        scheme = self.state.active_scheme
        scheme_name = scheme.name if scheme else None
        if self.last_scheme_name is not None and scheme_name != self.last_scheme_name:
            # A result from another scheme/orientation would be misleading.
            self.last_result = None
            self.details.value = ""
            self.error.value = ""
        self.last_scheme_name = scheme_name
        self._render_result()
        if update and self.page is not None:
            self.update()

    def generate(self, e):
        scheme = self.state.active_scheme
        if not scheme:
            self.error.value = "Create or select a letter scheme first."
            self.last_result = None
            self._render_result()
            self.update()
            return
        try:
            r = self.tracer.trace(self.scramble.value or "", scheme)
            self.error.value = ""
            self.last_result = r
            self.last_scheme_name = scheme.name
            self.details.value = (
                f"Corner targets: {' '.join(r.corner_targets) or '—'}\n"
                f"Corner letters: {' '.join(r.corner_letters) or '—'}\n"
                f"Edge targets: {' '.join(r.edge_targets) or '—'}\n"
                f"Edge letters: {' '.join(r.edge_letters) or '—'}"
            )
        except (ScrambleError, ValueError) as ex:
            self.error.value = str(ex)
            self.last_result = None
            self.details.value = ""
        self._render_result()
        self.update()

    def _toggle_words(self, e):
        self.show_words = not self.show_words
        self.toggle_button.text = "Show letters" if self.show_words else "Show words"
        self._render_result()
        self.update()

    def _memo_text(self, pairs, orientation):
        shown = []
        for pair in pairs:
            display_pair = self.state.get_pair_display(pair) if len(pair) == 2 and "?" not in pair else pair
            if self.show_words and len(pair) == 2 and "?" not in pair:
                # Missing word deliberately falls back to the visible pair label.
                shown.append(self.state.get_word(pair) or display_pair)
            else:
                shown.append(display_pair)
        shown.extend(orientation)
        return " ".join(shown) if shown else "(solved)"

    def _render_result(self):
        if self.last_result is None:
            # Default display follows the standard execution order: edges first.
            order = "EC"
        else:
            scheme = self.state.active_scheme
            order = (scheme.execution_order if scheme else "") or "EC"

        sections = {
            "C": ("Corners", "—" if self.last_result is None else self._memo_text(
                self.last_result.corner_pairs, self.last_result.corner_orientation
            )),
            "E": ("Edges", "—" if self.last_result is None else self._memo_text(
                self.last_result.edge_pairs, self.last_result.edge_orientation
            )),
        }
        controls = []
        for key in order:
            title, text = sections[key]
            controls.extend([
                ft.Text(title, weight=ft.FontWeight.BOLD),
                ft.Text(text, size=18, selectable=True),
            ])
        self.result_area.controls = controls
