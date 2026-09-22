from __future__ import annotations

import threading
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


class PracticePage(ft.Column):
    """Practice hub plus Blind Timer.

    Flet 0.24.1 only exposes key-down notifications. On macOS, holding Space
    generates repeated key-down events. The timer uses those repeat events to
    know that Space is still held, turns green once armed, then treats the end
    of the repeat stream as the release. A tiny hidden TextField keeps keyboard
    focus so holding Space does not trigger the system's repeated alert beep.
    """

    HOLD_ARM_SECONDS = 0.35
    RELEASE_SILENCE_SECONDS = 0.12
    TAP_CANCEL_SECONDS = 1.60

    def __init__(self, page: ft.Page, state, open_memo_callback=None):
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO)
        self.page_ref = page
        self.state = state
        self.open_memo_callback = open_memo_callback
        self.generator = ScrambleGenerator()

        self.mode = "menu"
        self.active = False
        self._alive = True

        self.current_scramble = self.generator.generate()
        self.scramble_stack = [self.current_scramble]
        self.scramble_index = 0

        self.running = False
        self.holding_space = False
        self.armed = False
        self.space_event_count = 0
        self.space_hold_started = 0.0
        self.last_space_event = 0.0
        self.started_at = 0.0
        self.last_display_second = -1
        self.last_solve_index = None

        # Keeping focus in a text control prevents the repeated macOS alert
        # sound that otherwise happens when Space is held on an unfocused UI.
        self.keyboard_sink = ft.TextField(
            value="",
            width=1,
            height=1,
            text_size=1,
            border=ft.InputBorder.NONE,
            color=ft.Colors.TRANSPARENT,
            bgcolor=ft.Colors.TRANSPARENT,
            autofocus=True,
            on_change=self._on_sink_change,
        )

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

        self.page_ref.on_keyboard_event = self._on_keyboard
        self._show_menu(update=False)
        self._refresh_stats_and_history(update=False)
        threading.Thread(target=self._watch_loop, daemon=True).start()

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
            border=ft.border.all(1, ft.Colors.OUTLINE),
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
        self.controls = [
            ft.Row([
                ft.IconButton(ft.Icons.ARROW_BACK, tooltip="Back to Practice", on_click=self._show_menu),
                ft.Text("Practice — Blind Timer", size=20, weight=ft.FontWeight.BOLD),
            ]),
            ft.Container(self.scramble_text, padding=12, border=ft.border.all(1, ft.Colors.OUTLINE), border_radius=8),
            ft.Row(
                [self.previous_scramble_button, self.new_scramble_button],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Container(
                ft.Column(
                    [self.timer_text, self.status_text, self.keyboard_sink],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                ),
                alignment=ft.alignment.center,
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
        ]
        self._refresh_stats_and_history(update=False)
        if update:
            self._safe_update()
            self._focus_keyboard_sink()
            self._focus_keyboard_sink_delayed()

    def set_active(self, active: bool):
        self.active = bool(active)
        if not self.active:
            self._reset_hold_state()
        elif self.mode == "timer":
            self._focus_keyboard_sink()

    def refresh(self, update: bool = True):
        self._refresh_stats_and_history(update=False)
        if update and self.page is not None:
            self.update()

    # ---- keyboard/timer --------------------------------------------------

    def _focus_keyboard_sink(self):
        try:
            if self.keyboard_sink.page is not None:
                self.keyboard_sink.focus()
        except Exception:
            pass

    def _focus_keyboard_sink_delayed(self):
        # Flet may mount the timer controls a fraction after the view update.
        # Focusing again shortly afterward avoids the first Space press being
        # used only to acquire keyboard focus on macOS.
        def worker():
            time.sleep(0.08)
            self._focus_keyboard_sink()
        threading.Thread(target=worker, daemon=True).start()

    def _reset_hold_state(self):
        self.holding_space = False
        self.armed = False
        self.space_event_count = 0
        if not self.running:
            self.timer_text.color = None

    def _on_keyboard(self, e):
        if not self.active or self.mode != "timer":
            return

        now = time.monotonic()

        # While running, any keyboard key stops the timer. Before the timer
        # starts, Space itself is handled by the focused keyboard sink below.
        # That makes the very first held Space press usable on macOS/Flet
        # 0.24.x instead of being consumed merely to acquire focus.
        if self.running:
            self._stop_timer(now)

    def _on_sink_change(self, e):
        if not self.active or self.mode != "timer":
            e.control.value = ""
            return

        text = e.control.value or ""
        e.control.value = ""

        now = time.monotonic()
        if self.running:
            # Printable keys may be consumed by the focused TextField before
            # Page.on_keyboard_event sees them, so stop here as well.
            if text:
                self._stop_timer(now)
            return

        # The sink accepts Space as ordinary text. This prevents the macOS
        # alert beep and, unlike Page.on_keyboard_event, captures the first
        # press immediately. Repeated spaces while held let the watch loop
        # distinguish a hold from a quick tap; release is inferred from the
        # repeat stream going silent.
        for ch in text:
            if ch == " ":
                if not self.holding_space:
                    self.holding_space = True
                    self.armed = False
                    self.space_event_count = 1
                    self.space_hold_started = now
                    self.last_space_event = now
                    self.status_text.value = ""
                    self.timer_text.value = "0.00"
                    self.timer_text.color = None
                    self._safe_update()
                else:
                    self.space_event_count += 1
                    self.last_space_event = now

    def _watch_loop(self):
        while self._alive:
            now = time.monotonic()
            try:
                if self.active and self.mode == "timer" and self.holding_space:
                    held = now - self.space_hold_started
                    silence = now - self.last_space_event
                    repeated = self.space_event_count >= 2

                    if repeated and held >= self.HOLD_ARM_SECONDS and not self.armed:
                        self.armed = True
                        self.timer_text.color = ft.Colors.GREEN
                        self.status_text.value = ""
                        self._safe_update()

                    if self.armed and silence >= self.RELEASE_SILENCE_SECONDS:
                        self.holding_space = False
                        self.armed = False
                        self._start_timer(now)
                    elif not repeated and held >= self.TAP_CANCEL_SECONDS:
                        # A quick tap produces no repeat stream; cancel rather
                        # than accidentally starting the timer.
                        self._reset_hold_state()
                        self.status_text.value = ""
                        self._safe_update()

                if self.running:
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
            except Exception:
                # Measurement remains monotonic even if a UI update happens
                # while the user navigates.
                pass
            time.sleep(0.02)

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
        self._focus_keyboard_sink()

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
        self._focus_keyboard_sink()

    def _previous_scramble(self, e=None):
        if self.running or self.scramble_index <= 0:
            return
        self.scramble_index -= 1
        self._show_scramble_at_index()
        self._safe_update()
        self._focus_keyboard_sink()

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
        self._focus_keyboard_sink()

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
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=6,
                )
            )
        self.history.controls = rows or [ft.Text("No solves yet.", italic=True)]
        if update:
            self._safe_update()

    def _copy_text(self, text: str, message: str = "Copied"):
        try:
            self.page_ref.set_clipboard(text)
            self._show_copy_notice(message)
            self._focus_keyboard_sink_delayed()
        except Exception:
            pass

    def _show_copy_notice(self, message: str):
        self._copy_notice_token += 1
        token = self._copy_notice_token
        self.copy_notice.value = message
        self.copy_notice.opacity = 1
        self._safe_update()

        def fade():
            time.sleep(3.0)
            if token != self._copy_notice_token:
                return
            try:
                self.copy_notice.opacity = 0
                self._safe_update()
                time.sleep(0.35)
                if token == self._copy_notice_token:
                    self.copy_notice.value = ""
                    self._safe_update()
            except Exception:
                pass

        threading.Thread(target=fade, daemon=True).start()

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
        self._focus_keyboard_sink()

    def _confirm_reset(self, e=None):
        def close(dialog):
            self.page_ref.close(dialog)

        def reset(dialog):
            self.state.reset_practice_session()
            self.last_solve_index = None
            close(dialog)
            self._refresh_stats_and_history()
            self._focus_keyboard_sink()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Reset timer session?"),
            content=ft.Text("This deletes all saved timer solves in the current session."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: close(dialog)),
                ft.TextButton("Reset", on_click=lambda e: reset(dialog)),
            ],
        )
        self.page_ref.open(dialog)
