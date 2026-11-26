from core.messages import message
from ui.language import tr
import flet as ft
from core.cube_definitions import CATEGORY_STICKER_ORDER


def build_buffer_picker(category: str, current_buffer_sticker: str | None, on_change) -> ft.Control:
    """Pick the exact tracing buffer sticker, not merely its physical piece."""
    stickers = CATEGORY_STICKER_ORDER[category]
    return ft.Dropdown(
        label=tr('{0} buffer sticker', message(category.capitalize())),
        hint_text=tr('Choose exact sticker'),
        width=230,
        value=current_buffer_sticker,
        options=[ft.DropdownOption(s) for s in stickers],
        on_select=lambda e: on_change(e.control.value),
    color=ft.Colors.ON_SURFACE, label_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT), hint_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT))
