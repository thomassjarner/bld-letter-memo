"""Practice navigation; the approved Blind Timer remains a separate control."""
import flet as ft

from ui.design import activity_card, page_heading
from ui.pages.progressive_memo_page import ProgressiveMemoPage
from ui.theme_colors import ThemeAwarePage


@ft.control
class PracticeHubPage(ThemeAwarePage, ft.Column):
    open_timer_callback = None
    open_memo_callback = None
    open_scheme_callback = None

    @property
    def state(self):
        return self.data

    def init(self):
        self.expand = True
        self.active = False
        self.mode = "menu"
        self.progressive = ProgressiveMemoPage(data=self.state)
        self.progressive.back_callback = self.show_menu
        self.show_menu(update=False)

    def show_menu(self, e=None, update=True):
        self.progressive.set_active(False)
        self.active = False
        self.mode = "menu"
        self.scroll = ft.ScrollMode.AUTO
        self.spacing = 12
        self.controls = [
            page_heading("Practice", "Choose a focused session. Build confidence one attempt at a time.", "03 / Repetition"),
            ft.ResponsiveRow([
                activity_card("Blind Timer", "Generate scrambles, time full blind attempts, and review your session history.",
                              ft.Icons.TIMER, "Open Blind Timer", lambda e: self.open_timer_callback()),
                activity_card("Progressive Memo", "Memo a real scramble one pair at a time, then type your recall and check your accuracy.",
                              ft.Icons.PSYCHOLOGY, "Open Progressive Memo", self.open_progressive),
                activity_card("Delayed Recall", "Memo, wait for a countdown, then type what you remember.",
                              ft.Icons.HOURGLASS_BOTTOM, "Coming soon", enabled=False),
                activity_card("Letter Pair Drill", "Build fast, reliable pair-to-word recall from your dictionary.",
                              ft.Icons.BOLT, "Coming soon", enabled=False),
            ], spacing=12, run_spacing=12),
            ft.Text("Blind Timer and Progressive Memo are ready. Delayed Recall and Letter Pair Drill are planned.",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT),
        ]
        if update and self.page is not None:
            self.update()

    def open_progressive(self, e=None):
        self.mode = "progressive"
        self.scroll = None
        self.spacing = 0
        self.progressive.open_scheme_callback = self.open_scheme_callback
        self.controls = [self.progressive]
        self.progressive.refresh(update=False)
        if self.page is not None:
            self.update()
        self.set_active(True)

    def set_active(self, active):
        self.active = bool(active) and self.mode == "progressive"
        self.progressive.set_active(self.active)

    def set_viewport(self, width, height):
        self.width, self.height = width, height
        self.progressive.set_viewport(width, height)

    def refresh(self, update=True):
        if self.mode == "progressive":
            self.progressive.refresh(update=update)

