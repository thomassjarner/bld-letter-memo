import flet as ft

from data.shared_preferences_repository import SharedPreferencesAppDataRepository
from ui.design import build_theme
from ui.theme_colors import apply_palette
from ui.pages.home_page import build_home
from ui.pages.letter_pairs_page import LetterPairsPage
from ui.pages.letter_schemes_page import LetterSchemesPage
from ui.pages.practice_page import PracticePage
from ui.pages.practice_hub_page import PracticeHubPage
from ui.pages.scramble_memo_page import ScrambleMemoPage
from ui.pages.settings_page import SettingsPage
from ui.state import AppState

DESTINATIONS = [
    ("Home", ft.Icons.HOME_OUTLINED),
    ("Letter Schemes", ft.Icons.GRID_VIEW),
    ("Letter Pairs", ft.Icons.TABLE_CHART),
    ("Scramble Memo", ft.Icons.SHUFFLE),
    ("Practice", ft.Icons.FITNESS_CENTER),
    ("Timer", ft.Icons.TIMER),
    ("Settings", ft.Icons.SETTINGS),
]
HOME_INDEX, SCHEMES_INDEX, PAIRS_INDEX, SCRAMBLE_INDEX, PRACTICE_INDEX, TIMER_INDEX, SETTINGS_INDEX = range(7)


