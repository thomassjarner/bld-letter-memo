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
    content_area = None
    menu_button = None
    current_index = 0

    def refresh_menu_items():
        nonlocal menu_button
        if menu_button is None:
            return
        menu_button.items = [
            ft.PopupMenuItem(
                content=label,
                icon=icon,
                checked=(idx == current_index),
                on_click=lambda e, i=idx: navigate_to(i),
                height=42,
            )
            for idx, (label, icon) in enumerate(DESTINATIONS)
        ]
        if menu_button.page is not None:
            menu_button.update()

    def navigate_to(index: int):
        nonlocal practice_page, pages, content_area, current_index
        if pages is None or content_area is None:
            return
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
        refresh_menu_items()
        if content_area.page is not None:
            content_area.update()
        else:
            page.update()

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
    content_area = ft.Container(
        content=pages[0],
        expand=True,
        padding=ft.Padding.only(left=12, top=10, right=12, bottom=66),
    )

    save_status = ft.Text("Saved", size=10, color=ft.Colors.ON_SURFACE_VARIANT)

    def on_save_status(status: str):
        save_status.value = status
        if save_status.page is not None:
            save_status.update()

    state.on_save_status(on_save_status)

    menu_button = ft.PopupMenuButton(
        content=ft.Container(
            content=ft.Row(
                [ft.Icon(ft.Icons.MENU, size=18), ft.Text("Menu", weight=ft.FontWeight.BOLD, size=13)],
                spacing=6,
                tight=True,
            ),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=18,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        ),
        menu_position=ft.PopupMenuPosition.OVER,
        menu_padding=4,
        tooltip="Open navigation menu",
    )
    refresh_menu_items()

    state.on_change(lambda: pairs_page.refresh() if content_area.content is pairs_page else None)

    def on_page_keyboard(e):
        if content_area is not None and content_area.content is schemes_page:
            schemes_page.handle_keyboard_event(e)

    page.on_keyboard_event = on_page_keyboard

    floating_nav = ft.Container(
        content=ft.Row([menu_button, save_status], spacing=8, tight=True),
        left=12,
        bottom=12,
        padding=0,
    )

    page.add(
        ft.Stack(
            controls=[content_area, floating_nav],
            expand=True,
            fit=ft.StackFit.EXPAND,
        )
    )


def run():
    ft.run(main)


if __name__ == "__main__":
    run()
