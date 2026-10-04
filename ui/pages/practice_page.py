from __future__ import annotations


import asyncio
import time

import flet as ft
from ui.theme_colors import ThemeAwarePage, show_themed_dialog

from core.scramble_generator import ScrambleGenerator
from ui.design import activity_card, page_heading, panel, eyebrow


def _format_centiseconds(cs: int) -> str:
    cs = max(0, int(cs))
    minutes, rem = divmod(cs, 6000)
    seconds = rem / 100.0
    if minutes:
        return f"{minutes}:{seconds:05.2f}"
    return f"{seconds:.2f}"


def _effective_centiseconds(solve) -> int:
    return solve.centiseconds + (200 if getattr(solve, "plus2", False) else 0)


def _wca_average(solves, count: int):
    """Return centiseconds, 'DNF', or None using WCA-style trimmed average."""
    if len(solves) < count:
        return None
    window = list(solves[-count:])
    dnfs = sum(1 for s in window if s.dnf)
    if dnfs >= 2:
        return "DNF"

    values = [None if s.dnf else _effective_centiseconds(s) for s in window]
    finite = [v for v in values if v is not None]
    if not finite:
        return "DNF"

    best = min(finite)
    removed_best = False
    remaining = []
    for value in values:
        if value == best and not removed_best:
            removed_best = True
            continue
        remaining.append(value)

    if None in remaining:
        remaining.remove(None)
    elif remaining:
        remaining.remove(max(remaining))

    if not remaining:
        return None
    return int(round(sum(remaining) / len(remaining)))



def _best_wca_average(solves, count: int):
    """Best valid WCA-style average of `count` across the current session."""
    if len(solves) < count:
        return None
    best = None
    for end in range(count, len(solves) + 1):
        value = _wca_average(solves[end-count:end], count)
        if value is None or value == "DNF":
            continue
        if best is None or value < best:
            best = value
    return best

