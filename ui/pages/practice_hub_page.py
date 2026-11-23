"""Practice navigation; the approved Blind Timer remains a separate control."""
import flet as ft

from ui.design import activity_card, page_heading
from ui.navigation_motion import route_switcher
from ui.pages.progressive_memo_page import ProgressiveMemoPage
from ui.theme_colors import ThemeAwarePage


@ft.control
class PracticeHubPage(ThemeAwarePage, ft.Column):
    open_timer_callback = None
    open_trainer_callback = None
    open_memo_callback = None
    open_scheme_callback = None

    @property
    def state(self):
        return self.data

    def _mounted(self):
        try:
            return self.page is not None
        except RuntimeError:
            return False

    def init(self):
        self.expand = True
        self.active = False
        self.mode = "menu"
        self._viewport = (1400, 760)
        self.progressive = ProgressiveMemoPage(data=self.state)
        self.progressive.key = "practice_memo"
        self.progressive.back_callback = self.show_menu
        self.menu = ft.Column(key="practice_activities", scroll=ft.ScrollMode.AUTO, spacing=12,
                              horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.switcher = route_switcher(self.menu, expand=True)
        self.controls = [self.switcher]
        self.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        self.show_menu(update=False)

    def show_menu(self, e=None, update=True):
        self.progressive.set_active(False)
        self.active = False
        self.mode = "menu"
        self.scroll = None
        self.spacing = 0
        activities = [
            activity_card("Blind Timer", "Time a blind solve and compare it with your session history.",
                          ft.Icons.TIMER, "Open Blind Timer", lambda e: self.open_timer_callback(),
                          "Timed solves", feature="timer"),
            activity_card("Progressive Memo", "Memo a scramble one pair at a time, then type what you remember.",
                          ft.Icons.PSYCHOLOGY, "Open Progressive Memo", self.open_progressive,
                          "Letter recall", feature="progressive"),
            activity_card("3-style corner trainer", "Choose corner cases, recall their algorithms, then retry the ones you missed.",
                          ft.Icons.SCHOOL_OUTLINED, "Open corner trainer", lambda e: self.open_trainer_callback(),
                          "Algorithm recall", feature="trainer"),
        ]
        for card in activities:
            card.col = {"xs": 12, "md": 6, "lg": 4}
        self.menu.controls = [
            page_heading("Practice", "Choose what to train: complete solves, memo, or corner algorithms."),
            ft.ResponsiveRow(activities, spacing=12, run_spacing=12),
            ft.ExpansionTile(title=ft.Text("More practice modes", size=14, color=ft.Colors.ON_SURFACE),
                subtitle=ft.Text("Planned activities", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                expanded=False, maintain_state=True, dense=True, tile_padding=0, controls_padding=8,
                expanded_cross_axis_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[ft.ResponsiveRow([
                activity_card("Delayed Recall", "Memo, wait for a countdown, then type what you remember.",
                              ft.Icons.HOURGLASS_BOTTOM, "Coming soon", enabled=False, feature="delayed"),
                activity_card("Letter Pair Drill", "Build fast, reliable pair-to-word recall from your dictionary.",
                              ft.Icons.BOLT, "Coming soon", enabled=False, feature="drill"),
            ], spacing=12, run_spacing=12)]),
        ]
        self.switcher.content = self.menu
        if update and self._mounted():
            self.update()

    def open_progressive(self, e=None):
        self.mode = "progressive"
        self.scroll = None
        self.spacing = 0
        self.progressive.open_scheme_callback = self.open_scheme_callback
        self.switcher.content = self.progressive
        self.progressive.refresh(update=False)
        if self._mounted():
            self.update()
        self.set_active(True)

    def set_active(self, active):
        self.active = bool(active) and self.mode == "progressive"
        self.progressive.set_active(self.active and self.mode == "progressive")

    def set_viewport(self, width, height):
        self.width, self.height = width, height
        self._viewport = (width, height)
        self.menu.width, self.menu.height = width, height
        self.progressive.set_viewport(width, height)

    def refresh(self, update=True):
        if self.mode == "progressive":
            self.progressive.refresh(update=update)

