from __future__ import annotations

from pathlib import Path
from typing import Any

from android_test_agent.memory.base import Memory
from android_test_agent.memory.vector_store import JsonVectorStore


class ElementMemory(Memory):
    """Known screen element and locator memory."""

    def __init__(self, path: str | Path = "knowledge/elements/element_memory.json") -> None:
        self._store = JsonVectorStore(path)

    def add(self, item: dict[str, Any]) -> None:
        self._store.add(item)

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return self._store.search(query, limit)
