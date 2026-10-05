"""Editable 3×3 cube net backed by the existing canonical sticker IDs."""
import flet as ft

from core.cube_definitions import face_groups
from ui.components.sticker_tiles import STICKER_BORDER, StickerTiles, buffer_stickers


# Both canonical face lists run clockwise: corners TL/TR/BR/BL and
# edges top/right/bottom/left. Reuse them rather than renaming any sticker.
def face_stickers():
    corners, edges = dict(face_groups("corners")), dict(face_groups("edges"))
    return {face: (corners[face][0], edges[face][0], corners[face][1],
                   edges[face][3], face, edges[face][1],
                   corners[face][3], edges[face][2], corners[face][2]) for face in corners}


NET_ROWS = ((None, "U", None, None), ("L", "F", "R", "B"), (None, "D", None, None))
CUBE_STICKER_ORDER = tuple(sticker for face in face_stickers().values() for sticker in face if len(sticker) > 1)
COLOR_NAMES = {"W": "White", "Y": "Yellow", "G": "Green", "B": "Blue", "R": "Red", "O": "Orange"}
OPPOSITE = {"W": "Y", "Y": "W", "G": "B", "B": "G", "R": "O", "O": "R"}
COLOR_VECTORS = {"W": (0, 1, 0), "Y": (0, -1, 0), "G": (0, 0, 1),
                 "B": (0, 0, -1), "R": (1, 0, 0), "O": (-1, 0, 0)}
FACE_COLORS = {
    "W": ("#F4F5F1", "#182B25"), "Y": ("#F4CF4A", "#2B270C"),
    "G": ("#217B61", "#FFFFFF"), "B": ("#2468B3", "#FFFFFF"),
    "R": ("#BD4548", "#FFFFFF"), "O": ("#F4A25B", "#38200D"),
}
FRAME_COLOR = "#101615"
STICKER_GAP = 3
FACE_PADDING = 4
NET_GAP = 6
MIN_STICKER_SIZE = 24
SCROLLBAR_SPACE = 12


def orientation_colors(up, front):
    if up not in OPPOSITE or front not in OPPOSITE or front in {up, OPPOSITE[up]}:
        up, front = "W", "G"
    u, f = COLOR_VECTORS[up], COLOR_VECTORS[front]
    right = (u[1] * f[2] - u[2] * f[1], u[2] * f[0] - u[0] * f[2], u[0] * f[1] - u[1] * f[0])
    right_color = next(color for color, vector in COLOR_VECTORS.items() if vector == right)
    return {"U": up, "D": OPPOSITE[up], "F": front, "B": OPPOSITE[front],
            "R": right_color, "L": OPPOSITE[right_color]}


@ft.control
class CubeNetEditor(ft.Column):
    def init(self):
        config = self.data  # Python-only configuration; never sent to Flet.
        scheme = config["scheme"]
        self.spacing = 6
        self.extra_height = 16 + 32 + 2 * self.spacing
        self.tiles = StickerTiles(
            {category: getattr(scheme, category) for category in ("edges", "corners")},
            config["on_letter_change"], config.get("on_field_focus"), config.get("field_registry"),
        )
        self.cell_controls, self.field_controls = self.tiles.cells, self.tiles.fields
        self.face_controls = {}
        self.blank_controls = []
        colors = orientation_colors(scheme.memo_up, scheme.memo_front)
        for face, positions in face_stickers().items():
            bg, fg = FACE_COLORS[colors[face]]
            cells = [self.tiles.add(sticker, bg, fg, f"{face} · {COLOR_NAMES[colors[face]]}")
                     for sticker in positions]
            self.face_controls[face] = ft.Container(ft.Column([
                ft.Row(cells[i:i + 3], spacing=STICKER_GAP, tight=True) for i in (0, 3, 6)
            ], spacing=STICKER_GAP, tight=True), padding=FACE_PADDING,
                border_radius=7, bgcolor=FRAME_COLOR)
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
            rows.append(ft.Row(row_controls, spacing=NET_GAP, tight=True))
        self.net = ft.Column(rows, spacing=NET_GAP, tight=True)
        self.net_scroll = ft.Row([self.net], scroll=ft.ScrollMode.AUTO)
        warning = self.tiles.warning()
        self.controls = [
            ft.Text("Type letters · Auto-saved · Advance automatically", size=11, height=16,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                    tooltip="Letters save immediately; typing advances to the next sticker.",
                    color=ft.Colors.ON_SURFACE_VARIANT),
            self.net_scroll,
            ft.Text("Editing edges + corners · ★ Buffer · ● Same piece", size=10,
                    height=32, max_lines=2, color=ft.Colors.ON_SURFACE_VARIANT),
            *([ft.Text(warning, size=12, color=ft.Colors.ERROR)] if warning else []),
        ]
        self.set_viewport(config.get("width", 760), config.get("height"))

    def set_width(self, available):
        self.set_viewport(available, getattr(self, "_available_height", None))

    def set_viewport(self, available, height=None):
        # Fit both dimensions. If a very small viewport would make entry
        # targets unusable, retain readable squares and let the page scroll.
        available = max(80.0, float(available))
        self._available_height = None if height is None else max(0.0, float(height))
        frame = 2 * STICKER_GAP + 2 * FACE_PADDING
        size = min(44, (available - 4 * frame - 3 * NET_GAP) / 12)
        if self._available_height is not None:
            minimum_width = 12 * MIN_STICKER_SIZE + 4 * frame + 3 * NET_GAP
            scrollbar = SCROLLBAR_SPACE if available < minimum_width else 0
            size = min(size, (self._available_height - 3 * frame - 2 * NET_GAP - scrollbar) / 9)
        size = max(MIN_STICKER_SIZE, size)
        face_width = 3 * size + frame
        self.tiles.set_size(size)
        for face in self.face_controls.values():
            face.width = face.height = face_width
        for blank in self.blank_controls:
            blank.width = blank.height = face_width
        self.net.width = 4 * face_width + 3 * NET_GAP
        self.net.height = 3 * face_width + 2 * NET_GAP
        self.net_scroll.width = available
        overflow = self.net.width > available
        self.net_scroll.height = self.net.height + (SCROLLBAR_SPACE if overflow else 0)
        self.net_scroll.scroll = ft.ScrollMode.ALWAYS if overflow else None
        self.net_scroll.alignment = ft.MainAxisAlignment.START if overflow else ft.MainAxisAlignment.CENTER
        self.width = available


def build_cube_net(category, scheme, on_letter_change, on_field_focus=None, field_registry=None, width=760, height=None):
    return CubeNetEditor(data={"category": category, "scheme": scheme,
                               "on_letter_change": on_letter_change, "on_field_focus": on_field_focus,
                               "field_registry": field_registry, "width": width, "height": height})
