import json
from datetime import date

import flet as ft

from data.models import AppData
from ui.state import AppState


@ft.control
class SettingsPage(ft.Column):
    state: AppState | None = None
    theme_callback: object | None = None

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
            ft.Text("Autosave is on. Your data is stored locally for this app/browser."),
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

    def _dark_mode_changed(self, e):
        enabled = bool(e.control.value)
        self.state.set_dark_mode(enabled)
        if self.theme_callback:
            self.theme_callback(enabled)

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
        pending = self._pending_import
        if self._current_dialog is not None:
            self.page.close(self._current_dialog)
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
