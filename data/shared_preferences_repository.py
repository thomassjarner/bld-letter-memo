"""Persistent repository backed by Flet SharedPreferences.

On web, SharedPreferences uses browser localStorage.  The primary storage key is
kept stable across releases.  A shadow copy and one rollback snapshot are also
kept so a bad deployment/startup cannot silently replace a populated database
with an empty one.
"""
from __future__ import annotations

import json

import flet as ft

from data.models import AppData
from data.repository import AppDataRepository


class SharedPreferencesAppDataRepository(AppDataRepository):
    # NEVER rename this key in a normal release: changing it would make existing
    # browser data appear to have vanished.
    STORAGE_KEY = "bld-letter-memo.app-data"
    SHADOW_KEY = "bld-letter-memo.app-data.shadow"
    ROLLBACK_KEY = "bld-letter-memo.app-data.rollback"

    def __init__(self, page: ft.Page, prefs: ft.SharedPreferences, initial: AppData, persisted_payload: str | None):
        self._page = page
        self._prefs = prefs
        self._data = initial
        self._persisted_payload = persisted_payload
        self._pending_payload: str | None = None
        self._flush_running = False

    @staticmethod
    def _decode(raw) -> tuple[AppData | None, str | None]:
        if not isinstance(raw, str) or not raw.strip():
            return None, None
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return AppData.from_dict(parsed), raw
        except Exception:
            pass
        return None, None

    @staticmethod
    def _richness(data: AppData) -> int:
        """Prefer a populated recovery copy over an accidentally empty one."""
        data.ensure_default_sessions()
        solves = sum(len(v) for v in data.practice_sessions.values())
        scheme_detail = 0
        for scheme in data.schemes.values():
            scheme_detail += len(scheme.corners.stickers) + len(scheme.edges.stickers)
            scheme_detail += len(scheme.corners.cycle_break_stickers) + len(scheme.edges.cycle_break_stickers)
            scheme_detail += len(scheme.corners.cycle_break_priority) + len(scheme.edges.cycle_break_priority)
        return (
            len(data.schemes) * 1000
            + scheme_detail * 10
            + len(data.global_words) * 20
            + len(data.pair_aliases) * 10
            + solves * 5
            + (1 if data.dark_mode else 0)
        )

    @classmethod
    async def create(cls, page: ft.Page) -> "SharedPreferencesAppDataRepository":
        prefs = ft.SharedPreferences()
        candidates: list[tuple[AppData, str, int]] = []
        # Read all copies.  If a release ever writes an empty primary by
        # mistake, the richest valid shadow/rollback copy wins on next load.
        for priority, key in enumerate((cls.STORAGE_KEY, cls.SHADOW_KEY, cls.ROLLBACK_KEY)):
            try:
                data, payload = cls._decode(await prefs.get(key))
                if data is not None and payload is not None:
                    candidates.append((data, payload, priority))
            except Exception:
                continue

        if candidates:
            # Richness first; on ties prefer the primary, then shadow, rollback.
            data, payload, _ = max(candidates, key=lambda item: (cls._richness(item[0]), -item[2]))
            initial = data
            persisted_payload = payload
            # Heal missing/stale primary and shadow copies in the background.
            try:
                await prefs.set(cls.STORAGE_KEY, payload)
                await prefs.set(cls.SHADOW_KEY, payload)
            except Exception:
                pass
        else:
            initial = AppData()
            persisted_payload = None

        return cls(page, prefs, initial, persisted_payload)

    def load(self) -> AppData:
        return self._data

    def save(self, data: AppData) -> None:
        self._data = data
        self._pending_payload = json.dumps(data.to_dict(), ensure_ascii=False)
        if not self._flush_running:
            self._flush_running = True
            self._page.run_task(self._flush_pending)

    async def _flush_pending(self) -> None:
        try:
            while self._pending_payload is not None:
                payload = self._pending_payload
                self._pending_payload = None
                try:
                    # Preserve the last successfully persisted state before
                    # replacing it, then write two current copies.
                    if self._persisted_payload and self._persisted_payload != payload:
                        await self._prefs.set(self.ROLLBACK_KEY, self._persisted_payload)
                    await self._prefs.set(self.STORAGE_KEY, payload)
                    await self._prefs.set(self.SHADOW_KEY, payload)
                    self._persisted_payload = payload
                except Exception:
                    # Keep the payload queued for one later save attempt instead
                    # of pretending a failed browser-storage write succeeded.
                    if self._pending_payload is None:
                        self._pending_payload = payload
                    break
        finally:
            self._flush_running = False
            # Do not spin forever after a storage exception.  A subsequent user
            # edit will schedule another attempt automatically.
