"""Fixed square letter inputs shared by the cube net and face cards."""
import flet as ft

from core.cube_definitions import CATEGORY_PIECES, find_piece_for_sticker
from core.pairs import find_duplicate_letters


STICKER_BORDER = 2


def buffer_stickers(category, cat):
    sticker = cat.buffer_sticker or cat.buffer_piece
    piece = find_piece_for_sticker(sticker, CATEGORY_PIECES[category]) if sticker else None
    return CATEGORY_PIECES[category].get(piece, set())


class StickerTiles:
    def __init__(self, category_schemes, on_letter_change, on_field_focus=None, field_registry=None):
        self.category_schemes = category_schemes
        self.on_letter_change = on_letter_change
        self.on_field_focus = on_field_focus
        self.cells = {}
        self.fields = {} if field_registry is None else field_registry
        self.focused = None
        self.resting_borders = {}
        self.focus_colors = {}
        self.duplicates = {category: find_duplicate_letters(cat, category)
                           for category, cat in category_schemes.items()}
        self.duplicated = {sticker for groups in self.duplicates.values()
                           for stickers in groups.values() for sticker in stickers}

    def add(self, sticker, bg, fg, center_tooltip=None):
        border_color = ft.Colors.TRANSPARENT
        if len(sticker) == 1:
            content, tooltip = None, center_tooltip
        else:
            category = "corners" if len(sticker) == 3 else "edges"
            cat = self.category_schemes[category]
            value = cat.stickers.get(sticker, "")
            locked = value == "BUFFER" or sticker in buffer_stickers(category, cat)
            if locked:
                exact = sticker == (cat.buffer_sticker or cat.buffer_piece)
                content = ft.Text("★" if exact else "●", size=18, weight=ft.FontWeight.BOLD, color=fg)
                tooltip = f"{sticker} · {'Buffer sticker' if exact else 'Buffer piece'}"
            else:
                field = ft.TextField(
                    value=value, tooltip=f"{category.title()} · {sticker}",
                    max_length=1, counter="", dense=True, collapsed=True,
                    fit_parent_size=True, autocorrect=False,
                    capitalization=ft.TextCapitalization.CHARACTERS,
                    text_align=ft.TextAlign.CENTER, text_vertical_align=ft.VerticalAlignment.CENTER,
                    text_size=18, text_style=ft.TextStyle(weight=ft.FontWeight.W_600),
                    content_padding=0, border=ft.InputBorder.NONE,
                    border_width=0, focused_border_width=0, filled=False,
                    bgcolor=bg, focused_bgcolor=bg, color=fg, focused_color=fg, cursor_color=fg,
                    selection_color=ft.Colors.with_opacity(0.25, fg),
                    on_change=lambda e, s=sticker: self.on_letter_change(s, e.control.value),
                    on_focus=lambda e, s=sticker: self.set_focus(s, True),
                    on_blur=lambda e, s=sticker: self.set_focus(s, False),
                )
                self.fields[sticker] = field
                content = ft.Semantics(content=field, label=f"{category.title()} sticker {sticker}")
                tooltip = field.tooltip
                if sticker in self.duplicated:
                    border_color = ft.Colors.ERROR
                    tooltip += f" · Duplicate letter {value}"
                self.resting_borders[sticker] = border_color
                self.focus_colors[sticker] = fg
        cell = ft.Container(content, bgcolor=bg, border_radius=4,
                            border=ft.Border.all(STICKER_BORDER, border_color),
                            alignment=ft.Alignment.CENTER, padding=0, tooltip=tooltip)
        self.cells[sticker] = cell
        return cell

    def set_focus(self, sticker, focused):
        # The border has the same width in every state, preserving geometry.
        changed = []
        if focused:
            previous = self.focused
            if previous is not None and previous != sticker:
                self.cells[previous].border = ft.Border.all(STICKER_BORDER, self.resting_borders[previous])
                changed.append(previous)
            self.focused = sticker
            color = self.focus_colors[sticker]
            if self.on_field_focus:
                self.on_field_focus(sticker)
        else:
            if self.focused == sticker:
                self.focused = None
            color = self.resting_borders[sticker]
        self.cells[sticker].border = ft.Border.all(STICKER_BORDER, color)
        changed.append(sticker)
        for key in changed:
            cell = self.cells[key]
            try:
                mounted = cell.page is not None
            except RuntimeError:
                mounted = False
            if mounted:
                cell.update()

    def set_size(self, size):
        for cell in self.cells.values():
            cell.width = cell.height = size
            if isinstance(cell.content, ft.Text):
                cell.content.size = max(13, min(18, size / 2))
        for field in self.fields.values():
            field.width = field.height = size - 2 * STICKER_BORDER
            field.text_size = max(13, min(18, size / 2))

    def warning(self):
        parts = []
        for category, groups in self.duplicates.items():
            if groups:
                details = "; ".join(f"{letter}: {', '.join(stickers)}" for letter, stickers in groups.items())
                parts.append(f"{category.title()}: {details}")
        return "Duplicate letters · " + " · ".join(parts) if parts else ""