async def main(page: ft.Page):
    page.title = "BLD Letter Memo · 2.23.0"
    page.theme = build_theme()
    page.dark_theme = build_theme(dark=True)
    page.padding = 0
    page.bgcolor = ft.Colors.SURFACE_CONTAINER_LOW

    repository = await SharedPreferencesAppDataRepository.create(page)
    state = AppState(repository)
    page.theme_mode = ft.ThemeMode.DARK if state.data.dark_mode else ft.ThemeMode.LIGHT
    current_index = HOME_INDEX
    popout_open = False

    schemes_page = LetterSchemesPage(data=state)
    pairs_page = LetterPairsPage(data=state)
    scramble_page = ScrambleMemoPage(data=state)
    settings_page = SettingsPage(data=state)

    content_area = ft.Container(expand=True, left=0, right=0, top=64, bottom=0,
                                padding=16)
    save_status = [ft.Text("Saved", size=10, color=ft.Colors.ON_SURFACE_VARIANT) for _ in range(3)]

    def on_save_status(status):
        for control in save_status:
            control.value = status
            if control.page is not None:
                control.update()
    state.on_save_status(on_save_status)

    def open_scramble_from_practice(scramble):
        scramble_page.scramble.value = scramble
        scramble_page.error.value = ""
        scramble_page.last_result = None
        scramble_page.details.value = ""
        scramble_page._render_result()
        navigate_to(SCRAMBLE_INDEX)
        if scramble_page.page is not None:
            scramble_page.update()

    # Preserve 2.20.2's separate control instances and asynchronous focus.
    timer_page = PracticePage(data=state)
    timer_page.open_memo_callback = open_scramble_from_practice
    timer_page.open_practice_callback = lambda: navigate_to(PRACTICE_INDEX)
    timer_page.show_timer(update=False)
    practice_page = PracticeHubPage(data=state)
    practice_page.open_memo_callback = open_scramble_from_practice
    practice_page.open_timer_callback = lambda: navigate_to(TIMER_INDEX)
    practice_page.open_scheme_callback = lambda: navigate_to(SCHEMES_INDEX)
    practice_page.show_menu(update=False)
    home_page = build_home(lambda name: navigate_to(next(i for i, (label, _) in enumerate(DESTINATIONS) if label == name)), data=state)
    pages = [home_page, schemes_page, pairs_page, scramble_page, practice_page, timer_page, settings_page]
    content_area.content = home_page

    def apply_dark_mode(enabled):
        page.theme_mode = ft.ThemeMode.DARK if enabled else ft.ThemeMode.LIGHT
        settings_page.dark_mode_switch.value = enabled
        # Memo spans use computed cycle colors rather than semantic color tokens.
        scramble_page.refresh(update=False)
        practice_page.refresh(update=False)
        rebuild_navigation(update=False)
        page.update()
    settings_page.theme_callback = apply_dark_mode

    def toggle_theme(e):
        enabled = not state.data.dark_mode
        state.set_dark_mode(enabled)
        apply_dark_mode(enabled)

    def theme_button():
        return ft.IconButton(ft.Icons.LIGHT_MODE_OUTLINED if state.data.dark_mode else ft.Icons.DARK_MODE_OUTLINED,
                             tooltip="Switch to light mode" if state.data.dark_mode else "Switch to dark mode",
                             icon_size=19, on_click=toggle_theme)

    def brand(compact=False):
        return ft.Row([
            ft.Icon(ft.Icons.VIEW_IN_AR_OUTLINED, size=28, color=ft.Colors.PRIMARY, key="brand_mark"),
            *([] if compact else [ft.Column([
                ft.Text("BLD Letter Memo", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Text("TRAINING WORKSPACE · v2.23.0", size=8, color=ft.Colors.ON_SURFACE_VARIANT,
                        style=ft.TextStyle(letter_spacing=1.2)),
            ], spacing=1)]),
        ], spacing=9, tight=True)

    def nav_button(index, compact=False):
        label, icon = DESTINATIONS[index]
        selected = index == current_index
        color = ft.Colors.ON_PRIMARY_CONTAINER if selected else ft.Colors.ON_SURFACE_VARIANT
        content = ft.Column([
            ft.Icon(icon, size=19, color=color),
            ft.Text(label.replace(" ", "\n"), size=10, text_align=ft.TextAlign.CENTER, color=color),
        ], spacing=3, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True) if compact else ft.Row([
            ft.Icon(icon, size=17, color=color),
            ft.Text(label, size=12, color=color, weight=ft.FontWeight.W_600),
        ], spacing=6, tight=True)
        return ft.TextButton(
            content=content, tooltip=label,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY_CONTAINER if selected else ft.Colors.TRANSPARENT,
                shape=ft.RoundedRectangleBorder(radius=7),
                padding=ft.Padding.symmetric(horizontal=10, vertical=9),
            ), on_click=lambda e, i=index: navigate_to(i),
        )

    top_nav = ft.Container(left=0, right=0, top=0, height=60,
        padding=ft.Padding.symmetric(horizontal=16, vertical=8), bgcolor=ft.Colors.SURFACE,
        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)))
    sidebar_nav = ft.Container(left=0, top=0, bottom=0, width=106, padding=8,
        bgcolor=ft.Colors.SURFACE, border=ft.Border(right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)))
    popout_panel = ft.Container(left=12, bottom=64, width=212, padding=8,
        bgcolor=ft.Colors.SURFACE, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=10, visible=False)

    def toggle_popout(e=None):
        nonlocal popout_open
        popout_open = not popout_open
        popout_panel.visible = popout_open
        popout_panel.update()

    popout_button = ft.Container(
        ft.FilledButton("Menu", icon=ft.Icons.MENU, on_click=toggle_popout),
        left=12, bottom=12,
    )

    def rebuild_navigation(update=True):
        width = page.width or 1200
        narrow = width < 1120
        # Small screens get a scrollable top nav; the saved preference is unchanged.
        style = state.data.navigation_style
        if style == "compact_sidebar" and width < 700:
            style = "top_tabs"
        top_nav.visible = style == "top_tabs"
        sidebar_nav.visible = style == "compact_sidebar"
        popout_button.visible = style == "popout"
        popout_panel.visible = style == "popout" and popout_open
        nav_row = ft.Row([nav_button(i) for i in range(len(DESTINATIONS))],
                         spacing=2, scroll=ft.ScrollMode.AUTO, expand=not narrow)
        tools = ft.Row([save_status[0], theme_button()], spacing=4, tight=True)
        top_nav.height = 98 if narrow else 60
        top_nav.content = ft.Column([
            ft.Row([brand(), tools], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), nav_row,
        ], spacing=2) if narrow else ft.Row([brand(), nav_row, tools], spacing=18)
        sidebar_nav.content = ft.Column([
            brand(compact=True), ft.Divider(height=10),
            ft.Column([nav_button(i, compact=True) for i in range(len(DESTINATIONS))],
                      spacing=3, scroll=ft.ScrollMode.AUTO, expand=True),
            theme_button(), save_status[1],
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)
        popout_panel.content = ft.Column([
            *[nav_button(i) for i in range(len(DESTINATIONS))], ft.Divider(height=8),
            ft.Row([save_status[2], theme_button()], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ], spacing=3, tight=True, scroll=ft.ScrollMode.AUTO)
        popout_panel.height = min(450, max(160, (page.height or 800) - 88))
        content_area.left = 106 if style == "compact_sidebar" else 0
        content_area.top = top_nav.height if style == "top_tabs" else 0
        content_area.padding = ft.Padding.only(left=12 if width < 700 else 20, top=16,
            right=12 if width < 700 else 20, bottom=64 if style == "popout" else 16)
        horizontal_padding = 24 if width < 700 else 40
        bottom_padding = 64 if style == "popout" else 16
        timer_page.set_viewport(width - content_area.left - horizontal_padding,
                                (page.height or 800) - content_area.top - 16 - bottom_padding)
        pairs_page.set_viewport(width - content_area.left - horizontal_padding,
                                (page.height or 800) - content_area.top - 16 - bottom_padding)
        practice_page.set_viewport(width - content_area.left - horizontal_padding,
                                   (page.height or 800) - content_area.top - 16 - bottom_padding)
        for view in pages:
            apply_palette(view, state.data.dark_mode)
        for chrome in (top_nav, sidebar_nav, popout_panel, popout_button):
            apply_palette(chrome, state.data.dark_mode)
        if update:
            page.update()

    def apply_navigation_style(style):
        nonlocal popout_open
        popout_open = False
        rebuild_navigation()
    settings_page.navigation_callback = apply_navigation_style

    def navigate_to(index):
        nonlocal current_index, popout_open
        current_index = index
        target = pages[index]
        if hasattr(target, "refresh"):
            target.refresh(update=False)
        content_area.content = target
        popout_open = False
        rebuild_navigation(update=False)
        page.update()
        timer_page.set_active(index == TIMER_INDEX)
        practice_page.set_active(index == PRACTICE_INDEX)

    def on_resize(e):
        # Reflow the existing timer body for every size change; its keyboard
        # listener and active solve stay intact even within one nav breakpoint.
        rebuild_navigation()

    state.on_change(lambda: pairs_page.refresh() if content_area.content is pairs_page else None)
    page.on_keyboard_event = lambda e: schemes_page.handle_keyboard_event(e) if content_area.content is schemes_page else None
    page.on_resize = on_resize
    page.add(ft.Stack([content_area, top_nav, sidebar_nav, popout_panel, popout_button],
                      expand=True, fit=ft.StackFit.EXPAND))
    rebuild_navigation()


def run():
    ft.run(main)


if __name__ == "__main__":
    run()
