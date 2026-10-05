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
FRAME_COLOR = "#101615"
STICKER_GAP = 3
FACE_PADDING = 4
NET_GAP = 6
STICKER_BORDER = 2
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


def buffer_stickers(category, cat):
    sticker = cat.buffer_sticker or cat.buffer_piece
    piece = find_piece_for_sticker(sticker, CATEGORY_PIECES[category]) if sticker else None
    return CATEGORY_PIECES[category].get(piece, set())


@ft.control
class CubeNetEditor(ft.Column):
    def init(self):
        config = self.data  # Python-only configuration; never sent to Flet.
        category, scheme = config["category"], config["scheme"]
        self.spacing = 6
        self.extra_height = 16 + 32 + 2 * self.spacing
        self.cell_controls = {}
        self.field_controls = {}
        self.face_controls = {}
        self.blank_controls = []
        self._focused_cell = None
        self._resting_borders = {}
        self._focus_colors = {}
        cat = getattr(scheme, category)
        duplicate_groups = find_duplicate_letters(cat, category)
        duplicated = {sticker for stickers in duplicate_groups.values() for sticker in stickers}
        colors = orientation_colors(scheme.memo_up, scheme.memo_front)
        for face, positions in face_stickers().items():
            bg, fg = FACE_COLORS[colors[face]]
            cells = []
            for sticker in positions:
                if len(sticker) == 1:
                    content = None
                    tooltip = f"{face} · {COLOR_NAMES[colors[face]]}"
                    border_color = ft.Colors.TRANSPARENT
                else:
                    sticker_category = "corners" if len(sticker) == 3 else "edges"
                    sticker_scheme = getattr(scheme, sticker_category)
                    value = sticker_scheme.stickers.get(sticker, "")
                    locked = value == "BUFFER" or sticker in buffer_stickers(sticker_category, sticker_scheme)
                    if sticker_category == category and not locked:
                        # The colored square owns the shape. The input has no
                        # floating label, fill or border to resize on focus.
                        field = ft.TextField(
                            value=value, tooltip=f"{category.title()} · {sticker}",
                            max_length=1, counter="", dense=True, collapsed=True,
                            fit_parent_size=True, autocorrect=False,
                            capitalization=ft.TextCapitalization.CHARACTERS,
                            text_align=ft.TextAlign.CENTER,
                            text_vertical_align=ft.VerticalAlignment.CENTER,
                            text_size=18, text_style=ft.TextStyle(weight=ft.FontWeight.W_600),
                            content_padding=0, border=ft.InputBorder.NONE,
                            border_width=0, focused_border_width=0, filled=False,
                            bgcolor=bg, focused_bgcolor=bg,
                            color=fg, focused_color=fg, cursor_color=fg,
                            selection_color=ft.Colors.with_opacity(0.25, fg),
                            on_change=lambda e, s=sticker: config["on_letter_change"](s, e.control.value),
                            on_focus=lambda e, s=sticker: self._set_cell_focus(s, True),
                            on_blur=lambda e, s=sticker: self._set_cell_focus(s, False),
                        )
                        self.field_controls[sticker] = field
                        if config.get("field_registry") is not None:
                            config["field_registry"][sticker] = field
                        content = ft.Semantics(content=field, label=f"{category.title()} sticker {sticker}")
                        tooltip = field.tooltip
                        border_color = ft.Colors.ERROR if sticker in duplicated else ft.Colors.TRANSPARENT
                        if sticker in duplicated:
                            tooltip += f" · Duplicate letter {value}"
                        self._resting_borders[sticker] = border_color
                        self._focus_colors[sticker] = fg
                    else:
                        exact_buffer = sticker == (sticker_scheme.buffer_sticker or sticker_scheme.buffer_piece)
                        symbol = ("★" if exact_buffer else "●") if locked else value or "·"
                        content = ft.Text(symbol, size=18,
                                          weight=ft.FontWeight.BOLD if locked else ft.FontWeight.W_500,
                                          color=fg)
                        tooltip = (f"{sticker} · {'Buffer sticker' if exact_buffer else 'Buffer piece'}" if locked
                                   else f"{sticker} · Switch to {sticker_category.title()} to edit")
                        border_color = ft.Colors.TRANSPARENT
                cell = ft.Container(content, bgcolor=bg, border_radius=4,
                                    border=ft.Border.all(STICKER_BORDER, border_color),
                                    alignment=ft.Alignment.CENTER, padding=0, tooltip=tooltip)
                self.cell_controls[sticker] = cell
                cells.append(cell)
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
        warning = ""
        if duplicate_groups:
            warning = "Duplicate letters: " + "; ".join(f"{letter}: {', '.join(stickers)}" for letter, stickers in duplicate_groups.items())
        self.controls = [
            ft.Text("Type letters · Auto-saved · Advance automatically", size=11, height=16,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                    tooltip="Letters save immediately; typing advances to the next sticker.",
                    color=ft.Colors.ON_SURFACE_VARIANT),
            self.net_scroll,
            ft.Text("★ Buffer · ● Same piece · Other letters are read-only", size=10,
                    height=32, max_lines=2, color=ft.Colors.ON_SURFACE_VARIANT),
            *([ft.Text(warning, size=12, color=ft.Colors.ERROR)] if warning else []),
        ]
        self.set_viewport(config.get("width", 760), config.get("height"))

    def _set_cell_focus(self, sticker, focused):
        # Reserve the same border on every sticker, so highlighting changes
        # only its color and never moves the text or neighboring cells.
        changed = []
        if focused:
            previous = self._focused_cell
            if previous is not None and previous != sticker:
                self.cell_controls[previous].border = ft.Border.all(STICKER_BORDER, self._resting_borders[previous])
                changed.append(previous)
            self._focused_cell = sticker
            color = self._focus_colors[sticker]
            if self.data.get("on_field_focus"):
                self.data["on_field_focus"](sticker)
        else:
            if self._focused_cell == sticker:
                self._focused_cell = None
            color = self._resting_borders[sticker]
        self.cell_controls[sticker].border = ft.Border.all(STICKER_BORDER, color)
        changed.append(sticker)
        for key in changed:
            cell = self.cell_controls[key]
            # Detached controls have no page during construction and tests.
            try:
                mounted = cell.page is not None
            except RuntimeError:
                mounted = False
            if mounted:
                cell.update()

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
        for cell in self.cell_controls.values():
            cell.width = cell.height = size
        for field in self.field_controls.values():
            field.width = field.height = size - 2 * STICKER_BORDER
            field.text_size = max(13, min(18, size / 2))
        for cell in self.cell_controls.values():
            if isinstance(cell.content, ft.Text):
                cell.content.size = max(13, min(18, size / 2))
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
