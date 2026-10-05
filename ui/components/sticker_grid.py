"""Compact face cards using the cube editor's fixed colored letter tiles."""
import math
import flet as ft

from core.cube_definitions import face_groups
from data.models import CategoryScheme
from ui.components.cube_net import FACE_COLORS, orientation_colors
from ui.components.sticker_tiles import StickerTiles


FACE_NAMES = {"U": "Up", "L": "Left", "F": "Front", "R": "Right", "B": "Back", "D": "Down"}
MIN_CARD_STICKER_SIZE = 32
CARD_PADDING = 10
CARD_BORDER = 1
CARD_GAP = 8
CELL_GAP = 6
CARD_EXTRA_HEIGHT = 2 * (CARD_PADDING + CARD_BORDER) + 18 + 6 + 12 + 2


@ft.control
class FaceCardsEditor(ft.Column):
    def init(self):
        config = self.data
        category, cat = config["category"], config["category_scheme"]
        scheme = config.get("scheme")
        colors = orientation_colors(scheme.memo_up, scheme.memo_front) if scheme is not None else orientation_colors("W", "G")
        self.spacing = 6
        self.extra_height = 16 + 32 + 2 * self.spacing
        self.tiles = StickerTiles({category: cat}, config["on_letter_change"],
                                  config.get("on_field_focus"), config.get("field_registry"))
        self.cell_controls, self.field_controls = self.tiles.cells, self.tiles.fields
        self.face_controls = {}
        self.tile_columns = []
        for face, stickers in face_groups(category):
            bg, fg = FACE_COLORS[colors[face]]
            columns = []
            for sticker in stickers:
                cell = self.tiles.add(sticker, bg, fg)
                column = ft.Column([
                    ft.Text(sticker, size=9, height=12, text_align=ft.TextAlign.CENTER,
                            color=ft.Colors.ON_SURFACE_VARIANT),
                    cell,
                ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True)
                columns.append(column)
                self.tile_columns.append(column)
            self.face_controls[face] = ft.Container(
                ft.Column([
                    ft.Text(f"{face} · {FACE_NAMES[face]}", size=12, height=18,
                            weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                    ft.Row(columns, spacing=CELL_GAP, alignment=ft.MainAxisAlignment.CENTER),
                ], spacing=6, tight=True),
                padding=CARD_PADDING, border_radius=8,
                bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST,
                border=ft.Border.all(CARD_BORDER, ft.Colors.OUTLINE_VARIANT),
            )
        self.card_grid = ft.Row(list(self.face_controls.values()), spacing=CARD_GAP,
                                run_spacing=CARD_GAP, wrap=True,
                                vertical_alignment=ft.CrossAxisAlignment.START)
        warning = self.tiles.warning()
        self.controls = [
            ft.Text("Type letters · Auto-saved · Advance automatically", size=11, height=16,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                    tooltip="Letters save immediately; typing advances to the next sticker.",
                    color=ft.Colors.ON_SURFACE_VARIANT),
            self.card_grid,
            ft.Text("★ Buffer · ● Same piece", size=10, height=32, color=ft.Colors.ON_SURFACE_VARIANT),
            *([ft.Text(warning, size=12, color=ft.Colors.ERROR)] if warning else []),
        ]
        self.set_viewport(config.get("width", 760), config.get("height"))

    def set_viewport(self, available, height=None):
        available = max(80.0, float(available))
        frame = 2 * (CARD_PADDING + CARD_BORDER) + 3 * CELL_GAP
        minimum_card_width = 4 * MIN_CARD_STICKER_SIZE + frame
        columns = min(3, max(1, int((available + CARD_GAP) / (minimum_card_width + CARD_GAP))))
        rows = math.ceil(6 / columns)
        card_width = math.floor((available - (columns - 1) * CARD_GAP) / columns)
        size = min(44, (card_width - frame) / 4)
        if height is not None:
            size = min(size, (max(0.0, float(height)) - (rows - 1) * CARD_GAP) / rows - CARD_EXTRA_HEIGHT)
        size = max(MIN_CARD_STICKER_SIZE, size)
        card_height = size + CARD_EXTRA_HEIGHT
        self.tiles.set_size(size)
        for column in self.tile_columns:
            column.width, column.height = size, size + 14
        for card in self.face_controls.values():
            card.width, card.height = card_width, card_height
        # One wrapping parent keeps every card/input mounted through changes
        # in the number of columns, preserving the editing state.
        self.columns = columns
        self.card_grid.width = available
        self.card_grid.height = rows * card_height + (rows - 1) * CARD_GAP
        self.width = available


def build_sticker_grid(category: str, category_scheme: CategoryScheme, on_letter_change,
                       on_field_focus=None, field_registry=None, *, scheme=None, width=760, height=None):
    return FaceCardsEditor(data={"category": category, "category_scheme": category_scheme,
                                 "scheme": scheme, "on_letter_change": on_letter_change,
                                 "on_field_focus": on_field_focus, "field_registry": field_registry,
                                 "width": width, "height": height})
