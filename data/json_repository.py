"""
JSON-file implementation of AppDataRepository.

Unlike the prototype (which silently discarded the file on a parse error),
a corrupt file is backed up rather than dropped, so a bad write can never
silently erase hundreds of saved words.
"""

import json
import shutil
from pathlib import Path

from data.models import AppData
from data.paths import get_data_file
from data.repository import AppDataRepository


class JsonAppDataRepository(AppDataRepository):
    def __init__(self, data_file: Path | None = None):
        self._data_file = data_file or get_data_file()

    def _corrupt_backup_path(self) -> Path:
        # Always sits next to the actual data file in use, not a hardcoded
        # global path, so this works correctly for custom data_file paths
        # (e.g. in tests) as well as the real user-data location.
        return self._data_file.with_name(self._data_file.stem + ".corrupt-backup.json")

    def load(self) -> AppData:
        if not self._data_file.exists():
            return AppData()

        try:
            with open(self._data_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return AppData.from_dict(raw)
        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            # Preserve the bad file instead of silently losing the user's
            # data, then start fresh so the app is still usable.
            backup_path = self._corrupt_backup_path()
            try:
                shutil.copy2(self._data_file, backup_path)
            except OSError:
                pass
            return AppData()

    def save(self, data: AppData) -> None:
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._data_file.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data.to_dict(), f, indent=2, ensure_ascii=False)
        # Atomic-ish replace: avoids leaving a half-written file if the
        # process is killed mid-write.
        tmp_path.replace(self._data_file)
