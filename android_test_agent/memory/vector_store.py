from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonVectorStore:
    """Tiny local store used until a real vector database is plugged in."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, item: dict[str, Any]) -> None:
        items = self._load()
        items.append(item)
        self._path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def upsert(self, key: str, item: dict[str, Any]) -> dict[str, Any]:
        items = self._load()
        item_key = item.get(key)
        if item_key is None:
            self.add(item)
            return item

        for index, existing in enumerate(items):
            if existing.get(key) == item_key:
                merged = {**existing, **item}
                items[index] = merged
                self._path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
                return merged

        items.append(item)
        self._path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        return item

    def find_one(self, key: str, value: Any) -> dict[str, Any] | None:
        for item in self._load():
            if item.get(key) == value:
                return item
        return None

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        query_tokens = set(query.lower().split())
        scored = []
        for item in self._load():
            text = json.dumps(item, ensure_ascii=False).lower()
            score = sum(1 for token in query_tokens if token in text)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def _load(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        return json.loads(self._path.read_text(encoding="utf-8"))
