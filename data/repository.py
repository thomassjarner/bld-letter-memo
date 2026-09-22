"""
Abstract storage interface. The UI and core logic only ever talk to this
interface, never to JSON/SQLite/etc directly, so the storage backend can
be swapped later (e.g. JsonAppDataRepository -> SqliteAppDataRepository)
without touching anything else.
"""

from abc import ABC, abstractmethod

from data.models import AppData


class AppDataRepository(ABC):
    @abstractmethod
    def load(self) -> AppData:
        ...

    @abstractmethod
    def save(self, data: AppData) -> None:
        ...
