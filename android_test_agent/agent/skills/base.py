from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from android_test_agent.tools.base import ToolResult


class Skill(ABC):
    """Base class for future MCP-compatible skills."""

    name: str
    description: str

    @abstractmethod
    def run(self, input_data: dict[str, Any]) -> ToolResult:
        """Execute the skill."""
