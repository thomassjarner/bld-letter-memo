"""
Resolves the OS-standard per-user data directory, so app updates/reinstalls
of the source code never touch saved schemes or words.

- Windows: %APPDATA%\\BLDLetterMemo
- macOS:   ~/Library/Application Support/BLDLetterMemo
- Linux:   ~/.local/share/BLDLetterMemo (respects $XDG_DATA_HOME)
"""

from pathlib import Path

import platformdirs

APP_NAME = "BLDLetterMemo"
APP_AUTHOR = "BLDLetterMemo"

DATA_FILENAME = "data.json"
BACKUP_FILENAME = "data.corrupt-backup.json"


def get_data_dir() -> Path:
    data_dir = Path(platformdirs.user_data_dir(APP_NAME, APP_AUTHOR))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_data_file() -> Path:
    return get_data_dir() / DATA_FILENAME


def get_corrupt_backup_file() -> Path:
    return get_data_dir() / BACKUP_FILENAME
