import flet as ft
from core.cube_definitions import CATEGORY_STICKER_ORDER


def build_buffer_picker(category: str, current_buffer_sticker: str | None, on_change) -> ft.Control:
    """Pick the exact tracing buffer sticker, not merely its physical piece."""
    stickers = CATEGORY_STICKER_ORDER[category]
    return ft.Dropdown(
        label=f"{category.capitalize()} buffer sticker",
        hint_text="Choose exact sticker",
        width=230,
        value=current_buffer_sticker,
        options=[ft.dropdown.Option(s) for s in stickers],
        on_change=lambda e: on_change(e.control.value),
    )
