"""An introduction and route chooser, deliberately without embedded tools."""
import flet as ft
from ui.theme_colors import ThemeAwarePage, show_themed_dialog
from ui.design import activity_card, action_button, eyebrow, panel


@ft.control
class HomePage(ThemeAwarePage, ft.Column):
    pass


def build_home(navigate, data=None):
    cards = [
        activity_card("Set up your letter scheme",
            "Assign sticker letters, choose your buffers, and set cycle-break preferences.",
            ft.Icons.GRID_VIEW, "Open letter schemes", lambda e: navigate("Letter Schemes"), "01 / Foundation"),
        activity_card("Build your letter pairs",
            "Create your mnemonic dictionary, add aliases, and rate the pairs you want to improve.",
            ft.Icons.TABLE_CHART, "Open letter pairs", lambda e: navigate("Letter Pairs"), "02 / Association"),
        activity_card("Practice",
            "Train recall with Progressive Memo or time a full attempt with Blind Timer.",
            ft.Icons.FITNESS_CENTER, "Choose a practice activity", lambda e: navigate("Practice"), "03 / Repetition"),
        activity_card("Analyze a scramble",
            "Generate memo with your scheme and explore temporary cycle-break choices.",
            ft.Icons.SHUFFLE, "Open scramble memo", lambda e: navigate("Scramble Memo"), "04 / Understanding"),
        activity_card("Method Library",
            "Study 3-style cases, edit your algorithms, or follow a scramble walkthrough.",
            ft.Icons.SCHOOL_OUTLINED, "Open Method Library", lambda e: navigate("Method Library"), "05 / Methods"),
    ]
    for card in cards: card.col = {"xs":12,"md":6,"lg":4}
    return HomePage([
        ft.ResponsiveRow([ft.Column([
            eyebrow("3×3 blindfolded / training workspace"),
            ft.Text("Build your memo.\nTrain your recall.", size=30,
                    weight=ft.FontWeight.W_600, style=ft.TextStyle(height=1.1), color=ft.Colors.ON_SURFACE),
            ft.Text(
                "Set up your letters, build memorable pairs, and connect your memo to real solves.",
                size=13, color=ft.Colors.ON_SURFACE_VARIANT, width=640,
            ),
        ], spacing=8, col={"xs":12,"lg":8}),
            ft.Column([
                ft.Text("Jump back in", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Row([
                    action_button("Open Timer", primary=True, icon=ft.Icons.TIMER,
                                  on_click=lambda e: navigate("Timer")),
                    action_button("Method Library", icon=ft.Icons.SCHOOL_OUTLINED,
                                  on_click=lambda e: navigate("Method Library")),
                ], spacing=8, wrap=True),
            ], spacing=6, col={"xs":12,"lg":4}),
        ], spacing=16, run_spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ft.Row([eyebrow("Your training workflow"),
                ft.Text("Start with your scheme, or jump straight into a session.",
                        size=12, color=ft.Colors.ON_SURFACE_VARIANT)], wrap=True, spacing=16),
        ft.ResponsiveRow(cards, spacing=12, run_spacing=12),
        panel(ft.Row([
            ft.Icon(ft.Icons.SAVE_OUTLINED, size=19, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text("Your workspace stays in this browser. Export a backup in Settings to keep a copy or move devices.",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
            ft.TextButton("Settings", on_click=lambda e: navigate("Settings")),
        ], spacing=10), padding=12),
    ], data=data, expand=True, spacing=14, scroll=ft.ScrollMode.AUTO)
