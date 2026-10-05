"""Editable 3×3 cube net backed by the existing canonical sticker IDs."""
import flet as ft

from core.cube_definitions import CATEGORY_PIECES, face_groups, find_piece_for_sticker
from core.pairs import find_duplicate_letters


# Both canonical face lists run clockwise: corners TL/TR/BR/BL and
# edges top/right/bottom/left. Reuse them rather than renaming any sticker.
def face_stickers():
    corners, edges = dict(face_groups("corners")), dict(face_groups("edges"))
    return {face: (corners[face][0], edges[face][0], corners[face][1],
                   edges[face][3], face, edges[face][1],
                   corners[face][3], edges[face][2], corners[face][2]) for face in corners}


NET_ROWS = ((None, "U", None, None), ("L", "F", "R", "B"), (None, "D", None, None))
COLOR_NAMES = {"W": "White", "Y": "Yellow", "G": "Green", "B": "Blue", "R": "Red", "O": "Orange"}
OPPOSITE = {"W": "Y", "Y": "W", "G": "B", "B": "G", "R": "O", "O": "R"}
COLOR_VECTORS = {"W": (0, 1, 0), "Y": (0, -1, 0), "G": (0, 0, 1),
                 "B": (0, 0, -1), "R": (1, 0, 0), "O": (-1, 0, 0)}
FACE_COLORS = {
    "W": ("#F4F5F1", "#182B25"), "Y": ("#F4CF4A", "#2B270C"),
    "G": ("#217B61", "#FFFFFF"), "B": ("#2468B3", "#FFFFFF"),
    "R": ("#BD4548", "#FFFFFF"), "O": ("#F4A25B", "#38200D"),
}


def orientation_colors(up, front):
    if up not in OPPOSITE or front not in OPPOSITE or front in {up, OPPOSITE[up]}:
        up, front = "W", "G"
    u, f = COLOR_VECTORS[up], COLOR_VECTORS[front]
    right = (u[1] * f[2] - u[2] * f[1], u[2] * f[0] - u[0] * f[2], u[0] * f[1] - u[1] * f[0])
    right_color = next(color for color, vector in COLOR_VECTORS.items() if vector == right)
    return {"U": up, "D": OPPOSITE[up], "F": front, "B": OPPOSITE[front],
            "R": right_color, "L": OPPOSITE[right_color]}


def buffer_stickers(category, cat):
    sticker = cat.buffer_sticker or cat.buffer_piece
    piece = find_piece_for_sticker(sticker, CATEGORY_PIECES[category]) if sticker else None
    return CATEGORY_PIECES[category].get(piece, set())


