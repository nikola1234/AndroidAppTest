from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class ToolResult:
    ok: bool
    output: str = ""
    error: str = ""
    data: dict[str, Any] | None = None


class Tool(Protocol):
    name: str
    description: str

    def run(self, input_data: dict[str, Any]) -> ToolResult:
        ...
