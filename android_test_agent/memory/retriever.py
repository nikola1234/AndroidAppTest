from __future__ import annotations

from android_test_agent.memory.base import Memory


class KnowledgeRetriever:
    """Aggregate multiple memory sources for prompt context."""

    def __init__(self, memories: list[Memory]) -> None:
        self._memories = memories

    def search(self, query: str, limit_per_memory: int = 3) -> list[dict]:
        results: list[dict] = []
        for memory in self._memories:
            results.extend(memory.search(query, limit_per_memory))
        return results