@ft.control
class CubeNetEditor(ft.Column):
    def init(self):
        config = self.data  # Python-only configuration; never sent to Flet.
        category, scheme = config["category"], config["scheme"]
        self.spacing = 8
        self.cell_controls = {}
        self.face_controls = {}
        self.blank_controls = []
        cat = getattr(scheme, category)
        duplicate_groups = find_duplicate_letters(cat, category)
        duplicated = {sticker for stickers in duplicate_groups.values() for sticker in stickers}
        colors = orientation_colors(scheme.memo_up, scheme.memo_front)
        for face, positions in face_stickers().items():
            cells = []
            for sticker in positions:
                if len(sticker) == 1:
                    bg, fg = FACE_COLORS[colors[face]]
                    cell = ft.Container(ft.Text(face, size=19, weight=ft.FontWeight.BOLD, color=fg),
                                        bgcolor=bg, border_radius=5, alignment=ft.Alignment.CENTER,
                                        tooltip=f"{face} · {COLOR_NAMES[colors[face]]}")
                else:
                    sticker_category = "corners" if len(sticker) == 3 else "edges"
                    sticker_scheme = getattr(scheme, sticker_category)
                    value = sticker_scheme.stickers.get(sticker, "")
                    locked = value == "BUFFER" or sticker in buffer_stickers(sticker_category, sticker_scheme)
                    if sticker_category == category and not locked:
                        cell = ft.TextField(
                            value=value, label=sticker, tooltip=f"{category.title()} · {sticker}",
                            max_length=1, counter="", dense=True,
                            capitalization=ft.TextCapitalization.CHARACTERS,
                            text_align=ft.TextAlign.CENTER, text_size=18,
                            content_padding=ft.Padding.symmetric(horizontal=4, vertical=4),
                            border_radius=5, filled=True, bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST,
                            border_color=ft.Colors.ERROR if sticker in duplicated else ft.Colors.OUTLINE,
                            color=ft.Colors.ON_SURFACE,
                            label_style=ft.TextStyle(size=9, color=ft.Colors.ON_SURFACE_VARIANT),
                            on_change=lambda e, s=sticker: config["on_letter_change"](s, e.control.value),
                            on_focus=(lambda e, s=sticker: config["on_field_focus"](s)) if config.get("on_field_focus") else None,
                        )
                        if config.get("field_registry") is not None:
                            config["field_registry"][sticker] = cell
                    else:
                        exact_buffer = sticker == (sticker_scheme.buffer_sticker or sticker_scheme.buffer_piece)
                        symbol = ("★" if exact_buffer else "●") if locked else value or "·"
                        cell = ft.Container(ft.Column([
                            ft.Text(sticker, size=8, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(symbol, size=16, weight=ft.FontWeight.W_600,
                                    color=ft.Colors.PRIMARY if locked else ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=1, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER),
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH, border_radius=5,
                            alignment=ft.Alignment.CENTER,
                            tooltip=f"{sticker} · {'Buffer sticker' if exact_buffer else 'Buffer piece'}" if locked else f"{sticker} · Switch to {sticker_category.title()} to edit")
                self.cell_controls[sticker] = cell
                cells.append(cell)
            self.face_controls[face] = ft.Container(ft.Column([
                ft.Text(f"{face} · {COLOR_NAMES[colors[face]]}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                *[ft.Row(cells[i:i + 3], spacing=3, tight=True) for i in (0, 3, 6)],
            ], spacing=3, tight=True), padding=5,
                border=ft.Border.all(1, FACE_COLORS[colors[face]][0]), border_radius=7,
                bgcolor=ft.Colors.SURFACE_CONTAINER_LOW)
        rows = []
        for row in NET_ROWS:
            row_controls = []
            for face in row:
                if face is None:
                    blank = ft.Container()
                    self.blank_controls.append(blank)
                    row_controls.append(blank)
                else:
                    row_controls.append(self.face_controls[face])
            rows.append(ft.Row(row_controls, spacing=10, tight=True))
        self.net = ft.Column(rows, spacing=10, tight=True)
        self.net_scroll = ft.Row([self.net], scroll=ft.ScrollMode.AUTO)
        warning = ""
        if duplicate_groups:
            warning = "Duplicate letters: " + "; ".join(f"{letter}: {', '.join(stickers)}" for letter, stickers in duplicate_groups.items())
        self.controls = [
            ft.Text("Type on the cube. Letters save immediately; typing advances to the next sticker.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            self.net_scroll,
            ft.Text(f"Editing {category} · ★ tracing buffer · ● buffer piece · Other-category stickers are read-only", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            *([ft.Text(warning, size=12, color=ft.Colors.ERROR)] if warning else []),
        ]
        self.set_width(config.get("width", 760))

    def set_width(self, available):
        # Keep sticker targets usable. Small windows can scroll the full net
        # horizontally, while the enclosing scheme editor scrolls vertically.
        available = max(80.0, float(available))
        size = max(36, min(44, (available - 94) / 12))
        face_width = 3 * size + 16
        for cell in self.cell_controls.values():
            cell.width = cell.height = size
        for face in self.face_controls.values():
            face.width = face_width
        for blank in self.blank_controls:
            blank.width = face_width
        self.net.width = 4 * face_width + 30
        self.net_scroll.width = available
        self.net_scroll.scroll = ft.ScrollMode.ALWAYS if self.net.width > available else None
        self.net_scroll.alignment = ft.MainAxisAlignment.START if self.net.width > available else ft.MainAxisAlignment.CENTER
        self.width = available


def build_cube_net(category, scheme, on_letter_change, on_field_focus=None, field_registry=None, width=760):
    return CubeNetEditor(data={"category": category, "scheme": scheme,
                               "on_letter_change": on_letter_change, "on_field_focus": on_field_focus,
                               "field_registry": field_registry, "width": width})
