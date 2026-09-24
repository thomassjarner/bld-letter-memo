import json
from datetime import date

import flet as ft

from data.models import AppData
from ui.state import AppState


@ft.control
class SettingsPage(ft.Column):
    @property
    def state(self):
        # BaseControl.data is a Flet skip_field(), so Python-only AppState
        # never enters the browser serialization protocol.
        return self.data

    theme_callback = None


    def init(self):
        self.expand = True
        self.spacing = 12
        self.status_text = ft.Text("")
        self._pending_import: tuple[str, bytes] | None = None
        self._current_dialog: ft.AlertDialog | None = None


        self.dark_mode_switch = ft.Switch(
            label="Dark mode",
            value=bool(self.state.data.dark_mode),
            on_change=self._dark_mode_changed,
        )

        self.rating_mode_dropdown = ft.Dropdown(
            label="Rating system",
            width=220,
            value=self.state.data.letter_pair_rating_mode,
            options=[
                ft.DropdownOption("numeric", "Numerical (1–5)"),
                ft.DropdownOption("colors", "Colors"),
                ft.DropdownOption("qualitative", "Bad / Mid / Good"),
            ],
            on_select=self._rating_mode_changed,
        )
        self.rating_levels_dropdown = ft.Dropdown(
            label="Color levels", width=150, value=str(self.state.data.rating_color_levels),
            options=[ft.DropdownOption(str(x), str(x)) for x in (3, 4, 5)],
            on_select=self._rating_levels_changed,
        )
        self.rating_palette_area = ft.Column(spacing=6)
        self._rebuild_rating_palette()

        self.controls = [
            ft.Text("Settings", size=20, weight=ft.FontWeight.BOLD),
            ft.Text("General", size=16, weight=ft.FontWeight.BOLD),
            self.dark_mode_switch,
            ft.Text(
                "Dark mode uses a softer teal accent so controls stay visible without being overly bright.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Divider(),
            ft.Text("Letter pairs settings", size=16, weight=ft.FontWeight.BOLD),
            self.rating_mode_dropdown,
            ft.Text(
                "Ratings are always stored on a common 1–5 scale, so changing the display system does not lose your grades.",
                size=12, color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Row([self.rating_levels_dropdown], wrap=True),
            self.rating_palette_area,
            ft.Divider(),
            ft.Text("Backup & data", size=16, weight=ft.FontWeight.BOLD),
            ft.Text("Autosave is on. Schemes, advanced settings, pair words/labels, timer sessions, and preferences are stored locally in this browser and survive app updates."),
            ft.Row(
                [
                    ft.ElevatedButton("Export Backup", icon=ft.Icons.DOWNLOAD, on_click=self._export_backup),
                    ft.ElevatedButton("Import Backup", icon=ft.Icons.UPLOAD_FILE, on_click=self._choose_import),
                ]
            ),
            ft.Text(
                "Importing a backup replaces the current schemes, letter-pair data, timer sessions, and settings.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            self.status_text,
        ]

    def _dark_mode_changed(self, e):
        enabled = bool(e.control.value)
        self.state.set_dark_mode(enabled)
        if self.theme_callback:
            self.theme_callback(enabled)

    def _rating_mode_changed(self, e):
        self.state.set_letter_pair_rating_mode(e.control.value)
        self.update()

    def _rating_levels_changed(self, e):
        try:
            levels = int(e.control.value)
        except (TypeError, ValueError):
            return
        self.state.set_rating_color_levels(levels)
        self._rebuild_rating_palette()
        self.rating_palette_area.update()

    def _rebuild_rating_palette(self):
        rows = []
        colors = list(self.state.data.rating_color_hexes)
        grades = list(self.state.data.rating_color_grades)
        for i, (color, grade) in enumerate(zip(colors, grades)):
            color_field = ft.TextField(
                label=f"Level {i+1} color", value=color, width=150, dense=True,
                on_blur=lambda e, idx=i: self._save_rating_color(idx, e.control),
                on_submit=lambda e, idx=i: self._save_rating_color(idx, e.control),
            )
            grade_field = ft.TextField(
                label="Grade", value=(f"{grade:.2f}".rstrip("0").rstrip(".")), width=90, dense=True,
                on_blur=lambda e, idx=i: self._save_rating_grade(idx, e.control),
                on_submit=lambda e, idx=i: self._save_rating_grade(idx, e.control),
            )
            rows.append(ft.Row([
                ft.Container(width=22, height=22, bgcolor=color, border_radius=11),
                color_field, grade_field,
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER))
        self.rating_palette_area.controls = rows

    def _save_rating_color(self, index, control):
        if not self.state.set_rating_color(index, control.value):
            control.value = self.state.data.rating_color_hexes[index]
            control.error_text = "Use a hex color like #F9A825"
        else:
            control.value = self.state.data.rating_color_hexes[index]
            control.error_text = None
        control.update()

    def _save_rating_grade(self, index, control):
        if not self.state.set_rating_color_grade(index, control.value):
            control.value = str(self.state.data.rating_color_grades[index])
            control.error_text = "Grade must be between 1 and 5"
        else:
            control.value = f"{self.state.data.rating_color_grades[index]:.2f}".rstrip("0").rstrip(".")
            control.error_text = None
        control.update()

    async def _export_backup(self, e):
        try:
            payload = json.dumps(
                self.state.data.to_dict(), indent=2, ensure_ascii=False
            ).encode("utf-8")
            filename = f"bld-memo-backup-{date.today().isoformat()}.json"
            saved = await ft.FilePicker().save_file(
                file_name=filename,
                src_bytes=payload,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["json"],
            )
            self.status_text.value = (
                f"Backup exported: {filename}" if saved is not None else "Backup export cancelled."
            )
        except Exception as exc:
            self.status_text.value = f"Could not export backup: {exc}"
        self.update()

    async def _choose_import(self, e):
        try:
            files = await ft.FilePicker().pick_files(
                dialog_title="Import BLD Letter Memo backup",
                allow_multiple=False,
                with_data=True,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["json"],
            )
        except Exception as exc:
            self.status_text.value = f"Could not open backup picker: {exc}"
            self.update()
            return

        if not files:
            return
        selected = files[0]
        if selected.bytes is None:
            self.status_text.value = "Could not read that backup file."
            self.update()
            return

        self._pending_import = (selected.name, selected.bytes)
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Import backup?"),
            content=ft.Text(
                "This will replace your current schemes, letter-pair data, timer sessions, and settings with the selected backup."
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self._close_dialog),
                ft.ElevatedButton("Import", on_click=self._confirm_import),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._current_dialog = dialog
        self.page.show_dialog(dialog)

    def _close_dialog(self, e=None):
        if self._current_dialog is not None:
            self.page.pop_dialog()
            self._current_dialog = None
        self._pending_import = None

    def _confirm_import(self, e):
        pending = self._pending_import
        if self._current_dialog is not None:
            self.page.pop_dialog()
            self._current_dialog = None
        if pending is None:
            self.page.update()
            return
        name, raw_bytes = pending
        try:
            raw = json.loads(raw_bytes.decode("utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Backup root must be an object")
            imported = AppData.from_dict(raw)
            self.state.replace_data(imported)
            self.dark_mode_switch.value = bool(imported.dark_mode)
            if self.theme_callback:
                self.theme_callback(bool(imported.dark_mode))
            self.status_text.value = f"Imported backup: {name}"
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            self.status_text.value = f"Could not import that backup: {exc}"
        self._pending_import = None
        self.page.update()
