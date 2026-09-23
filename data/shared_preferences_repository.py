"""Persistent repository backed by Flet SharedPreferences.

On web, SharedPreferences uses browser localStorage, so data survives GitHub
Pages deployments as long as the site origin and storage key stay the same.
On desktop it also persists using the platform's local preferences backend.
"""
from __future__ import annotations

import json

import flet as ft

from data.models import AppData
from data.repository import AppDataRepository


class SharedPreferencesAppDataRepository(AppDataRepository):
    STORAGE_KEY = "bld-letter-memo.app-data"

    def __init__(self, page: ft.Page, prefs: ft.SharedPreferences, initial: AppData):
        self._page = page
        self._prefs = prefs
        self._data = initial
        self._pending_payload: str | None = None
        self._flush_running = False

    @classmethod
    async def create(cls, page: ft.Page) -> "SharedPreferencesAppDataRepository":
        prefs = ft.SharedPreferences()
        initial = AppData()
        try:
            raw = await prefs.get(cls.STORAGE_KEY)
            if isinstance(raw, str) and raw.strip():
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    initial = AppData.from_dict(parsed)
        except Exception:
            # Never destroy the browser's stored value on a read/parse failure.
            # The user can still recover with Import Backup if needed.
            initial = AppData()
        return cls(page, prefs, initial)

    def load(self) -> AppData:
        return self._data

    def save(self, data: AppData) -> None:
        self._data = data
        # Stable key + versioned payload means app deployments do not wipe data.
        self._pending_payload = json.dumps(data.to_dict(), ensure_ascii=False)
        if not self._flush_running:
            self._flush_running = True
            self._page.run_task(self._flush_pending)

    async def _flush_pending(self) -> None:
        try:
            while self._pending_payload is not None:
                payload = self._pending_payload
                self._pending_payload = None
                await self._prefs.set(self.STORAGE_KEY, payload)
        finally:
            self._flush_running = False
            # If a save landed in the tiny window after the loop completed,
            # schedule one more flush rather than risking a lost last update.
            if self._pending_payload is not None:
                self._flush_running = True
                self._page.run_task(self._flush_pending)
