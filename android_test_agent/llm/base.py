from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """Minimal LLM interface used by agent nodes."""

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return raw model text."""

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        text = self.complete(system_prompt, user_prompt)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM did not return valid JSON: {text}") from exc


class NoopLLMClient(LLMClient):
    """Fallback client for local dry-runs without API keys."""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise RuntimeError("No LLM client is configured")
