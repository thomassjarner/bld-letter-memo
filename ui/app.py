import flet as ft

from data.cloud_client import BrowserCloud
from data.cloud_sync import CloudSync
from data.cloud_endpoint import SYNC_URL
from data.shared_preferences_repository import SharedPreferencesAppDataRepository
from ui.design import build_theme, icon_action
from ui.feature_icons import feature_icon
from ui.navigation_motion import route_switcher, set_reduced_motion
from ui.theme_colors import apply_palette
from ui.pages.home_page import build_home
from ui.pages.case_library_page import CaseLibraryPage
from ui.pages.letter_pairs_page import LetterPairsPage
from ui.pages.letter_schemes_page import LetterSchemesPage
from ui.pages.practice_page import PracticePage
from ui.pages.practice_hub_page import PracticeHubPage
from ui.pages.scramble_memo_page import ScrambleMemoPage
from ui.pages.settings_page import SettingsPage
from ui.state import AppState

DESTINATIONS = [
    ("Home", "home"),
    ("Letter Schemes", "schemes"),
    ("Letter Pairs", "pairs"),
    ("Scramble Memo", "memo"),
    ("Method Library", "library"),
    ("Practice", "practice"),
    ("Timer", "timer"),
    ("Settings", "settings"),
]
HOME_INDEX, SCHEMES_INDEX, PAIRS_INDEX, SCRAMBLE_INDEX, METHOD_INDEX, PRACTICE_INDEX, TIMER_INDEX, SETTINGS_INDEX = range(8)


