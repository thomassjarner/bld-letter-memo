"""A compact, grouped route chooser with no embedded training tools."""
from core.messages import message
from ui.language import present, tr
import flet as ft

from ui.design import eyebrow, panel
from ui.feature_icons import feature_icon
from ui.theme_colors import ThemeAwarePage


# Categories describe the task; destinations keep their familiar names.
HOME_GROUPS = (
    ("setup", message('Set up your memo'), message('Your letters and mnemonics.'), (
        ("schemes", message('Set up your letter scheme'), message('Assign letters, buffers and cycle-break preferences.'), message('Letter Schemes')),
        ("pairs", message('Build your letter pairs'), message('Build and rate your mnemonic dictionary.'), message('Letter Pairs')),
    )),
    ("analyze", message('Analyze a scramble'), message('Understand a scramble before you solve it.'), (
        ("memo", message('Scramble Memo'), message('Trace your targets and explore cycle-break choices.'), message('Scramble Memo')),
        ("walkthrough", message('Scramble walkthrough'), message('Follow your corner algorithms on the interactive cube.'), message('Scramble walkthrough')),
    )),
    ("learn", message('Learning material'), message('Understand and refine your method.'), (
        ("library", message('Method Library'), message('Study 3-style cases, save algorithms and find lessons.'), message('Method Library')),
        ("playground", message('Algorithm Playground'), message('Try moves or commutators and inspect their effect.'), message('Algorithm Playground')),
    )),
    ("practice", message('Practice'), message('Build recall and track your progress.'), (
        ("timer", message('Blind Timer'), message('Time your solves and review sessions and history.'), message('Timer')),
        ("progressive", message('Progressive Memo'), message('Memo a real scramble, then test your typed recall.'), message('Progressive Memo')),
        ("trainer", message('3-style corner trainer'), message('Recall your algorithms and review each case.'), message('3-style corner trainer')),
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
                        ft.Text(present(name), size=14, weight=ft.FontWeight.W_600,
                                color=ft.Colors.ON_SURFACE, max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(present(detail), size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=3, expand=True, tight=True),
                    ft.Icon(ft.Icons.ARROW_FORWARD, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=12),
                height=76, key=f"home_open_{icon}", data=destination,
                tooltip=tr('Open {0}: {1}', name, detail),
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
                ft.Text(present(title), size=17, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                ft.Text(present(description), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=3),
            ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
            ft.Column(rows, spacing=2, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        ], spacing=10, tight=True), padding=14, col={"xs": 12, "md": 6}, key=f"home_group_{key}"))

    title = ft.Text(tr('Build your memo.\nTrain your recall.'), size=27,
                    weight=ft.FontWeight.W_600, style=ft.TextStyle(height=1.1), color=ft.Colors.ON_SURFACE)
    home = HomePage([
        ft.Column([
            eyebrow(message('3×3 blindfolded / training workspace')), title,
            ft.Text(tr('Set up your letters, explore a scramble, or jump into a training session.'),
                    size=13, color=ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=6),
        ft.ResponsiveRow(groups, spacing=12, run_spacing=12),
        ft.Row([
            ft.Icon(ft.Icons.SAVE_OUTLINED, size=17, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text(tr('Your workspace saves in this browser. Export a backup in Settings to keep a copy.'),
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
            ft.TextButton(tr('Settings'), key="home_open_settings", on_click=lambda e: navigate(message('Settings'))),
        ], spacing=8),
    ], data=data, expand=True, spacing=14, scroll=ft.ScrollMode.AUTO,
       horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    home.launch_buttons = buttons
    home.hero_title = title
    return home
