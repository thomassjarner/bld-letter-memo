"""Persistent repository backed by Flet SharedPreferences.

On web, SharedPreferences uses browser localStorage.  The primary storage key is
kept stable across releases.  A shadow copy and one rollback snapshot are also
kept so a bad deployment/startup cannot silently replace a populated database
with an empty one.
"""
from __future__ import annotations

import asyncio
import hashlib
import json

import flet as ft

from data.models import AppData
from data.color_themes import LIGHT_THEMES
from data.repository import AppDataRepository


class SharedPreferencesAppDataRepository(AppDataRepository):
    # NEVER rename this key in a normal release: changing it would make existing
    # browser data appear to have vanished.
    STORAGE_KEY = "bld-letter-memo.app-data"
    SHADOW_KEY = "bld-letter-memo.app-data.shadow"
    ROLLBACK_KEY = "bld-letter-memo.app-data.rollback"
    PREFERENCES_KEY = "bld-letter-memo.workspace-preferences"
    CLOUD_CURRENT_KEY = "bld-letter-memo.cloud-local-revision"
    asynchronous_saves = True

    def __init__(self, page: ft.Page, prefs: ft.SharedPreferences, initial: AppData, persisted_payload: str | None):
        self._page = page
        self._prefs = prefs
        self._data = initial
        self._persisted_payload = persisted_payload
        self._pending_payload: str | None = None
        self._flush_running = False
        self._save_status_callback = None
        self._idle = asyncio.Event()
        self._idle.set()
        self.cloud_anchor = self.cloud_owner = None
        self._cloud_tracking = None

    def on_save_status(self, callback):
        self._save_status_callback = callback

    def _status(self, message):
        if self._save_status_callback is not None:
            try:
                self._save_status_callback(message)
            except Exception:
                pass  # A disconnected view must not turn a saved write into a failure.

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
            + len(data.progressive_memo_history) * 5
            + len(data.corner_case_library) * 20
            + sum(len(record.algorithms) * 10 for record in data.corner_case_library.values())
            + len(data.playground_algorithms) * 20
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

        # Only opt-in cloud copies have a commit marker. An intentional deletion
        # in such a copy must not be resurrected by a richer old rollback.
        anchor = owner = None
        verified = None
        try:
            stored = await prefs.get(cls.CLOUD_CURRENT_KEY)
            mark = json.loads(stored) if isinstance(stored, str) else {}
            if isinstance(mark,dict) and type(mark.get("account")) is int:
                owner = mark["account"]
            for item in candidates:
                if item[2] in (0, 1) and isinstance(mark.get("account"), int) and isinstance(mark.get("revision"), int) and mark.get("digest") == cls._digest(item[1]):
                    anchor = (mark["account"], mark["revision"])
                    verified = item
                    break
        except Exception:
            pass  # Guest storage works even if the optional key is unavailable.

        if candidates:
            # Richness first; on ties prefer the primary, then shadow, rollback.
            data, payload, _ = verified or max(candidates, key=lambda item: (cls._richness(item[0]), -item[2]))
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

        # These small, current preferences are independent of which richer
        # recovery snapshot supplies schemes/history. Never resurrect an older
        # scheme selection or appearance just because that snapshot has data.
        try:
            raw = await prefs.get(cls.PREFERENCES_KEY)
            choices = json.loads(raw) if isinstance(raw, str) else None
            if isinstance(choices, dict):
                selected = choices.get('active_scheme')
                if isinstance(selected, str) and selected in initial.schemes:
                    initial.active_scheme = selected
                if isinstance(choices.get('dark_mode'), bool):
                    initial.dark_mode = choices['dark_mode']
                theme = choices.get('light_theme')
                if isinstance(theme, str) and theme in LIGHT_THEMES:
                    initial.light_theme = theme
        except Exception:
            pass

        repo = cls(page, prefs, initial, persisted_payload)
        repo.cloud_anchor,repo.cloud_owner = anchor,owner
        return repo

    @staticmethod
    def _digest(text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def wait_saved(self):
        await self._idle.wait()
        if self._pending_payload is not None:
            raise OSError("Browser save did not finish; cloud sync is paused.")

    def stop_tracking_cloud(self):
        self._cloud_tracking = None

    async def track_cloud(self, account, revision):
        await self.wait_saved()
        self._cloud_tracking = (account, revision)
        self.cloud_owner = account
        if self._persisted_payload:
            await self._mark_cloud_copy(self._persisted_payload)

    async def _put(self,key,value):
        if await self._prefs.set(key,value) is False:
            raise OSError("Browser storage rejected the save.")

    async def _mark_cloud_copy(self, payload):
        account, revision = self._cloud_tracking
        await self._put(self.CLOUD_CURRENT_KEY, json.dumps({
            "account": account, "revision": revision, "digest": self._digest(payload)}))
        self.cloud_anchor = (account, revision)

    def load(self) -> AppData:
        return self._data

    def save(self, data: AppData) -> None:
        self._data = data
        self._pending_payload = json.dumps(data.to_dict(), ensure_ascii=False)
        if not self._flush_running:
            self._idle.clear()
            self._flush_running = True
            self._page.run_task(self._flush_pending)

    async def _flush_pending(self) -> None:
        try:
            while self._pending_payload is not None:
                payload = self._pending_payload
                self._pending_payload = None
                try:
                    snapshot = json.loads(payload)
                    choices = {name: snapshot.get(name) for name in ('active_scheme', 'dark_mode', 'light_theme')}
                    # Save the small workspace selection first, before rotating
                    # potentially much larger history/algorithm backup copies.
                    await self._put(self.PREFERENCES_KEY, json.dumps(choices, ensure_ascii=False))
                    # Preserve the last successfully persisted state before
                    # replacing it, then write two current copies.
                    if self._persisted_payload and self._persisted_payload != payload:
                        await self._put(self.ROLLBACK_KEY, self._persisted_payload)
                    await self._put(self.STORAGE_KEY, payload)
                    await self._put(self.SHADOW_KEY, payload)
                    self._persisted_payload = payload
                    if self._cloud_tracking is not None:
                        await self._mark_cloud_copy(payload)
                    if self._pending_payload is None:
                        self._status('Saved')
                except Exception:
                    # Keep the payload queued for one later save attempt instead
                    # of pretending a failed browser-storage write succeeded.
                    if self._pending_payload is None:
                        self._pending_payload = payload
                    self._status('Save failed — retry on next change')
                    break
        finally:
            self._flush_running = False
            self._idle.set()
            # Do not spin forever after a storage exception.  A subsequent user
            # edit will schedule another attempt automatically.