async def main(page: ft.Page):
    page.title = "BLD Letter Memo · 2.56.0"
    page.theme = build_theme()
    page.dark_theme = build_theme(dark=True)
    page.padding = 0
    page.bgcolor = ft.Colors.SURFACE_CONTAINER_LOW

    repository = await SharedPreferencesAppDataRepository.create(page)
    state = AppState(repository)
    page.theme = build_theme(light_theme=state.data.light_theme)
    page.theme_mode = ft.ThemeMode.DARK if state.data.dark_mode else ft.ThemeMode.LIGHT
    current_index = HOME_INDEX
    popout_open = False

    schemes_page = LetterSchemesPage(data=state)
    pairs_page = LetterPairsPage(data=state)
    scramble_page = ScrambleMemoPage(data=state)
    settings_page = SettingsPage(data=state)
    method_page = CaseLibraryPage(data=state)

    save_status = [ft.Text("Saved", size=11, color=ft.Colors.ON_SURFACE_VARIANT) for _ in range(3)]

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

    def open_corner_walkthrough_from_timer(scramble):
        method_page.open_corner_walkthrough(scramble, state.data.active_scheme)
        navigate_to(METHOD_INDEX)

    # Preserve 2.20.2's separate control instances and asynchronous focus.
    timer_page = PracticePage(data=state)
    timer_page.open_memo_callback = open_scramble_from_practice
    timer_page.open_corner_walkthrough_callback = open_corner_walkthrough_from_timer
    timer_page.open_practice_callback = lambda: navigate_to(PRACTICE_INDEX)
    timer_page.show_timer(update=False)
    practice_page = PracticeHubPage(data=state)
    practice_page.open_memo_callback = open_scramble_from_practice
    practice_page.open_timer_callback = lambda: navigate_to(TIMER_INDEX)
    practice_page.open_scheme_callback = lambda: navigate_to(SCHEMES_INDEX)
    scramble_page.open_scheme_callback = lambda: navigate_to(SCHEMES_INDEX)
    practice_page.show_menu(update=False)

    def open_home_destination(name):
        if name == "Method Library":
            method_page._set_mode("overview")
            navigate_to(METHOD_INDEX)
        elif name == "Scramble walkthrough":
            method_page._set_mode("walkthrough")
            navigate_to(METHOD_INDEX)
        elif name == "Algorithm Playground":
            method_page._set_mode("explorer")
            navigate_to(METHOD_INDEX)
        elif name == "Progressive Memo":
            practice_page.open_progressive()
            navigate_to(PRACTICE_INDEX)
        elif name == "3-style corner trainer":
            method_page._set_mode("trainer")
            navigate_to(METHOD_INDEX)
        else:
            navigate_to(next(i for i, (label, _) in enumerate(DESTINATIONS) if label == name))

    practice_page.open_trainer_callback = lambda: open_home_destination("3-style corner trainer")
    home_page = build_home(open_home_destination, data=state)
    pages = [home_page, schemes_page, pairs_page, scramble_page, method_page, practice_page, timer_page, settings_page]
    for i, view in enumerate(pages):
        view.key = f"workspace_{i}"
    content_area = route_switcher(home_page, left=0, right=0, top=64, bottom=0)

    def apply_dark_mode(enabled):
        page.theme = build_theme(light_theme=state.data.light_theme)
        page.theme_mode = ft.ThemeMode.DARK if enabled else ft.ThemeMode.LIGHT
        settings_page.dark_mode_switch.value = enabled
        settings_page.refresh_appearance()
        # Memo spans use computed cycle colors rather than semantic color tokens.
        scramble_page.refresh(update=False)
        practice_page.refresh(update=False)
        method_page.refresh(update=False)
        rebuild_navigation(update=False)
        page.update()
    settings_page.theme_callback = apply_dark_mode

    def apply_light_theme():
        page.theme = build_theme(light_theme=state.data.light_theme)
        rebuild_navigation(update=False)
        page.update()
    settings_page.light_theme_callback = apply_light_theme

    def toggle_theme(e):
        enabled = not state.data.dark_mode
        state.set_dark_mode(enabled)
        apply_dark_mode(enabled)

    def theme_button():
        return icon_action(ft.Icons.LIGHT_MODE_OUTLINED if state.data.dark_mode else ft.Icons.DARK_MODE_OUTLINED,
                           "Switch to light mode" if state.data.dark_mode else "Switch to dark mode", toggle_theme,
                           size=40)

    def brand(compact=False):
        return ft.Row([
            ft.Icon(ft.Icons.VIEW_IN_AR_OUTLINED, size=28, color=ft.Colors.PRIMARY, key="brand_mark"),
            *([] if compact else [ft.Column([
                ft.Text("BLD Letter Memo", size=16, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                ft.Text("Blindfold training · v2.56.0", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=1)]),
        ], spacing=9, tight=True)

    def nav_button(index, compact=False):
        label, icon = DESTINATIONS[index]
        selected = index == current_index
        color = ft.Colors.ON_PRIMARY_CONTAINER if selected else ft.Colors.ON_SURFACE_VARIANT
        content = ft.Row([
            feature_icon(icon, size=18, selected=selected),
            ft.Text(label, size=13, color=color, weight=ft.FontWeight.W_600,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        ], spacing=8, tight=True)
        return ft.TextButton(
            content=content, tooltip=label, height=40, width=156 if compact else None,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY_CONTAINER if selected else ft.Colors.TRANSPARENT,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=8 if compact else 9, vertical=8),
                alignment=ft.Alignment.CENTER_LEFT,
            ), on_click=lambda e, i=index: navigate_to(i),
        )

    def restore_training_focus(e=None):
        # Closing a menu must return Space/typing to the active training tool.
        if current_index == TIMER_INDEX:
            if not timer_page.running:
                timer_page._reset_hold_state()
                timer_page._safe_update()
            timer_page.set_active(True)
        elif current_index == PRACTICE_INDEX:
            practice_page.set_active(True)

    top_nav = ft.Container(left=0, right=0, top=0, height=60,
        padding=ft.Padding.symmetric(horizontal=16, vertical=8), bgcolor=ft.Colors.SURFACE,
        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)))
    sidebar_nav = ft.Container(left=0, top=0, bottom=0, width=172, padding=8,
        bgcolor=ft.Colors.SURFACE, border=ft.Border(right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)))
    popout_panel = ft.Container(left=12, bottom=64, width=240, padding=8,
        bgcolor=ft.Colors.SURFACE, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=10, visible=False)

    def toggle_popout(e=None):
        nonlocal popout_open
        popout_open = not popout_open
        popout_panel.visible = popout_open
        if popout_panel.page is not None: popout_panel.update()
        if not popout_open: restore_training_focus()

    popout_button = ft.Container(
        ft.FilledButton("Menu", icon=ft.Icons.MENU, on_click=toggle_popout),
        left=12, bottom=12,
    )

    previous_viewport = previous_palette = None

    def rebuild_navigation(update=True):
        nonlocal previous_viewport, previous_palette
        page.bgcolor = build_theme(state.data.dark_mode, state.data.light_theme).color_scheme.surface_container_low
        width = page.width or 1200
        narrow = width < 1320
        compact = width < 1100
        # A full page menu makes every destination reachable on small screens.
        style = state.data.navigation_style
        if style == "compact_sidebar" and width < 700:
            style = "top_tabs"
        top_nav.visible = style == "top_tabs"
        sidebar_nav.visible = style == "compact_sidebar"
        popout_button.visible = style == "popout"
        popout_panel.visible = style == "popout" and popout_open
        nav_row = ft.Row([nav_button(i) for i in range(len(DESTINATIONS))],
                         spacing=2, scroll=ft.ScrollMode.AUTO, expand=not narrow)
        page_menu = ft.PopupMenuButton(icon=ft.Icons.MENU, tooltip="Open navigation", icon_size=20,
            width=40, height=40, bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST, icon_color=ft.Colors.PRIMARY,
            menu_position=ft.PopupMenuPosition.UNDER, on_cancel=restore_training_focus, items=[
                ft.PopupMenuItem(content=ft.Row([
                    feature_icon(icon, size=18),
                    ft.Text(label, size=13, color=ft.Colors.ON_SURFACE, expand=True),
                    ft.Icon(ft.Icons.CHECK, size=17, color=ft.Colors.PRIMARY, visible=i == current_index),
                ], spacing=10, width=210), height=44,
                    on_click=lambda e, index=i: navigate_to(index), data=label)
                for i, (label, icon) in enumerate(DESTINATIONS)])
        save_status[0].visible = width >= 580
        tools = ft.Row([save_status[0], theme_button()], spacing=4, tight=True)
        top_nav.height = 98 if narrow and not compact else 60
        top_nav.content = ft.Row([
            brand(compact=width < 700),
            ft.Text(DESTINATIONS[current_index][0], size=14, weight=ft.FontWeight.W_600,
                    color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                    expand=True, key="current_destination"),
            page_menu, tools,
        ], spacing=10) if compact else ft.Column([
            ft.Row([brand(), tools], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), nav_row,
        ], spacing=2) if narrow else ft.Row([brand(), nav_row, tools], spacing=18)
        sidebar_nav.content = ft.Column([
            ft.Row([brand(compact=True), ft.Text("BLD Letter Memo", size=13, weight=ft.FontWeight.W_600,
                    color=ft.Colors.ON_SURFACE, expand=True)], spacing=8, height=44),
            ft.Divider(height=8),
            ft.Column([nav_button(i, compact=True) for i in range(SETTINGS_INDEX)],
                      spacing=4, scroll=ft.ScrollMode.AUTO, expand=True),
            nav_button(SETTINGS_INDEX, compact=True),
            ft.Row([save_status[1], theme_button()], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ], spacing=6)
        popout_panel.content = ft.Column([
            *[nav_button(i) for i in range(len(DESTINATIONS))], ft.Divider(height=8),
            ft.Row([save_status[2], theme_button()], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ], spacing=3, tight=True, scroll=ft.ScrollMode.AUTO,
           horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        popout_panel.height = min(450, max(160, (page.height or 800) - 88))
        inset = 0 if width < 320 else 12 if width < 700 else 20
        content_area.left = (172 if style == "compact_sidebar" else 0) + inset
        content_area.right = inset
        content_area.top = (top_nav.height if style == "top_tabs" else 0) + 12
        content_area.bottom = 64 if style == "popout" else 12
        viewport = (max(1,width - content_area.left - content_area.right),
                    max(1,(page.height or 800) - content_area.top - content_area.bottom))
        # A tab click doesn't resize every hidden workspace or repaint every
        # offscreen sticker. Only a geometry/palette change needs that pass.
        for view in (home_page, timer_page, pairs_page, schemes_page, practice_page, method_page):
            if viewport != previous_viewport or view is pages[current_index]:
                view.set_viewport(*viewport)
        previous_viewport = viewport
        # AnimatedSwitcher lays out its child loosely; even short pages need the
        # full viewport so headers stay aligned with long, scrollable pages.
        for view in (settings_page, scramble_page):
            view.width, view.height = viewport
        palette = (state.data.dark_mode, state.data.light_theme)
        for view in (pages if palette != previous_palette else (pages[current_index],)):
            apply_palette(view, state.data.dark_mode, state.data.light_theme)
        previous_palette = palette
        for chrome in (top_nav, sidebar_nav, popout_panel, popout_button):
            apply_palette(chrome, state.data.dark_mode, state.data.light_theme)
        if update:
            page.update()

    def apply_navigation_style(style):
        nonlocal popout_open
        popout_open = False
        rebuild_navigation()
    settings_page.navigation_callback = apply_navigation_style

    cloud = None

    def navigate_to(index, *, refresh=True):
        nonlocal current_index, popout_open
        current_index = index
        target = pages[index]
        if refresh and hasattr(target, "refresh"):
            target.refresh(update=False)
        content_area.content = target
        popout_open = False
        rebuild_navigation(update=False)
        page.update()
        timer_page.set_active(index == TIMER_INDEX)
        practice_page.set_active(index == PRACTICE_INDEX)
        method_page.set_active(index == METHOD_INDEX)
        if cloud and cloud.ready and index in (HOME_INDEX, SETTINGS_INDEX) and not cloud.differences:
            cloud.request()

    def on_resize(e):
        # Reflow the existing timer body for every size change; its keyboard
        # listener and active solve stay intact even within one nav breakpoint.
        rebuild_navigation()

    state.on_change(lambda: pairs_page.refresh() if content_area.content is pairs_page else None)
    page.on_keyboard_event = lambda e: schemes_page.handle_keyboard_event(e) if content_area.content is schemes_page else None
    page.on_resize = on_resize
    if SYNC_URL:
        def app_visibility(e):
            if cloud and cloud.ready and e.state==ft.AppLifecycleState.RESUME:
                cloud.request()
        page.on_app_lifecycle_state_change=app_visibility
    page.add(ft.Stack([content_area, top_nav, sidebar_nav, popout_panel, popout_button],
                      expand=True, fit=ft.StackFit.EXPAND))
    rebuild_navigation()

    if isinstance(page, ft.Page):
        async def read_motion_preference():
            try:
                flags = await ft.SemanticsService().get_accessibility_features()
            except (RuntimeError, ValueError, TimeoutError, ft.FletException):
                return  # Older clients use Flutter's native animation behavior.
            if flags.disable_animations:
                for host in (content_area, practice_page.switcher):
                    set_reduced_motion(host, True)
                page.update()
        page.run_task(read_motion_preference)

    async def start_cloud():
        nonlocal cloud
        try:
            client = await BrowserCloud.open()
            if not client:
                return
            cloud = CloudSync(state, repository, client, page.run_task,
                              safe=lambda: current_index in (HOME_INDEX, SETTINGS_INDEX))
            settings_page.account.cloud = cloud
            cloud.changed = lambda: settings_page.account.render(update=current_index==SETTINGS_INDEX)
            def refresh_workspace():
                settings_page.dark_mode_switch.value = state.data.dark_mode
                settings_page.navigation_style_dropdown.value = state.data.navigation_style
                settings_page.simultaneous_moves_switch.value = state.data.simultaneous_moves
                settings_page.rating_mode_dropdown.value = state.data.letter_pair_rating_mode
                settings_page.rating_levels_dropdown.value = str(state.data.rating_color_levels)
                settings_page._rebuild_rating_palette()
                settings_page.refresh_appearance()
                page.theme_mode = ft.ThemeMode.DARK if state.data.dark_mode else ft.ThemeMode.LIGHT
                page.theme = build_theme(light_theme=state.data.light_theme)
                rebuild_navigation()
            cloud.applied = refresh_workspace
            state.on_save_status(cloud.local_saved)
            if client.returning: navigate_to(SETTINGS_INDEX)
            await cloud.initialize()
        except Exception:
            settings_page.account.unavailable = "Could not open cloud sync. Your local workspace is still available."
            settings_page.account.cloud = None
            settings_page.account.render(update=current_index==SETTINGS_INDEX)
    if SYNC_URL: page.run_task(start_cloud)


def run():
    ft.run(main)


if __name__ == "__main__":
    run()
