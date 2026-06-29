from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Memory(ABC):
    """Base interface for case, element and failure memories."""

    @abstractmethod
    def add(self, item: dict[str, Any]) -> None:
        """Store one memory item."""

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Return memory items related to the query."""
