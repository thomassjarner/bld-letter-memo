import flet as ft

from data.shared_preferences_repository import SharedPreferencesAppDataRepository
from ui.pages.letter_pairs_page import LetterPairsPage
from ui.pages.letter_schemes_page import LetterSchemesPage
from ui.pages.practice_page import PracticePage
from ui.pages.scramble_memo_page import ScrambleMemoPage
from ui.pages.settings_page import SettingsPage
from ui.state import AppState

DESTINATIONS = [
    ("Letter Schemes", ft.Icons.GRID_VIEW),
    ("Letter Pairs", ft.Icons.TABLE_CHART),
    ("Scramble Memo", ft.Icons.SHUFFLE),
    ("Practice", ft.Icons.FITNESS_CENTER),
    ("Settings", ft.Icons.SETTINGS),
]


async def main(page: ft.Page):
    page.title = "BLD Letter Memo"
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)
    page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.TEAL_400)
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    repository = await SharedPreferencesAppDataRepository.create(page)
    state = AppState(repository)
    page.theme_mode = ft.ThemeMode.DARK if state.data.dark_mode else ft.ThemeMode.LIGHT

    schemes_page = LetterSchemesPage(data=state)
    pairs_page = LetterPairsPage(data=state)
    scramble_page = ScrambleMemoPage(data=state)
    practice_page = None
    pages = None
    current_index = 0
    popout_open = False

    content_area = ft.Container(
        expand=True,
        padding=ft.Padding.only(left=14, top=62, right=14, bottom=14),
        left=0,
        right=0,
        top=0,
        bottom=0,
    )

    top_save_status = ft.Text("Saved", size=10, color=ft.Colors.ON_SURFACE_VARIANT)
    side_save_status = ft.Text("Saved", size=10, color=ft.Colors.ON_SURFACE_VARIANT)
    pop_save_status = ft.Text("Saved", size=10, color=ft.Colors.ON_SURFACE_VARIANT)

    def on_save_status(status: str):
        for control in (top_save_status, side_save_status, pop_save_status):
            control.value = status
            if control.page is not None:
                control.update()

    state.on_save_status(on_save_status)

    def open_scramble_from_practice(scramble: str):
        scramble_page.scramble.value = scramble
        scramble_page.error.value = ""
        scramble_page.last_result = None
        scramble_page.details.value = ""
        scramble_page._render_result()
        navigate_to(2)
        if scramble_page.page is not None:
            scramble_page.update()

    practice_page = PracticePage(data=state)
    practice_page.open_memo_callback = open_scramble_from_practice

    def apply_dark_mode(enabled: bool):
        page.theme_mode = ft.ThemeMode.DARK if enabled else ft.ThemeMode.LIGHT
        page.update()

    settings_page = SettingsPage(data=state)
    settings_page.theme_callback = apply_dark_mode

    pages = [schemes_page, pairs_page, scramble_page, practice_page, settings_page]
    content_area.content = pages[0]

    def make_nav_button(index: int, compact: bool = False):
        label, icon = DESTINATIONS[index]
        selected = index == current_index
        return ft.Container(
            content=ft.Row(
                [ft.Icon(icon, size=18), ft.Text(label, size=12, weight=ft.FontWeight.BOLD if selected else None)],
                spacing=5,
                tight=True,
            ) if not compact else ft.Column(
                [ft.Icon(icon, size=19), ft.Text(label.replace(" ", "\n"), size=10, text_align=ft.TextAlign.CENTER)],
                spacing=3,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
            padding=ft.Padding.symmetric(horizontal=9 if not compact else 6, vertical=7),
            border_radius=8,
            bgcolor=ft.Colors.SECONDARY_CONTAINER if selected else None,
            ink=True,
            on_click=lambda e, i=index: navigate_to(i),
        )

    top_nav = ft.Container(
        left=0,
        right=0,
        top=0,
        height=52,
        padding=ft.Padding.symmetric(horizontal=14, vertical=7),
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
    )
    sidebar_nav = ft.Container(
        left=0,
        top=0,
        bottom=0,
        width=108,
        padding=ft.Padding.symmetric(horizontal=6, vertical=8),
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border(right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
    )
    popout_panel = ft.Container(
        left=12,
        bottom=54,
        width=190,
        padding=7,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=10,
        visible=False,
    )
    popout_button = ft.Container(
        left=12,
        bottom=12,
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=18,
        ink=True,
    )

    def toggle_popout(e=None):
        nonlocal popout_open
        popout_open = not popout_open
        popout_panel.visible = popout_open
        if popout_panel.page is not None:
            popout_panel.update()

    popout_button.content = ft.Row(
        [ft.Icon(ft.Icons.MENU, size=18), ft.Text("Menu", size=12, weight=ft.FontWeight.BOLD), pop_save_status],
        spacing=6,
        tight=True,
    )
    popout_button.on_click = toggle_popout

    def rebuild_navigation(update: bool = True):
        nonlocal popout_open
        style = state.data.navigation_style

        top_nav.visible = style == "top_tabs"
        sidebar_nav.visible = style == "compact_sidebar"
        popout_button.visible = style == "popout"
        popout_panel.visible = style == "popout" and popout_open

        top_nav.content = ft.Row(
            [
                ft.Row([
                    ft.Text("BLD Letter Memo", size=15, weight=ft.FontWeight.BOLD),
                    top_save_status,
                ], spacing=8, tight=True),
                ft.Row([make_nav_button(i) for i in range(len(DESTINATIONS))], spacing=2, tight=True),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        sidebar_nav.content = ft.Column(
            [
                ft.Text("BLD", size=13, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Divider(height=8),
                *[make_nav_button(i, compact=True) for i in range(len(DESTINATIONS))],
                ft.Container(expand=True),
                side_save_status,
            ],
            spacing=3,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        popout_panel.content = ft.Column(
            [make_nav_button(i) for i in range(len(DESTINATIONS))],
            spacing=2,
            tight=True,
        )

        if style == "top_tabs":
            content_area.left = 0
            content_area.top = 52
            content_area.padding = ft.Padding.only(left=14, top=10, right=14, bottom=14)
        elif style == "compact_sidebar":
            content_area.left = 108
            content_area.top = 0
            content_area.padding = ft.Padding.all(14)
        else:
            content_area.left = 0
            content_area.top = 0
            content_area.padding = ft.Padding.only(left=14, top=14, right=14, bottom=58)

        if update:
            page.update()

    def apply_navigation_style(style: str):
        nonlocal popout_open
        popout_open = False
        rebuild_navigation(update=True)

    settings_page.navigation_callback = apply_navigation_style

    def navigate_to(index: int):
        nonlocal current_index, popout_open
        current_index = index
        practice_page.set_active(index == 3)
        target = pages[index]
        if target is pairs_page:
            pairs_page.refresh(update=False)
        elif target is schemes_page:
            schemes_page.refresh(update=False)
        elif target is scramble_page:
            scramble_page.refresh(update=False)
        elif target is practice_page:
            practice_page.refresh(update=False)
        content_area.content = target
        popout_open = False
        rebuild_navigation(update=False)
        page.update()

    state.on_change(lambda: pairs_page.refresh() if content_area.content is pairs_page else None)

    def on_page_keyboard(e):
        if content_area.content is schemes_page:
            schemes_page.handle_keyboard_event(e)

    page.on_keyboard_event = on_page_keyboard

    root = ft.Stack(
        controls=[content_area, top_nav, sidebar_nav, popout_panel, popout_button],
        expand=True,
        fit=ft.StackFit.EXPAND,
    )
    page.add(root)
    rebuild_navigation(update=True)


def run():
    ft.run(main)


if __name__ == "__main__":
    run()
