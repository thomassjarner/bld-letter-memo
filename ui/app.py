import flet as ft

from data.json_repository import JsonAppDataRepository
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


def main(page: ft.Page):
    page.title = "BLD Letter Memo"
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)
    page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.TEAL_400)
    page.padding = 0

    repository = JsonAppDataRepository()
    state = AppState(repository)
    page.theme_mode = ft.ThemeMode.DARK if state.data.dark_mode else ft.ThemeMode.LIGHT

    schemes_page = LetterSchemesPage(state)
    pairs_page = LetterPairsPage(state)
    scramble_page = ScrambleMemoPage(state)
    nav_rail = None
    practice_page = None
    pages = None
    content_area = None

    def navigate_to(index: int):
        nonlocal nav_rail, practice_page, pages, content_area
        if pages is None or content_area is None:
            return
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
        if nav_rail is not None and nav_rail.selected_index != index:
            nav_rail.selected_index = index
            if nav_rail.page is not None:
                nav_rail.update()
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

    practice_page = PracticePage(page, state, open_scramble_from_practice)
    def apply_dark_mode(enabled: bool):
        page.theme_mode = ft.ThemeMode.DARK if enabled else ft.ThemeMode.LIGHT
        page.update()

    settings_page = SettingsPage(page, state, apply_dark_mode)

    pages = [schemes_page, pairs_page, scramble_page, practice_page, settings_page]
    content_area = ft.Container(content=pages[0], expand=True, padding=16)

    def on_nav_change(e):
        navigate_to(e.control.selected_index)

    save_status = ft.Text("Saved", size=11, color=ft.Colors.ON_SURFACE_VARIANT)

    def on_save_status(status: str):
        save_status.value = status
        if save_status.page is not None:
            save_status.update()

    state.on_save_status(on_save_status)

    nav_rail = ft.NavigationRail(
        expand=True,
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=180,
        destinations=[
            ft.NavigationRailDestination(icon=icon, label=label) for label, icon in DESTINATIONS
        ],
        on_change=on_nav_change,
    )

    # Letter Schemes changes (buffer/letters) affect which pairs are
    # active, so refresh the Letter Pairs page whenever underlying data
    # changes and it happens to be visible.
    state.on_change(lambda: pairs_page.refresh() if content_area.content is pairs_page else None)

    sidebar = ft.Container(
        width=220,
        padding=ft.Padding.only(top=8, bottom=4),
        content=ft.Column(
            [nav_rail, ft.Container(save_status, padding=8)],
            expand=True,
            spacing=0,
        ),
    )

    page.add(
        ft.Row(
            [
                sidebar,
                ft.VerticalDivider(width=1),
                content_area,
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    )


def run():
    ft.run(main)


if __name__ == "__main__":
    run()
