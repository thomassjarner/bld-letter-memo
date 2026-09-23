import json
import shutil
from datetime import date
from pathlib import Path

import flet as ft

from data.models import AppData
from data.paths import get_data_file
from ui.state import AppState


@ft.control
class SettingsPage(ft.Column):
    state: AppState | None = None
    theme_callback: object | None = None

    def init(self):
        self.expand = True
        self.spacing = 12
        self.status_text = ft.Text("")
        self._pending_import: Path | None = None
        self._current_dialog: ft.AlertDialog | None = None

        self.file_picker = ft.FilePicker(on_result=self._import_file_selected)

        self.dark_mode_switch = ft.Switch(
            label="Dark mode",
            value=bool(self.state.data.dark_mode),
            on_change=self._dark_mode_changed,
        )

        data_file = get_data_file()
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
            ft.Text("Backup & data", size=16, weight=ft.FontWeight.BOLD),
            ft.Text("Autosave is on. Your local data is stored here:"),
            ft.Container(
                content=ft.Text(str(data_file), selectable=True, font_family="monospace"),
                padding=10,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border_radius=6,
            ),
            ft.Row(
                [
                    ft.ElevatedButton("Export Backup", icon=ft.Icons.DOWNLOAD, on_click=self._export_backup),
                    ft.ElevatedButton("Import Backup", icon=ft.Icons.UPLOAD_FILE, on_click=self._choose_import),
                ]
            ),
            ft.Text(
                "Importing a backup replaces the current schemes and letter-pair words.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            self.status_text,
        ]

    def did_mount(self):
        # FilePicker is a service in modern Flet. In 0.86 it belongs in
        # page.services, not page.overlay.
        if self.file_picker not in self.page.services:
            self.page.services.append(self.file_picker)

    def _dark_mode_changed(self, e):
        enabled = bool(e.control.value)
        self.state.set_dark_mode(enabled)
        if self.theme_callback:
            self.theme_callback(enabled)

    def _export_backup(self, e):
        data_file = get_data_file()
        if not data_file.exists():
            self.status_text.value = "No data file yet — create a scheme first."
            self.update()
            return
        downloads = Path.home() / "Downloads"
        backup_dir = downloads if downloads.exists() else data_file.parent
        backup_path = backup_dir / f"bld-memo-backup-{date.today().isoformat()}.json"
        shutil.copy2(data_file, backup_path)
        self.status_text.value = f"Backup written to {backup_path}"
        self.update()

    def _choose_import(self, e):
        self.file_picker.pick_files(
            dialog_title="Import BLD Letter Memo backup",
            allow_multiple=False,
            allowed_extensions=["json"],
        )

    def _import_file_selected(self, e: ft.FilePickerResultEvent):
        if not e.files:
            return
        self._pending_import = Path(e.files[0].path)
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Import backup?"),
            content=ft.Text(
                "This will replace your current schemes and letter-pair words with the selected backup."
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self._close_dialog),
                ft.ElevatedButton("Import", on_click=self._confirm_import),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._current_dialog = dialog
        self.page.open(dialog)

    def _close_dialog(self, e):
        if self._current_dialog is not None:
            self.page.close(self._current_dialog)
        self._pending_import = None

    def _confirm_import(self, e):
        path = self._pending_import
        if self._current_dialog is not None:
            self.page.close(self._current_dialog)
        if path is None:
            self.page.update()
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                raise ValueError("Backup root must be an object")
            imported = AppData.from_dict(raw)
            self.state.replace_data(imported)
            self.dark_mode_switch.value = bool(imported.dark_mode)
            if self.theme_callback:
                self.theme_callback(bool(imported.dark_mode))
            self.status_text.value = f"Imported backup: {path.name}"
        except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            self.status_text.value = f"Could not import that backup: {exc}"
        self._pending_import = None
        self.page.update()
