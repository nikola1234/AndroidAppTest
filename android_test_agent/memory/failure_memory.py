from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from android_test_agent.memory.base import Memory
from android_test_agent.memory.vector_store import JsonVectorStore


class FailureMemory(Memory):
    """Failure pattern and fix memory."""

    def __init__(self, path: str | Path = "knowledge/failures/failure_memory.json") -> None:
        self._store = JsonVectorStore(path)

    def add(self, item: dict[str, Any]) -> None:
        self._store.add(item)

    def upsert_by_fingerprint(self, item: dict[str, Any], *, increment: bool = True) -> dict[str, Any]:
        fingerprint = item.get("fingerprint")
        if not fingerprint:
            self.add(item)
            return item

        now = datetime.now(timezone.utc).isoformat()
        existing = self.find_by_fingerprint(str(fingerprint))
        if existing:
            item = {
                **existing,
                **item,
                "first_seen": existing.get("first_seen") or item.get("first_seen") or now,
                "last_seen": now,
                "occurrence_count": int(existing.get("occurrence_count", 1)) + (1 if increment else 0),
            }
        else:
            item = {
                **item,
                "first_seen": item.get("first_seen") or now,
                "last_seen": item.get("last_seen") or now,
                "occurrence_count": int(item.get("occurrence_count", 1)),
            }
        return self._store.upsert("fingerprint", item)

    def find_by_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        return self._store.find_one("fingerprint", fingerprint)

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return self._store.search(query, limit)
