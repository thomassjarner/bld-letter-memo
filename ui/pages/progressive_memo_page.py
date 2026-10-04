"""Space-driven real-scramble memo, recall, feedback and persistent history."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from uuid import uuid4

import flet as ft

from core.progressive_memo import ProgressiveRun, align_letters, build_plan, normalize_letters, pairs, score_recall
from core.scramble_generator import ScrambleGenerator
from core.tracer import ScrambleError
from data.models import ProgressiveMemoAttempt
from ui.design import panel
from ui.pages.practice_page import _format_centiseconds
from ui.theme_colors import ThemeAwarePage, apply_palette


def order_label(order):
    return " → ".join("Corners" if letter == "C" else "Edges" for letter in order)


@ft.control
class ProgressiveMemoPage(ThemeAwarePage, ft.Column):
    back_callback = None
    open_scheme_callback = None
    INTRO_SECONDS = 1.0
    SPACE_KEYS = {" ", "Space", "Spacebar"}

    @property
    def state(self):
        return self.data

    @property
    def phase(self):
        return self.run.phase if self.run else ("result" if self.result else "ready")

    @property
    def in_attempt(self):
        return self.run is not None and self.run.phase != "result"

    def init(self):
        self.expand = True
        self.spacing = 12
        self.scroll = None
        self.active = False
        self.generator = ScrambleGenerator()
        self.current_scramble = self.generator.generate()
        self.run: ProgressiveRun | None = None
        self.result: ProgressiveMemoAttempt | None = None
        self.error = ""
        self._generation = 0
        self._viewport = (1400.0, 760.0)
        self._space_submitted = False
        self._last_space_letters = ""
        self.history_limit = 50
        self.presentation = None
        self.presentation_estimate = 0
        self._layout_wide = None

        self.clock = ft.Text("0.00", size=14, font_family="monospace", color=ft.Colors.ON_SURFACE)
        self.cancel_button = ft.TextButton("Cancel", on_click=self._cancel)
        self.title_text = ft.Text("Progressive Memo", size=23, weight=ft.FontWeight.W_600,
                                  expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.header = ft.Row([
            ft.IconButton(ft.Icons.ARROW_BACK, tooltip="Back to Practice", on_click=self._back),
            self.title_text,
            self.clock, self.cancel_button,
        ], height=40, spacing=8)
        self.scheme_dropdown = ft.Dropdown(label="Letter scheme", width=280, dense=True,
                                          on_select=self._choose_scheme)
        self.display_letters = ft.Text("", size=84, weight=ft.FontWeight.W_600,
                                       font_family="monospace", text_align=ft.TextAlign.CENTER)
        self.recall_field = ft.TextField(
            hint_text="Type letters", width=240, height=58, dense=True,
            text_size=28, text_align=ft.TextAlign.CENTER,
            capitalization=ft.TextCapitalization.CHARACTERS,
            autocorrect=False, enable_suggestions=False,
            on_change=self._input_changed, on_submit=self._input_submitted,
        )
        self.stage_scroll = ft.ListView(spacing=12, scroll=ft.ScrollMode.AUTO,
                                        build_controls_on_demand=False)
        self.stage_panel = panel(self.stage_scroll, padding=20)
        self.history_meta = ft.Text("", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
        self.history = ft.ListView(spacing=4, scroll=ft.ScrollMode.ALWAYS)
        self.older_button = ft.TextButton("Older attempts", height=32, on_click=self._older_attempts)
        self.history_panel = panel(ft.Column([
            ft.Row([ft.Text("Saved attempts", size=14, weight=ft.FontWeight.W_600, expand=True),
                    self.history_meta], height=28),
            self.history, self.older_button,
        ], spacing=8), padding=14)
        self.main_region = ft.Column(spacing=12)
        self.keyboard_listener = ft.KeyboardListener(
            content=self.main_region, on_key_down=self._key_down,
            on_key_repeat=lambda e: None, autofocus=True,
        )
        self.controls = [self.header, self.keyboard_listener]
        self.set_viewport(*self._viewport)
        self.refresh(update=False)

    def _page(self):
        try:
            return self.page
        except RuntimeError:
            return None

    def _update(self):
        apply_palette(self, self.state.data.dark_mode)
        if self._page() is not None:
            self.update()

    def _task(self, function, *args):
        page = self._page()
        if page is not None:
            page.run_task(function, *args)

    def set_viewport(self, width, height):
        width, height = max(280.0, float(width)), max(300.0, float(height))
        self._viewport = (width, height)
        self.width, self.height = width, height
        self.header.width = width
        self.title_text.size = 23 if width >= 600 else 18
        main_height = height - 52
        wide = width >= 1000
        history_width = min(360, width * 0.28) if wide else width
        stage_width = width - history_width - 16 if wide else width
        history_height = main_height if wide else min(210, max(120, main_height * 0.28))
        stage_height = main_height if wide else main_height - history_height - 12
        self.stage_panel.width, self.stage_panel.height = stage_width, stage_height
        self.stage_scroll.width, self.stage_scroll.height = stage_width - 40, max(1, stage_height - 40)
        self.history_panel.width, self.history_panel.height = history_width, history_height
        self.history.width, self.history.height = history_width - 28, max(1, history_height - 104)
        self.main_region.width, self.main_region.height = width, main_height
        if wide != self._layout_wide:
            self.main_region.controls = [ft.Row([self.stage_panel, self.history_panel], spacing=16)] if wide else [self.stage_panel, self.history_panel]
            self._layout_wide = wide
            if self.active and self.in_attempt:
                self._focus(self.phase == "recall")
        self.scheme_dropdown.width = min(320, max(180, stage_width - 48))
        self.recall_field.width = min(360, max(180, stage_width - 48))
        self.display_letters.size = max(24, min(84, stage_height * 0.24,
                                              (stage_width - 48) / (max(2, len(self.display_letters.value or "")) * 0.65)))
        if self.presentation is not None:
            self.presentation.padding = ft.Padding.symmetric(
                vertical=max(0, (self.stage_scroll.height - self.presentation_estimate) / 2))

    def set_active(self, active):
        self.active = bool(active)
        if not self.active and self.in_attempt:
            # Navigation cancels unfinished work; it never records an attempt.
            self._cancel(update=False)
        elif self.active and self.in_attempt:
            self._focus(self.phase == "recall")

    def refresh(self, update=True):
        self.scheme_dropdown.options = [ft.DropdownOption(name, name) for name in self.state.scheme_names]
        self.scheme_dropdown.value = self.state.data.active_scheme
        if self.result and not any(item.id == self.result.id for item in self.state.data.progressive_memo_history):
            self.run, self.result = None, None
        if not self.in_attempt:
            self._render_stage()
        self._refresh_history()
        if update:
            self._update()

    def _center(self, controls, estimate=220):
        self.presentation_estimate = estimate
        self.presentation = ft.Container(ft.Column(controls, spacing=12, tight=True,
                                                   horizontal_alignment=ft.CrossAxisAlignment.CENTER))
        self.stage_scroll.controls = [self.presentation]

    def _render_stage(self):
        self.presentation = None
        self.cancel_button.visible = self.in_attempt
        self.clock.visible = self.phase != "ready"
        if self.phase == "ready":
            scheme = self.state.active_scheme
            info = []
            if scheme:
                info = [ft.Text(f"Memo: {order_label(scheme.memo_order or 'CE')}", size=12),
                        ft.Text(f"Recall: {order_label(scheme.execution_order or 'EC')}", size=12),
                        ft.Text(" · ".join(f"{label}: {'letters, grouped' if cat.orientation_memo == 'trace' else 'visual, omitted'}"
                                           for label, cat in (("Twists", scheme.corners), ("Flips", scheme.edges))),
                                size=12, color=ft.Colors.ON_SURFACE_VARIANT)]
            self.stage_scroll.controls = [
                ft.Text("Memo, then recall", size=24, weight=ft.FontWeight.W_600),
                ft.Text("See each pair, press Space to continue, and review the whole category. Then type the letters from memory.", size=13),
                self.scheme_dropdown, *info,
                ft.Text("Real scramble", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(self.current_scramble, size=13, font_family="monospace", selectable=True),
                ft.Text(self.error or ("Choose or create a letter scheme first." if not scheme else ""), color=ft.Colors.ERROR),
                ft.Row([ft.FilledButton("Start", icon=ft.Icons.PLAY_ARROW, disabled=scheme is None, on_click=self._start),
                        ft.OutlinedButton("New scramble", on_click=self._new_scramble),
                        ft.TextButton("Letter Schemes", on_click=self._open_scheme)], wrap=True, spacing=8),
                ft.Text("Category titles last 1 second. Timing starts at the first letters and ends when you confirm the last answer. Leaving the activity cancels an unfinished attempt.",
                        size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ]
        elif self.phase == "intro":
            self._center([ft.Text(self.run.category.category.title(), size=44, weight=ft.FontWeight.W_600)], 70)
        elif self.phase == "memo":
            prompt = self.run.prompt
            self.display_letters.value = " ".join(pairs(prompt.letters))
            self._center([
                ft.Text(f"{prompt.category.title()} · {prompt.label}", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                self.display_letters,
                ft.Text("Space → next", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.FilledButton("Next", on_click=self._next),
            ])
        elif self.phase == "overview":
            category = self.run.category
            controls = [ft.Text(f"{category.category.title()} · Review all pairs", size=21, weight=ft.FontWeight.W_600),
                        ft.Text(" ".join(category.ordinary_pairs) or "No ordinary letter targets", size=32,
                                font_family="monospace", text_align=ft.TextAlign.CENTER)]
            if category.orientation_pairs:
                controls += [ft.Text("All twists" if category.category == "corners" else "All flips", size=12),
                             ft.Text(" ".join(category.orientation_pairs), size=28, font_family="monospace")]
            last = self.run.category_index == len(self.run.plan.categories) - 1
            controls += [ft.Text("Space → type your recall" if last else "Space → next category", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                         ft.FilledButton("Recall" if last else "Next category", on_click=self._next)]
            self._center(controls, 260)
        elif self.phase == "recall":
            prompt = self.run.prompt
            self._center([
                ft.Text(f"Recall {prompt.category.title()} · {prompt.label}", size=20, weight=ft.FontWeight.W_600),
                ft.Text(f"Answer {self.run.recall_index + 1} / {len(self.run.plan.recall_prompts)}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                self.recall_field,
                ft.Text("Type all twist/flip letters together." if prompt.kind == "orientation" else "Type the letter pair (or the single final letter).", size=12),
                ft.Text("Space or Enter → confirm. Use Skip if you cannot recall it.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Row([ft.FilledButton("Confirm", on_click=self._next),
                        ft.TextButton("Skip", on_click=lambda e: self._submit_recall(""))],
                       alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            ], 280)
        else:
            self._render_result()
        self.set_viewport(*self._viewport)

    def _choose_scheme(self, e):
        self.state.switch_scheme(e.control.value)
        self.error = ""
        self.refresh()

    def _open_scheme(self, e=None):
        if self.open_scheme_callback:
            self.open_scheme_callback()

    def _new_scramble(self, e=None):
        self._generation += 1
        self.run, self.result = None, None
        self.current_scramble = self.generator.generate()
        self.error = ""
        self.clock.value = "0.00"
        self.recall_field.value = ""
        self.refresh()

    def _start(self, e=None):
        if not self.active or self.in_attempt or self.state.active_scheme is None:
            return
        try:
            plan = build_plan(self.current_scramble, self.state.active_scheme)
        except ScrambleError as error:
            self.error = str(error)
            self._render_stage()
            self._update()
            return
        self._generation += 1
        self.run = ProgressiveRun(plan)
        self.result = None
        self.error = ""
        self.clock.value = "0.00"
        self.recall_field.value = ""
        self._space_submitted = False
        self._render_stage()
        self._refresh_history()
        self._update()
        self._focus(False)
        self._schedule_intro()

    def _schedule_intro(self):
        self._task(self._intro_delay, self._generation, self.run.category_index)

    async def _intro_delay(self, token, category_index):
        await asyncio.sleep(self.INTRO_SECONDS)
        self._finish_intro(token, category_index)

    def _finish_intro(self, token, category_index):
        if not self.active or token != self._generation or not self.run or self.phase != "intro" or self.run.category_index != category_index:
            return
        started = self.run.started_at is not None
        self.run.finish_intro(time.monotonic())
        self._render_stage()
        self._update()
        self._focus(False)
        if not started and self.run.started_at is not None:
            self._task(self._tick, token)

    async def _tick(self, token):
        while self.active and token == self._generation and self.in_attempt:
            if self.run.started_at is not None:
                self.clock.value = _format_centiseconds(round((time.monotonic() - self.run.started_at) * 100))
                self._update()
            await asyncio.sleep(0.2)

    def _key_down(self, e):
        if self.active and e.key in self.SPACE_KEYS and self.phase in {"memo", "overview"}:
            self._next()
        # During recall the TextField's actual edit event submits the answer.
        # This avoids a keyboard callback reading a stale final typed letter.

    def _next(self, e=None):
        if not self.active or not self.run:
            return
        if self.phase == "recall":
            self._submit_recall(self.recall_field.value or "")
            return
        if self.run.next(time.monotonic()):
            self._render_stage()
            self._update()
            self._focus(self.phase == "recall")
            if self.phase == "intro":
                self._schedule_intro()

    def _input_changed(self, e):
        if not self.active or self.phase != "recall":
            return
        raw = e.control.value or ""
        if any(char.isspace() for char in raw):
            letters = normalize_letters(raw)
            # Held Space cannot skip empty answers or re-submit a stale edit.
            if letters and (not self._space_submitted or letters != self._last_space_letters):
                self._space_submitted = True
                self._last_space_letters = letters
                self._submit_recall(letters)
            else:
                self.recall_field.value = ""
                self._update()
        else:
            self._space_submitted = False

    def _input_submitted(self, e):
        self._submit_recall(e.control.value or "")

    def _submit_recall(self, value):
        if not self.active or not self.run or not self.run.submit(value, time.monotonic()):
            return
        self.recall_field.value = ""
        if self.phase == "result":
            self._complete()
        self._render_stage()
        self._update()
        if self.phase == "recall":
            self._focus(True)

    def _complete(self):
        memo, recall = self.run.timings()
        correct, scored = score_recall(self.run.recall)
        plan = self.run.plan
        self.result = ProgressiveMemoAttempt(
            id=uuid4().hex, created_at=datetime.now(timezone.utc).isoformat(),
            scramble=plan.scramble, scheme_name=plan.scheme_name, scheme_snapshot=plan.scheme_snapshot,
            memo_order=plan.memo_order, execution_order=plan.execution_order,
            memo_centiseconds=memo, recall_centiseconds=recall,
            correct_letters=correct, scored_letters=scored, recall=list(self.run.recall),
        )
        self.state.add_progressive_memo_attempt(self.result)
        self.clock.value = _format_centiseconds(self.result.centiseconds)
        self._refresh_history()

    def _cancel(self, e=None, update=True):
        self._generation += 1
        self.run, self.result = None, None
        self.recall_field.value = ""
        self.clock.value = "0.00"
        self.refresh(update=update)

    def _back(self, e=None):
        if self.back_callback:
            self.back_callback()

    def _focus(self, recall):
        self._task(self._focus_async, recall, self._generation, self.run.recall_index if self.run else 0)

    async def _focus_async(self, recall, token, index):
        if not self.active or token != self._generation or not self.in_attempt:
            return
        if recall != (self.phase == "recall"):
            return
        if recall and (not self.run or self.phase != "recall" or self.run.recall_index != index):
            return
        try:
            await (self.recall_field if recall else self.keyboard_listener).focus()
        except RuntimeError:
            # Navigation can detach a control between scheduling and focus.
            pass

    def _result_letter(self, expected, entered, correct):
        dark = self.state.data.dark_mode
        foreground = ("#83E0AF" if dark else "#12643D") if correct else ("#FFB4AB" if dark else "#BA1A1A")
        background = ("#173F2C" if dark else "#E1F3E7") if correct else ("#482A29" if dark else "#FCEAE8")
        description = f"Correct: {expected}" if correct else (f"Missing: {expected}" if not entered else (f"Extra: {entered}" if not expected else f"{entered} should be {expected}"))
        return ft.Container(ft.Column([
            ft.Text(entered or "—", size=19, weight=ft.FontWeight.BOLD, color=foreground),
            ft.Text(expected or "extra", size=11, color=foreground),
        ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=40, padding=6, border_radius=6, bgcolor=background, tooltip=description)

    def _render_result(self):
        result = self.result
        controls = [
            ft.Text("Recall result", size=24, weight=ft.FontWeight.W_600),
            ft.Row([ft.Text(f"{result.accuracy:.1f}% accuracy", size=23, weight=ft.FontWeight.W_600),
                    ft.Text(f"Total {_format_centiseconds(result.centiseconds)}", size=20, font_family="monospace")], wrap=True, spacing=24),
            ft.Text(f"Memo {_format_centiseconds(result.memo_centiseconds)} · Recall {_format_centiseconds(result.recall_centiseconds)} · {result.correct_letters}/{result.scored_letters} scored letters correct", size=12),
            ft.Text("Green = correct · Red = incorrect, missing or extra. Each tile shows your answer above the correct letter. Accuracy counts letters; extra letters reduce the score.",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT),
        ]
        for category in ("corners" if letter == "C" else "edges" for letter in result.execution_order):
            items = [item for item in result.recall if item.category == category]
            controls.append(ft.Text(category.title(), size=17, weight=ft.FontWeight.W_600))
            if not items:
                controls.append(ft.Text("No letter targets", size=12))
            pair_index = 0
            for item in items:
                pair_index += item.kind == "pair"
                label = ("All twists" if category == "corners" else "All flips") if item.kind == "orientation" else f"Pair {pair_index}"
                controls.append(ft.Row([
                    ft.Text(label, size=12, width=72),
                    ft.Row([self._result_letter(*letter) for letter in align_letters(item.expected, item.entered)],
                           spacing=4, wrap=True, expand=True),
                ], spacing=10))
        controls += [ft.Divider(),
                     ft.Text(f"Saved · {result.scheme_name} · Memo {result.memo_order} / Exec {result.execution_order}", size=12),
                     ft.Text(result.scramble, size=12, font_family="monospace", selectable=True),
                     ft.FilledButton("Start next attempt", on_click=self._start_next)]
        self.stage_scroll.controls = controls

    def _start_next(self, e=None):
        self._new_scramble()
        self._start()

    def _refresh_history(self):
        history = self.state.data.progressive_memo_history
        self.history_meta.value = str(len(history))
        self.older_button.visible = len(history) > self.history_limit
        self.older_button.disabled = self.in_attempt
        self.history.controls = [ft.Text("Finished attempts save here automatically.", size=12, color=ft.Colors.ON_SURFACE_VARIANT)]
        if history:
            self.history.controls = [ft.TextButton(content=ft.Column([
                ft.Row([ft.Text(_format_centiseconds(item.centiseconds), size=16, weight=ft.FontWeight.W_600, expand=True),
                        ft.Text(f"{item.accuracy:.1f}%", size=13)], spacing=8),
                ft.Text(f"{item.scheme_name} · {item.created_at[:16].replace('T', ' ')} UTC", size=10,
                        color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=3), tooltip=item.scramble, disabled=self.in_attempt,
                on_click=lambda e, saved=item: self._show_saved(saved)) for item in reversed(history[-self.history_limit:])]

    def _show_saved(self, saved):
        if self.in_attempt:
            return
        self._generation += 1
        self.run, self.result = None, saved
        self.clock.value = _format_centiseconds(saved.centiseconds)
        self._render_stage()
        self._update()

    def _older_attempts(self, e=None):
        self.history_limit += 50
        self._refresh_history()
        self._update()