@ft.control
class PracticePage(ThemeAwarePage, ft.Column):
    @property
    def state(self):
        # BaseControl.data is a Flet skip_field(), so Python-only AppState
        # never enters the browser serialization protocol.
        return self.data

    open_memo_callback = None
    open_timer_callback = None
    open_practice_callback = None

    """Practice hub plus Blind Timer.

    Uses ft.KeyboardListener's real on_key_down/on_key_up events (added
    after this app was first built for Flet 0.24, which only exposed a
    global key-down stream). Hold Space to arm (turns green after a short
    delay), release once armed to start; any key stops a running timer.

    All timed/delayed behavior (arm delay, live elapsed-seconds display,
    copy-notice fade) runs as asyncio tasks via page.run_task rather than
    background threads: raw OS threads (threading.Thread) cannot be
    created inside Flet's Pyodide/web runtime ("can't start new thread"),
    only real desktop mode. asyncio tasks work in both.
    """

    HOLD_ARM_SECONDS = 0.10
    SPACE_KEYS = (" ", "Space")


    def init(self):
        self.expand = True
        self.spacing = 0
        # The Practice hub may scroll, but the timer view itself is deliberately
        # fixed to the available app viewport. Solve history gets its own
        # independent scroll area instead of making the whole page taller.
        self.scroll = ft.ScrollMode.AUTO
        self.generator = ScrambleGenerator()

        self.mode = "menu"
        self.active = False

        self.current_scramble = self.generator.generate()
        self.scramble_stack = [self.current_scramble]
        self.scramble_index = 0

        self.running = False
        self.holding_space = False
        self.armed = False
        self.started_at = 0.0
        self.last_display_second = -1
        self.last_solve_index = None
        self.keyboard_listener: ft.KeyboardListener | None = None

        self.scramble_text = ft.Text(self.current_scramble, size=17, selectable=True, font_family="monospace", color=ft.Colors.ON_SURFACE)
        self.timer_text = ft.Text("0.00", size=68, weight=ft.FontWeight.W_500, font_family="monospace", color=ft.Colors.ON_SURFACE)
        self.status_text = ft.Text("", size=14, color=ft.Colors.ON_SURFACE)
        self.stats_text = ft.Text("", color=ft.Colors.ON_SURFACE)
        self.copy_notice = ft.Text("", opacity=0, animate_opacity=300, size=12, color=ft.Colors.ON_SURFACE)
        self._copy_notice_token = 0
        # Keep this ListView mounted and give it an explicit viewport. Flet web
        # can otherwise let a nested expanding history list grow past the page.
        self.history = ft.ListView(spacing=0, scroll=ft.ScrollMode.ALWAYS,
                                   build_controls_on_demand=True)
        self.history_limit = 50
        self._history_session = self.state.data.active_practice_session
        self.history_meta = ft.Text("", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
        self.older_solves_button = ft.TextButton("Older solves", on_click=self._load_older_solves)
        self.metric_values = [ft.Text("—", size=17, weight=ft.FontWeight.W_600,
                                      color=ft.Colors.ON_SURFACE) for _ in range(6)]
        self._viewport = (1400, 760)
        self.session_dropdown = ft.Dropdown(
            label="Session",
            width=150, height=44, dense=True,
            value=self.state.data.active_practice_session,
            options=[ft.DropdownOption(name, name) for name in self.state.practice_session_names],
            on_select=self._switch_session,
        color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT), hint_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT))

        self.previous_scramble_button = ft.IconButton(
            ft.Icons.CHEVRON_LEFT, tooltip="Previous scramble",
            on_click=self._previous_scramble, disabled=True,
        )
        self.new_scramble_button = ft.IconButton(
            ft.Icons.CHEVRON_RIGHT, tooltip="Next scramble", on_click=self._new_scramble,
        )
        self.success_button = ft.OutlinedButton(
            "Success", icon=ft.Icons.CHECK_CIRCLE, on_click=lambda e: self._mark_last("ok"), disabled=True
        )
        self.plus2_button = ft.OutlinedButton(
            "+2", icon=ft.Icons.ADD, on_click=lambda e: self._mark_last("plus2"), disabled=True
        )
        self.dnf_button = ft.OutlinedButton(
            "DNF", icon=ft.Icons.CANCEL, on_click=lambda e: self._mark_last("dnf"), disabled=True
        )
        self.memo_button = ft.OutlinedButton(
            "Analyze solve", icon=ft.Icons.SHUFFLE, tooltip="Take saved solve to Scramble Memo",
            on_click=self._take_last_to_memo, disabled=True,
        )
        for button in (self.success_button, self.plus2_button, self.dnf_button, self.memo_button):
            button.style = ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=10, vertical=9))

        self._show_menu(update=False)
        self._refresh_stats_and_history(update=False)

    # ---- navigation inside Practice -------------------------------------

    def _practice_card(self, title: str, subtitle: str, icon, enabled: bool, on_click=None):
        return activity_card(title, subtitle, icon,
            "Open Blind Timer" if enabled else "Coming soon",
            on_click=on_click, enabled=enabled)

    def show_menu(self, update: bool = True):
        self._show_menu(update=update)

    def show_timer(self, update: bool = True):
        self._show_timer(update=update)

    def _open_timer_from_practice(self, e=None):
        if self.open_timer_callback:
            self.open_timer_callback()
        else:
            self._show_timer()

    def _back_to_practice(self, e=None):
        if self.running:
            return
        if self.open_practice_callback:
            self.open_practice_callback()
        else:
            self._show_menu()

    def _show_menu(self, e=None, update=True):
        if self.running:
            return
        self.mode = "menu"
        self.scroll = ft.ScrollMode.AUTO
        self._reset_hold_state()
        self.spacing = 12
        self.controls = [
            page_heading("Practice", "Choose a focused session. Build confidence one attempt at a time.", "03 / Repetition"),
            ft.ResponsiveRow([
                self._practice_card("Blind Timer", "Generate scrambles, time full blind attempts, and review your session history.",
                                    ft.Icons.TIMER, True, self._open_timer_from_practice),
                self._practice_card("Progressive Memo", "Memo a real cube one pair at a time, then recall it.",
                                    ft.Icons.PSYCHOLOGY, False),
                self._practice_card("Delayed Recall", "Memo, wait for a countdown, then type what you remember.",
                                    ft.Icons.HOURGLASS_BOTTOM, False),
                self._practice_card("Letter Pair Drill", "Build fast, reliable pair-to-word recall from your dictionary.",
                                    ft.Icons.BOLT, False),
            ], spacing=12, run_spacing=12),
            ft.Text("Blind Timer is ready to use. The other three activities are planned.",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT),
        ]
        if update:
            self._safe_update()

    def _show_timer(self, e=None, update=True):
        self.mode = "timer"
        self.scroll = None
        self.spacing = 0

        self.scramble_text.expand = True
        self._scramble_panel = panel(ft.Row([
            self.scramble_text,
            ft.Row([self.previous_scramble_button, self.new_scramble_button], spacing=0, tight=True),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=12)
        self._timer_hint = ft.Text("Hold Space to arm · Release to start · Any key to stop",
                                  size=11, color=ft.Colors.ON_SURFACE_VARIANT,
                                  text_align=ft.TextAlign.CENTER)
        self._timer_stage = panel(ft.Column([
            self.timer_text, self.status_text, self._timer_hint, self.copy_notice,
        ], spacing=8, alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=16)
        self._result_row = ft.Row([
            self.success_button, self.plus2_button, self.dnf_button, self.memo_button,
        ], spacing=8, wrap=True, alignment=ft.MainAxisAlignment.CENTER)
        self._stats_panel = panel(ft.Row([
            ft.Column([
                ft.Text(label, size=10, color=ft.Colors.ON_SURFACE_VARIANT), value,
            ], spacing=4, expand=True)
            for label, value in zip(("Success / total", "Ao5", "Ao12", "Best single", "Best Ao5", "Best Ao12"), self.metric_values)
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=14)
        self._timer_workspace = ft.Column([
            self._timer_stage, self._result_row, self._stats_panel,
        ], spacing=12)

        self._stats_button = ft.IconButton(ft.Icons.INSIGHTS, tooltip="Session statistics",
                                           on_click=self._show_session_stats, visible=False)
        self.history_panel = panel(ft.Column([
            ft.Container(ft.Row([
                ft.Text("Session history", size=15, weight=ft.FontWeight.W_600,
                        color=ft.Colors.ON_SURFACE, expand=True),
                self._stats_button,
                ft.IconButton(ft.Icons.DELETE_SWEEP_OUTLINED, tooltip="Reset session",
                              icon_size=18, on_click=self._confirm_reset),
            ], spacing=2), height=32),
            self.history,
            ft.Container(ft.Row([
                self.history_meta, self.older_solves_button,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=4), height=28),
        ], spacing=8), padding=12)
        self._main_region = ft.Column(spacing=0)
        self._timer_body = ft.Column([
            ft.Container(ft.Row([
                ft.IconButton(ft.Icons.ARROW_BACK, tooltip="Back to Practice", icon_size=19,
                              on_click=self._back_to_practice),
                ft.Text("Blind Timer", size=23, weight=ft.FontWeight.W_600,
                        color=ft.Colors.ON_SURFACE, expand=True),
                self.session_dropdown,
            ], spacing=8), height=44),
            self._scramble_panel,
            self._main_region,
        ], spacing=12, expand=True)
        # Reflow updates the existing body. The KeyboardListener is created
        # once and stays mounted through resizing, theme changes, and history.
        self.keyboard_listener = ft.KeyboardListener(
            content=self._timer_body, autofocus=True,
            on_key_down=self._on_key_down, on_key_repeat=self._on_key_repeat,
            on_key_up=self._on_key_up, expand=True,
        )
        self.controls = [self.keyboard_listener]
        self._timer_layout_wide = None
        self.set_viewport(*self._viewport)
        self._refresh_stats_and_history(update=False)
        if update:
            self._safe_update()
            self._focus_keyboard_listener()

    def set_viewport(self, width, height):
        """Bound both panels to available space without rebuilding keyboard input."""
        width, height = max(280, float(width)), max(300, float(height))
        self._viewport = (width, height)
        if self.mode != "timer" or not hasattr(self, "_main_region"):
            return
        wide = width >= 1000
        scramble_height = 72 if wide else (90 if width >= 600 else 104)
        main_height = max(120, height - 44 - scramble_height - 24)
        self._scramble_panel.height = scramble_height
        self._scramble_panel.width = width
        self._timer_body.width = width
        self.scramble_text.size = 17 if wide else 14
        self.session_dropdown.width = 150 if wide else 136
        self.success_button.content = "Success" if width >= 600 else "OK"
        self.memo_button.content = "Analyze solve" if width >= 600 else "Analyze"
        self._stats_panel.visible = wide
        self._stats_button.visible = not wide
        if wide:
            history_width = min(420, max(340, width * 0.29))
            timer_width = width - history_width - 20
            history_height = timer_height = main_height
            self._timer_workspace.expand = True
            self.history_panel.width = history_width
            if self._timer_layout_wide is not True:
                self._timer_workspace.controls = [self._timer_stage, self._result_row, self._stats_panel]
                self._main_region.controls = [ft.Row([
                    self._timer_workspace, self.history_panel,
                ], spacing=20, vertical_alignment=ft.CrossAxisAlignment.STRETCH)]
        else:
            timer_width = width
            history_height = min(220, max(100, main_height * 0.37))
            history_height = min(history_height, main_height - 72)
            timer_height = main_height - history_height - 12
            self._timer_workspace.expand = False
            self.history_panel.width = width
            if self._timer_layout_wide is not False:
                self._timer_workspace.controls = [self._timer_stage, self._result_row]
                self._main_region.controls = [ft.Column([
                    self._timer_workspace, self.history_panel,
                ], spacing=12)]
        self._timer_layout_wide = wide
        self._main_region.controls[0].height = main_height
        self._timer_workspace.width = timer_width
        self._timer_workspace.height = timer_height
        self._timer_stage.width = timer_width
        self._stats_panel.width = timer_width
        self._result_row.width = timer_width
        self._stats_panel.height = 76
        self._result_row.height = 40
        # Desktop gives the time the full remaining left panel. Compact
        # screens keep statistics accessible from the history header.
        self._timer_stage.height = max(24, timer_height - (140 if wide else 52))
        self._timer_stage.content.controls = [self.timer_text]
        if self._timer_stage.height >= 64:
            self._timer_stage.content.controls.append(self.status_text)
        if self._timer_stage.height >= 128:
            self._timer_stage.content.controls.append(self._timer_hint)
        if self._timer_stage.height >= 160:
            self._timer_stage.content.controls.append(self.copy_notice)
        self._timer_stage.tooltip = "Hold Space to arm · Release to start · Any key to stop"
        self.history_panel.height = history_height
        self.history.height = max(1, history_height - 100)
        self._main_region.height = main_height
        self._main_region.width = width
        self._timer_width = timer_width
        self._adjust_timer_font()

    def _adjust_timer_font(self):
        if hasattr(self, "_timer_stage"):
            glyphs = max(7, len(self.timer_text.value or "0.00"))
            self.timer_text.size = max(22, min(128, self._timer_stage.height * 0.34,
                                             (self._timer_width - 32) / (glyphs * 0.62)))

    def _load_older_solves(self, e=None):
        self.history_limit += 50
        self._refresh_stats_and_history()
        self._focus_keyboard_listener()

    def _show_session_stats(self, e=None):
        dialog = ft.AlertDialog(
            title=ft.Text("Session statistics", color=ft.Colors.ON_SURFACE),
            content=ft.Text(self.stats_text.value.replace("    ", "\n"),
                            color=ft.Colors.ON_SURFACE),
            actions=[ft.TextButton("Close", on_click=lambda e: self._close_session_stats())],
        )
        show_themed_dialog(self.page, dialog, self.state.data.dark_mode)

    def _close_session_stats(self):
        self.page.pop_dialog()
        self._focus_keyboard_listener()

    def set_active(self, active: bool):
        self.active = bool(active)
        if not self.active:
            self._reset_hold_state()
        elif self.mode == "timer":
            self._focus_keyboard_listener()

    def refresh(self, update: bool = True):
        self.session_dropdown.value = self.state.data.active_practice_session
        self._refresh_stats_and_history(update=False)
        if update and self.page is not None:
            self.update()

    def _switch_session(self, e):
        if self.running:
            # Do not move a running solve between sessions.
            e.control.value = self.state.data.active_practice_session
            self._safe_update()
            return
        name = e.control.value
        self.state.switch_practice_session(name)
        self.last_solve_index = None
        self.current_scramble = self.generator.generate()
        self.scramble_stack = [self.current_scramble]
        self.scramble_index = 0
        self.scramble_text.value = self.current_scramble
        self.previous_scramble_button.disabled = True
        self.timer_text.value = "0.00"
        self.timer_text.color = ft.Colors.ON_SURFACE
        self.status_text.value = ""
        self.memo_button.disabled = True
        self.success_button.disabled = True
        self.plus2_button.disabled = True
        self.dnf_button.disabled = True
        self._refresh_stats_and_history(update=False)
        self._safe_update()
        self._focus_keyboard_listener()

    # ---- keyboard/timer --------------------------------------------------

    def _on_key_repeat(self, e):
        # Repeated Space key-down events are intentionally ignored. The timer
        # is armed from the first key-down and starts only on key-up.
        return

    def _focus_keyboard_listener(self):
        # In Flet 0.86 focus() is async. Calling it without awaiting only creates
        # a coroutine and does not reliably move browser focus, which can leave
        # the timer deaf to Space after navigation.
        if self.page is not None:
            self.page.run_task(self._focus_keyboard_listener_async)

    async def _focus_keyboard_listener_async(self):
        try:
            if self.keyboard_listener is not None and self.keyboard_listener.page is not None:
                await self.keyboard_listener.focus()
        except Exception:
            # Autofocus remains as a fallback when the control is first mounted.
            pass

    def _reset_hold_state(self):
        self.holding_space = False
        self.armed = False
        if not self.running:
            self.timer_text.color = ft.Colors.ON_SURFACE

    def _on_key_down(self, e: ft.KeyDownEvent):
        if not self.active or self.mode != "timer":
            return

        now = time.monotonic()

        # While running, any key stops the timer.
        if self.running:
            self._stop_timer(now)
            return

        # After a solve has stopped, quick keyboard result shortcuts:
        # D = DNF; + or 2 = +2. Space remains reserved for arming the next solve.
        key = (e.key or "").upper()
        if self.last_solve_index is not None and not self.holding_space:
            if key == "D":
                self._mark_last("dnf")
                return
            if e.key in {"+", "2", "Add", "NumpadAdd"}:
                self._mark_last("plus2")
                return

        if e.key in self.SPACE_KEYS and not self.holding_space:
            self.holding_space = True
            self.armed = False
            self.status_text.value = ""
            self.timer_text.value = "0.00"
            self.timer_text.color = ft.Colors.ON_SURFACE
            self._safe_update()
            self.page.run_task(self._arm_after_delay)

    def _on_key_up(self, e: ft.KeyUpEvent):
        if not self.active or self.mode != "timer":
            return
        if e.key not in self.SPACE_KEYS or not self.holding_space:
            return

        now = time.monotonic()
        if self.armed:
            self.holding_space = False
            self.armed = False
            self._start_timer(now)
        else:
            # Released before the arm delay elapsed -- a quick tap, not a
            # hold. Cancel rather than starting the timer.
            self._reset_hold_state()
            self.status_text.value = ""
            self._safe_update()

    async def _arm_after_delay(self):
        await asyncio.sleep(self.HOLD_ARM_SECONDS)
        if self.holding_space and not self.armed and self.active and self.mode == "timer" and not self.running:
            self.armed = True
            self.timer_text.color = ft.Colors.PRIMARY
            self._safe_update()

    async def _tick_loop(self):
        while self.running:
            await asyncio.sleep(0.2)
            if not self.running:
                break
            now = time.monotonic()
            elapsed = max(0.0, now - self.started_at)
            whole = int(elapsed)
            if whole != self.last_display_second:
                self.last_display_second = whole
                if whole >= 60:
                    m, s = divmod(whole, 60)
                    self.timer_text.value = f"{m}:{s:02d}"
                else:
                    self.timer_text.value = str(whole)
                self._safe_update()

    def _start_timer(self, now: float):
        self.running = True
        self.started_at = now
        self.last_display_second = -1
        self.timer_text.color = ft.Colors.ON_SURFACE
        self.status_text.value = "RUNNING — press any key to stop"
        self.previous_scramble_button.disabled = True
        self.new_scramble_button.disabled = True
        self.success_button.disabled = True
        self.plus2_button.disabled = True
        self.dnf_button.disabled = True
        self.memo_button.disabled = True
        self._safe_update()
        self.page.run_task(self._tick_loop)

    def _stop_timer(self, now: float):
        elapsed = max(0.0, now - self.started_at)
        self.running = False
        centiseconds = max(0, int(round(elapsed * 100)))
        solved_scramble = self.current_scramble
        self.timer_text.value = _format_centiseconds(centiseconds)
        self.timer_text.color = ft.Colors.ON_SURFACE
        self.status_text.value = "Stopped — mark Success, +2, or DNF"
        self.last_solve_index = self.state.add_practice_solve(
            centiseconds, solved_scramble, dnf=False, plus2=False
        )
        self.success_button.disabled = False
        self.plus2_button.disabled = False
        self.dnf_button.disabled = False
        self.memo_button.disabled = False
        self.new_scramble_button.disabled = False

        # Prepare the next scramble immediately, while leaving the just-finished
        # time and result controls on screen. The result buttons still refer to
        # last_solve_index, i.e. the solve that just ended.
        self._advance_to_fresh_scramble_preserving_result()

        self._refresh_stats_and_history(update=False)
        self._safe_update()
        self._focus_keyboard_listener()

    def _advance_to_fresh_scramble_preserving_result(self):
        if self.scramble_index < len(self.scramble_stack) - 1:
            self.scramble_index += 1
        else:
            self.scramble_stack.append(self.generator.generate())
            self.scramble_index += 1
        self.current_scramble = self.scramble_stack[self.scramble_index]
        self.scramble_text.value = self.current_scramble
        self.previous_scramble_button.disabled = self.scramble_index <= 0

    def _safe_update(self):
        self._adjust_timer_font()
        if self.page is not None:
            self.update()

    # ---- scramble / result controls -------------------------------------

    def _show_scramble_at_index(self):
        self.current_scramble = self.scramble_stack[self.scramble_index]
        self.scramble_text.value = self.current_scramble
        self.previous_scramble_button.disabled = self.scramble_index <= 0

        # If this scramble already has a solve, restore its latest saved result
        # so a user can go back and capture the time + scramble together.
        matching = [
            (i, s) for i, s in enumerate(self.state.data.practice_solves)
            if s.scramble == self.current_scramble
        ]
        if matching:
            idx, solve = matching[-1]
            self.last_solve_index = idx
            if solve.dnf:
                self.timer_text.value = f"DNF ({_format_centiseconds(solve.centiseconds)})"
                self.status_text.value = "Previous scramble — saved result: DNF"
            else:
                effective = _effective_centiseconds(solve)
                self.timer_text.value = _format_centiseconds(effective) + ("+" if getattr(solve, "plus2", False) else "")
                self.status_text.value = "Previous scramble — saved result"
            self.memo_button.disabled = False
            self.success_button.disabled = False
            self.plus2_button.disabled = False
            self.dnf_button.disabled = False
        else:
            self.last_solve_index = None
            # Keep the last displayed result on screen. It resets to 0.00 only
            # when Space is held to arm the next solve.
            self.status_text.value = ""
            self.memo_button.disabled = True
            self.success_button.disabled = True
            self.plus2_button.disabled = True
            self.dnf_button.disabled = True
        self.timer_text.color = ft.Colors.ON_SURFACE

    def _new_scramble(self, e=None):
        if self.running:
            return
        if self.scramble_index < len(self.scramble_stack) - 1:
            self.scramble_index += 1
        else:
            self.scramble_stack.append(self.generator.generate())
            self.scramble_index += 1
        self._show_scramble_at_index()
        self._safe_update()
        self._focus_keyboard_listener()

    def _previous_scramble(self, e=None):
        if self.running or self.scramble_index <= 0:
            return
        self.scramble_index -= 1
        self._show_scramble_at_index()
        self._safe_update()
        self._focus_keyboard_listener()

    def _mark_last(self, result: str):
        if self.last_solve_index is None:
            return
        solves = self.state.data.practice_solves
        if not (0 <= self.last_solve_index < len(solves)):
            return

        solve = solves[self.last_solve_index]
        raw_time = _format_centiseconds(solve.centiseconds)

        if result == "dnf":
            self.state.set_practice_solve_result(self.last_solve_index, dnf=True, plus2=False)
            self.timer_text.value = f"DNF ({raw_time})"
            self.status_text.value = "DNF"
        elif result == "plus2":
            self.state.set_practice_solve_result(self.last_solve_index, dnf=False, plus2=True)
            # Show the penalized time immediately. Internally the solve keeps
            # its measured time plus a +2 flag, so stats still use 37.26 for
            # a measured 35.26 without losing the original measurement.
            self.timer_text.value = _format_centiseconds(solve.centiseconds + 200) + "+"
            self.status_text.value = "+2"
        else:
            self.state.set_practice_solve_result(self.last_solve_index, dnf=False, plus2=False)
            self.timer_text.value = raw_time
            self.status_text.value = "Success"
        self._refresh_stats_and_history(update=False)
        self._safe_update()
        self._focus_keyboard_listener()

    def _take_last_to_memo(self, e=None):
        if self.last_solve_index is None or not self.open_memo_callback:
            return
        solves = self.state.data.practice_solves
        if 0 <= self.last_solve_index < len(solves):
            self.open_memo_callback(solves[self.last_solve_index].scramble)

    def _open_solve_memo(self, scramble: str):
        if self.open_memo_callback:
            self.open_memo_callback(scramble)

    # ---- statistics/history ---------------------------------------------

    def _refresh_stats_and_history(self, update=True):
        solves = self.state.data.practice_solves
        if self._history_session != self.state.data.active_practice_session:
            self._history_session = self.state.data.active_practice_session
            self.history_limit = 50
        successes = sum(1 for s in solves if not s.dnf)
        ao5 = _wca_average(solves, 5)
        ao12 = _wca_average(solves, 12)
        best_ao5 = _best_wca_average(solves, 5)
        best_ao12 = _best_wca_average(solves, 12)
        best = min((_effective_centiseconds(s) for s in solves if not s.dnf), default=None)

        def fmt_avg(value):
            if value is None:
                return "—"
            if value == "DNF":
                return "DNF"
            return _format_centiseconds(value)

        self.stats_text.value = (
            f"Successful / total: {successes}/{len(solves)}    "
            f"Ao5: {fmt_avg(ao5)}    Ao12: {fmt_avg(ao12)}    "
            f"Best single: {_format_centiseconds(best) if best is not None else '—'}    "
            f"Best Ao5: {fmt_avg(best_ao5)}    Best Ao12: {fmt_avg(best_ao12)}"
        )

        metric_texts = (
            f"{successes}/{len(solves)}", fmt_avg(ao5), fmt_avg(ao12),
            _format_centiseconds(best) if best is not None else "—", fmt_avg(best_ao5), fmt_avg(best_ao12),
        )
        for control, value in zip(self.metric_values, metric_texts):
            control.value = value
        shown = min(len(solves), self.history_limit)
        self.history_meta.value = f"{shown} of {len(solves)} solves · newest first"
        self.older_solves_button.visible = shown < len(solves)
        rows = []
        for idx in range(len(solves) - 1, len(solves) - shown - 1, -1):
            solve = solves[idx]
            effective = _effective_centiseconds(solve)
            if solve.dnf:
                result = f"DNF ({_format_centiseconds(solve.centiseconds)})"
                result_color = ft.Colors.ERROR
            else:
                result = _format_centiseconds(effective) + ("+" if getattr(solve, "plus2", False) else "")
                result_color = ft.Colors.PRIMARY if best is not None and effective == best else ft.Colors.ON_SURFACE

            rows.append(
                ft.Container(
                    ft.Column([
                        ft.Row([
                            ft.Text(f"#{idx + 1}", width=36, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Container(
                                content=ft.Text(result, size=16, weight=ft.FontWeight.W_600, color=result_color),
                                expand=True, tooltip="Click to copy time + scramble",
                                padding=ft.Padding.symmetric(vertical=4),
                                on_click=lambda e, s=solve: self._copy_time_and_scramble(s),
                            ),
                            ft.IconButton(ft.Icons.SHUFFLE, icon_size=17, tooltip="Take to Scramble Memo",
                                          on_click=lambda e, s=solve.scramble: self._open_solve_memo(s)),
                            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=17, tooltip="Delete solve",
                                          on_click=lambda e, i=idx: self._delete_solve(i)),
                        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.GestureDetector(
                            content=ft.Text(solve.scramble, size=11, max_lines=2,
                                            color=ft.Colors.ON_SURFACE_VARIANT, tooltip="Click to copy scramble"),
                            on_tap=lambda e, text=solve.scramble: self._copy_text(text, "Scramble copied"),
                        ),
                    ], spacing=2),
                    padding=ft.Padding.symmetric(horizontal=4, vertical=10),
                    border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
                )
            )
        self.history.controls = rows or [ft.Text("No solves yet.", italic=True, color=ft.Colors.ON_SURFACE)]
        if update:
            self._safe_update()

    def _copy_text(self, text: str, message: str = "Copied"):
        try:
            self.page.set_clipboard(text)
            self._show_copy_notice(message)
            self._focus_keyboard_listener()
        except Exception:
            pass

    def _show_copy_notice(self, message: str):
        self._copy_notice_token += 1
        token = self._copy_notice_token
        self.copy_notice.value = message
        self.copy_notice.opacity = 1
        self._safe_update()
        self.page.run_task(self._fade_copy_notice, token)

    async def _fade_copy_notice(self, token: int):
        await asyncio.sleep(2.0)
        if token != self._copy_notice_token:
            return
        try:
            self.copy_notice.opacity = 0
            self._safe_update()
            await asyncio.sleep(0.35)
            if token == self._copy_notice_token:
                self.copy_notice.value = ""
                self._safe_update()
        except Exception:
            pass

    def _copy_time_and_scramble(self, solve):
        if solve.dnf:
            result = f"DNF ({_format_centiseconds(solve.centiseconds)})"
        else:
            result = _format_centiseconds(_effective_centiseconds(solve))
            if getattr(solve, "plus2", False):
                result += "+"
        self._copy_text(f"{result} - {solve.scramble}", "Time + scramble copied")

    def _delete_solve(self, index: int):
        self.state.delete_practice_solve(index)
        self.last_solve_index = None
        self._refresh_stats_and_history()
        self._focus_keyboard_listener()

    def _confirm_reset(self, e=None):
        def close(dialog=None):
            self.page.pop_dialog()

        def reset(dialog=None):
            self.state.reset_practice_session()
            self.last_solve_index = None
            close()
            self._refresh_stats_and_history()
            self._focus_keyboard_listener()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Reset timer session?", color=ft.Colors.ON_SURFACE),
            content=ft.Text("This deletes all saved timer solves in the current session.", color=ft.Colors.ON_SURFACE),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: close(dialog)),
                ft.TextButton("Reset", on_click=lambda e: reset(dialog)),
            ],
        )
        show_themed_dialog(self.page, dialog, self.state.data.dark_mode)
