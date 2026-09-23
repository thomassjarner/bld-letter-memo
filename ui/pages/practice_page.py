from __future__ import annotations

from dataclasses import field

import asyncio
import time

import flet as ft

from core.scramble_generator import ScrambleGenerator


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


@ft.control
class PracticePage(ft.Column):
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

    HOLD_ARM_SECONDS = 0.35
    SPACE_KEYS = (" ", "Space")

    state: object | None = field(default=None, metadata={"skip": True})
    open_memo_callback: object | None = field(default=None, metadata={"skip": True})

    def init(self):
        self.expand = True
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

        self.scramble_text = ft.Text(self.current_scramble, size=18, selectable=True)
        self.timer_text = ft.Text("0.00", size=64, weight=ft.FontWeight.BOLD)
        self.status_text = ft.Text("", size=14)
        self.stats_text = ft.Text("")
        self.copy_notice = ft.Text("", opacity=0, animate_opacity=300, size=12)
        self._copy_notice_token = 0
        self.history = ft.Column(spacing=6)

        self.previous_scramble_button = ft.OutlinedButton(
            "Previous", icon=ft.Icons.ARROW_BACK, on_click=self._previous_scramble, disabled=True
        )
        self.new_scramble_button = ft.OutlinedButton(
            "Next scramble", icon=ft.Icons.ARROW_FORWARD, on_click=self._new_scramble
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
        self.memo_button = ft.ElevatedButton(
            "Take to Scramble Memo", icon=ft.Icons.SHUFFLE, on_click=self._take_last_to_memo, disabled=True
        )

        self._show_menu(update=False)
        self._refresh_stats_and_history(update=False)

    # ---- navigation inside Practice -------------------------------------

    def _practice_card(self, title: str, subtitle: str, icon, enabled: bool, on_click=None):
        button = ft.ElevatedButton(
            title if enabled else f"{title} — coming soon",
            icon=icon,
            on_click=on_click if enabled else None,
            disabled=not enabled,
        )
        return ft.Container(
            content=ft.Column([
                ft.Icon(icon, size=34),
                ft.Text(title, size=18, weight=ft.FontWeight.BOLD),
                ft.Text(subtitle, color=ft.Colors.ON_SURFACE_VARIANT),
                button,
            ], spacing=8),
            padding=16,
            border=ft.Border.all(1, ft.Colors.OUTLINE),
            border_radius=10,
            width=340,
        )

    def _show_menu(self, e=None, update=True):
        if self.running:
            return
        self.mode = "menu"
        self._reset_hold_state()
        self.controls = [
            ft.Text("Practice", size=22, weight=ft.FontWeight.BOLD),
            ft.Text("Choose a practice activity.", color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Row([
                self._practice_card(
                    "Blind Timer",
                    "Generate a scramble and time a full blind attempt.",
                    ft.Icons.TIMER,
                    True,
                    self._show_timer,
                ),
                self._practice_card(
                    "Progressive Memo",
                    "Memo a real cube one pair at a time, then recall it.",
                    ft.Icons.PSYCHOLOGY,
                    False,
                ),
            ], wrap=True, spacing=12, run_spacing=12),
            ft.Row([
                self._practice_card(
                    "Delayed Recall",
                    "Memo, wait for a countdown, then type what you remember.",
                    ft.Icons.HOURGLASS_BOTTOM,
                    False,
                ),
                self._practice_card(
                    "Letter Pair Drill",
                    "Practice fast pair-to-word recall.",
                    ft.Icons.BOLT,
                    False,
                ),
            ], wrap=True, spacing=12, run_spacing=12),
        ]
        if update:
            self._safe_update()

    def _show_timer(self, e=None, update=True):
        self.mode = "timer"
        body = ft.Column(
            [
                ft.Row([
                    ft.IconButton(ft.Icons.ARROW_BACK, tooltip="Back to Practice", on_click=self._show_menu),
                    ft.Text("Practice — Blind Timer", size=20, weight=ft.FontWeight.BOLD),
                ]),
                ft.Container(self.scramble_text, padding=12, border=ft.Border.all(1, ft.Colors.OUTLINE), border_radius=8),
                ft.Row(
                    [self.previous_scramble_button, self.new_scramble_button],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Container(
                    ft.Column(
                        [self.timer_text, self.status_text],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    alignment=ft.Alignment.CENTER,
                    padding=36,
                    height=250,
                ),
                ft.Row([self.success_button, self.plus2_button, self.dnf_button, self.memo_button], wrap=True),
                ft.Divider(),
                self.stats_text,
                ft.Row([
                    ft.Text("Session solves", size=18, weight=ft.FontWeight.BOLD),
                    ft.TextButton("Reset session", icon=ft.Icons.DELETE_SWEEP, on_click=self._confirm_reset),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                self.copy_notice,
                self.history,
            ],
        )
        self.keyboard_listener = ft.KeyboardListener(
            content=body,
            autofocus=True,
            on_key_down=self._on_key_down,
            on_key_up=self._on_key_up,
        )
        self.controls = [self.keyboard_listener]
        self._refresh_stats_and_history(update=False)
        if update:
            self._safe_update()
            self._focus_keyboard_listener()

    def set_active(self, active: bool):
        self.active = bool(active)
        if not self.active:
            self._reset_hold_state()
        elif self.mode == "timer":
            self._focus_keyboard_listener()

    def refresh(self, update: bool = True):
        self._refresh_stats_and_history(update=False)
        if update and self.page is not None:
            self.update()

    # ---- keyboard/timer --------------------------------------------------

    def _focus_keyboard_listener(self):
        try:
            if self.keyboard_listener is not None and self.keyboard_listener.page is not None:
                self.keyboard_listener.focus()
        except Exception:
            pass

    def _reset_hold_state(self):
        self.holding_space = False
        self.armed = False
        if not self.running:
            self.timer_text.color = None

    def _on_key_down(self, e: ft.KeyDownEvent):
        if not self.active or self.mode != "timer":
            return

        now = time.monotonic()

        # While running, any key stops the timer.
        if self.running:
            self._stop_timer(now)
            return

        if e.key in self.SPACE_KEYS and not self.holding_space:
            self.holding_space = True
            self.armed = False
            self.status_text.value = ""
            self.timer_text.value = "0.00"
            self.timer_text.color = None
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
            self.timer_text.color = ft.Colors.GREEN
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
        self.timer_text.color = None
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
        self.timer_text.value = _format_centiseconds(centiseconds)
        self.timer_text.color = None
        self.status_text.value = "Stopped — mark Success, +2, or DNF"
        self.last_solve_index = self.state.add_practice_solve(centiseconds, self.current_scramble, dnf=False, plus2=False)
        self.success_button.disabled = False
        self.plus2_button.disabled = False
        self.dnf_button.disabled = False
        self.memo_button.disabled = False
        self.previous_scramble_button.disabled = self.scramble_index <= 0
        self.new_scramble_button.disabled = False
        self._refresh_stats_and_history(update=False)
        self._safe_update()
        self._focus_keyboard_listener()

    def _safe_update(self):
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
                self.timer_text.value = "DNF"
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
        self.timer_text.color = None

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
        if result == "dnf":
            self.state.set_practice_solve_result(self.last_solve_index, dnf=True, plus2=False)
            self.status_text.value = "DNF"
        elif result == "plus2":
            self.state.set_practice_solve_result(self.last_solve_index, dnf=False, plus2=True)
            self.status_text.value = "+2"
        else:
            self.state.set_practice_solve_result(self.last_solve_index, dnf=False, plus2=False)
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
        successes = sum(1 for s in solves if not s.dnf)
        ao5 = _wca_average(solves, 5)
        ao12 = _wca_average(solves, 12)
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
            f"Best: {_format_centiseconds(best) if best is not None else '—'}"
        )

        rows = []
        for idx in range(len(solves) - 1, max(-1, len(solves) - 30), -1):
            solve = solves[idx]
            effective = _effective_centiseconds(solve)
            if solve.dnf:
                result = "DNF"
                result_color = ft.Colors.ERROR
            else:
                result = _format_centiseconds(effective) + ("+" if getattr(solve, "plus2", False) else "")
                result_color = ft.Colors.GREEN if best is not None and effective == best else None

            rows.append(
                ft.Container(
                    ft.Row([
                        ft.Text(f"#{idx + 1}", width=50),
                        ft.GestureDetector(
                            content=ft.Text(result, width=90, weight=ft.FontWeight.BOLD, color=result_color),
                            on_tap=lambda e, s=solve: self._copy_time_and_scramble(s),
                        ),
                        ft.GestureDetector(
                            content=ft.Text(solve.scramble, expand=True, max_lines=2, tooltip="Click to copy scramble"),
                            on_tap=lambda e, text=solve.scramble: self._copy_text(text, "Scramble copied"),
                        ),
                        ft.IconButton(ft.Icons.SHUFFLE, tooltip="Take to Scramble Memo", on_click=lambda e, s=solve.scramble: self._open_solve_memo(s)),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Delete solve", on_click=lambda e, i=idx: self._delete_solve(i)),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=8,
                    border=ft.Border.all(1, ft.Colors.OUTLINE),
                    border_radius=6,
                )
            )
        self.history.controls = rows or [ft.Text("No solves yet.", italic=True)]
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
        await asyncio.sleep(3.0)
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
            result = "DNF"
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
        def close(dialog):
            self.page.close(dialog)

        def reset(dialog):
            self.state.reset_practice_session()
            self.last_solve_index = None
            close(dialog)
            self._refresh_stats_and_history()
            self._focus_keyboard_listener()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Reset timer session?"),
            content=ft.Text("This deletes all saved timer solves in the current session."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: close(dialog)),
                ft.TextButton("Reset", on_click=lambda e: reset(dialog)),
            ],
        )
        self.page.open(dialog)
