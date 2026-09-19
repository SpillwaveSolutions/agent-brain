"""Repository implementations. Both follow the same contract."""

from __future__ import annotations

import sqlite3
from typing import Protocol

from inventory.models import Item


class Repository(Protocol):
    """Storage contract used by the service layer."""

    def get(self, sku: str) -> Item | None: ...

    def save(self, item: Item) -> None: ...

    def list_all(self) -> list[Item]: ...


class InMemoryRepository:
    """Dict-backed store for tests."""

    def __init__(self) -> None:
        self._items: dict[str, Item] = {}

    def get(self, sku: str) -> Item | None:
        return self._items.get(sku)

    def save(self, item: Item) -> None:
        self._items[item.sku] = item

    def list_all(self) -> list[Item]:
        return list(self._items.values())


class SqliteRepository:
    """SQLite-backed store. One table named items. See ADR 0001."""

    def __init__(self, path: str = "inventory.sqlite3") -> None:
        self._conn = sqlite3.connect(path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS items "
            "(sku TEXT PRIMARY KEY, name TEXT NOT NULL, on_hand INTEGER NOT NULL)"
        )

    def get(self, sku: str) -> Item | None:
        row = self._conn.execute(
            "SELECT sku, name, on_hand FROM items WHERE sku = ?", (sku,)
        ).fetchone()
        return Item(*row) if row else None

    def save(self, item: Item) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO items (sku, name, on_hand) VALUES (?, ?, ?)",
            (item.sku, item.name, item.on_hand),
        )
        self._conn.commit()

    def list_all(self) -> list[Item]:
        rows = self._conn.execute("SELECT sku, name, on_hand FROM items").fetchall()
        return [Item(*row) for row in rows]
