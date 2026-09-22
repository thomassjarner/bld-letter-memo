"""
Renders the 6 face-groups of a category (corners or edges) as visually
separated cards, each containing 4 sticker cells in the exact requested
order. Buffer stickers render as locked/greyed chips; everything else is
an editable single-letter field that autosaves on change.
"""

import flet as ft

from core.cube_definitions import face_groups
from core.pairs import find_duplicate_letters
from data.models import CategoryScheme

BUFFER_MARKER = "BUFFER"

FACE_NAMES = {
    "U": "Up",
    "L": "Left",
    "F": "Front",
    "R": "Right",
    "B": "Back",
    "D": "Down",
}


def build_sticker_grid(
    category: str,
    category_scheme: CategoryScheme,
    on_letter_change,
) -> ft.Control:
    """
    on_letter_change(sticker: str, new_value: str) -> None
    """
    duplicates = find_duplicate_letters(category_scheme, category)
    duplicated_stickers = {s for stickers in duplicates.values() for s in stickers}

    face_cards = []
    for face, stickers in face_groups(category):
        cells = []
        for sticker in stickers:
            value = category_scheme.stickers.get(sticker, "")
            is_buffer = value == BUFFER_MARKER

            if is_buffer:
                cell = ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(sticker, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "BUFFER ★" if sticker == category_scheme.buffer_sticker else "BUFFER PIECE",
                                size=12,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        spacing=2,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    width=72,
                    height=64,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    border_radius=8,
                    alignment=ft.alignment.center,
                )
            else:
                field = ft.TextField(
                    value=value,
                    label=sticker,
                    width=72,
                    max_length=1,
                    text_align=ft.TextAlign.CENTER,
                    border_color=ft.Colors.RED if sticker in duplicated_stickers else None,
                    on_change=lambda e, s=sticker: on_letter_change(s, e.control.value),
                )
                cell = field
            cells.append(cell)

        face_cards.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(f"{face} — {FACE_NAMES[face]}", weight=ft.FontWeight.BOLD, size=13),
                        ft.Row(cells, spacing=8, wrap=True),
                    ],
                    spacing=6,
                ),
                padding=12,
                border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=10,
            )
        )

    warning = None
    if duplicates:
        details = "; ".join(f"{letter}: {', '.join(stickers)}" for letter, stickers in duplicates.items())
        warning = ft.Container(
            content=ft.Text(f"⚠ Duplicate letters assigned: {details}", color=ft.Colors.RED, size=12),
            padding=ft.Padding.only(bottom=8),
        )

    children = [warning] if warning else []
    children.append(ft.Row(face_cards[:3], spacing=12, wrap=True))
    children.append(ft.Row(face_cards[3:], spacing=12, wrap=True))

    return ft.Column(children, spacing=12)
