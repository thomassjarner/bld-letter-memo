"""A compact, grouped route chooser with no embedded training tools."""
import flet as ft

from ui.design import eyebrow, panel
from ui.feature_icons import feature_icon
from ui.theme_colors import ThemeAwarePage


# Categories describe the task; destinations keep their familiar names.
HOME_GROUPS = (
    ("setup", "Set up your memo", "Your letters and mnemonics.", (
        ("schemes", "Set up your letter scheme", "Assign letters, buffers and cycle-break preferences.", "Letter Schemes"),
        ("pairs", "Build your letter pairs", "Build and rate your mnemonic dictionary.", "Letter Pairs"),
    )),
    ("analyze", "Analyze a scramble", "Understand a scramble before you solve it.", (
        ("memo", "Scramble Memo", "Trace your targets and explore cycle-break choices.", "Scramble Memo"),
        ("walkthrough", "Scramble walkthrough", "Follow your corner algorithms on the interactive cube.", "Scramble walkthrough"),
    )),
    ("learn", "Learning material", "Understand and refine your method.", (
        ("library", "Method Library", "Study 3-style cases, save algorithms and find lessons.", "Method Library"),
        ("playground", "Algorithm Playground", "Try moves or commutators and inspect their effect.", "Algorithm Playground"),
    )),
    ("practice", "Practice", "Build recall and track your progress.", (
        ("timer", "Blind Timer", "Time your solves and review sessions and history.", "Timer"),
        ("progressive", "Progressive Memo", "Memo a real scramble, then test your typed recall.", "Progressive Memo"),
        ("trainer", "3-style corner trainer", "Recall your algorithms and review each case.", "3-style corner trainer"),
    )),
)


@ft.control
class HomePage(ThemeAwarePage, ft.Column):
    def set_viewport(self, width, height):
        self.width, self.height = width, height
        self.hero_title.size = 23 if width < 480 else 27
        # Preserve room for two title/description lines on narrow screens.
        for button in self.launch_buttons.values():
            button.height = 88 if width < 480 else 76


def build_home(navigate, data=None):
    buttons, groups = {}, []
    for key, title, description, features in HOME_GROUPS:
        rows = []
        for icon, name, detail, destination in features:
            button = ft.TextButton(
                content=ft.Row([
                    ft.Container(feature_icon(icon, size=24), width=40, height=40,
                                 alignment=ft.Alignment.CENTER, border_radius=10,
                                 bgcolor=ft.Colors.SURFACE_CONTAINER_LOW),
                    ft.Column([
                        ft.Text(name, size=14, weight=ft.FontWeight.W_600,
                                color=ft.Colors.ON_SURFACE, max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(detail, size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=3, expand=True, tight=True),
                    ft.Icon(ft.Icons.ARROW_FORWARD, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=12),
                height=76, key=f"home_open_{icon}", data=destination,
                tooltip=f"Open {name}: {detail}",
                style=ft.ButtonStyle(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    shape=ft.RoundedRectangleBorder(radius=9),
                    alignment=ft.Alignment.CENTER_LEFT,
                    bgcolor={ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT,
                             ft.ControlState.HOVERED: ft.Colors.SURFACE_CONTAINER_LOW,
                             ft.ControlState.FOCUSED: ft.Colors.PRIMARY_CONTAINER},
                ),
                on_click=lambda e, target=destination: navigate(target),
            )
            buttons[icon] = button
            rows.append(button)
        groups.append(panel(ft.Column([
            ft.Column([
                ft.Text(title, size=17, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                ft.Text(description, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=3),
            ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
            ft.Column(rows, spacing=2, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        ], spacing=10, tight=True), padding=14, col={"xs": 12, "md": 6}, key=f"home_group_{key}"))

    title = ft.Text("Build your memo.\nTrain your recall.", size=27,
                    weight=ft.FontWeight.W_600, style=ft.TextStyle(height=1.1), color=ft.Colors.ON_SURFACE)
    home = HomePage([
        ft.Column([
            eyebrow("3×3 blindfolded / training workspace"), title,
            ft.Text("Set up your letters, explore a scramble, or jump into a training session.",
                    size=13, color=ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=6),
        ft.ResponsiveRow(groups, spacing=12, run_spacing=12),
        ft.Row([
            ft.Icon(ft.Icons.SAVE_OUTLINED, size=17, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text("Your workspace saves in this browser. Export a backup in Settings to keep a copy.",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
            ft.TextButton("Settings", key="home_open_settings", on_click=lambda e: navigate("Settings")),
        ], spacing=8),
    ], data=data, expand=True, spacing=14, scroll=ft.ScrollMode.AUTO,
       horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    home.launch_buttons = buttons
    home.hero_title = title
    return home
