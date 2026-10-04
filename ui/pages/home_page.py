"""An introduction and route chooser, deliberately without embedded tools."""
import flet as ft
from ui.design import activity_card, eyebrow, panel


def build_home(navigate):
    return ft.Column([
        ft.Container(ft.Column([
            eyebrow("3×3 blindfolded / training workspace"),
            ft.Text("Build your memo.\nTrain your recall.", size=36,
                    weight=ft.FontWeight.W_600, style=ft.TextStyle(height=1.1)),
            ft.Text(
                "A focused workspace for blindfolded cubing. Set up your sticker letters, "
                "turn letter pairs into memorable words, and connect your memo to real solves.",
                size=14, color=ft.Colors.ON_SURFACE_VARIANT, width=670,
            ),
        ], spacing=12), padding=ft.Padding.only(top=8, bottom=12)),
        ft.Row([eyebrow("Your training workflow"),
                ft.Text("Start with your scheme, or jump straight into a session.",
                        size=12, color=ft.Colors.ON_SURFACE_VARIANT)], wrap=True, spacing=16),
        ft.ResponsiveRow([
            activity_card("Set up your letter scheme",
                "Assign letters to edge and corner stickers. Choose buffers, orientation, and cycle-break priorities.",
                ft.Icons.GRID_VIEW, "Open letter schemes", lambda e: navigate("Letter Schemes"), "01 / FOUNDATION"),
            activity_card("Build your letter pairs",
                "Create a personal mnemonic dictionary. Add words and aliases, rate your pairs, and find what needs work.",
                ft.Icons.TABLE_CHART, "Open letter pairs", lambda e: navigate("Letter Pairs"), "02 / ASSOCIATION"),
            activity_card("Practice",
                "Time full attempts with Blind Timer. Progressive Memo, Delayed Recall, and Letter Pair Drill are planned.",
                ft.Icons.FITNESS_CENTER, "Choose a practice activity", lambda e: navigate("Practice"), "03 / REPETITION"),
            activity_card("Analyze a scramble",
                "Trace a scramble using your scheme. Inspect memo targets and explore temporary cycle-break choices.",
                ft.Icons.SHUFFLE, "Open scramble memo", lambda e: navigate("Scramble Memo"), "04 / UNDERSTANDING"),
        ], spacing=12, run_spacing=12),
        panel(ft.Row([
            ft.Icon(ft.Icons.SAVE_OUTLINED, size=19, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text("Your workspace stays in this browser. Export a backup in Settings to keep a copy or move devices.",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
            ft.TextButton("Settings", on_click=lambda e: navigate("Settings")),
        ], spacing=10), padding=12),
    ], expand=True, spacing=14, scroll=ft.ScrollMode.AUTO)
