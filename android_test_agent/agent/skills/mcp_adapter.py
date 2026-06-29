from __future__ import annotations

from typing import Any

from android_test_agent.tools.base import Tool, ToolResult


class MCPAdapter:
    """Small adapter that can expose local tools as MCP-style skills later."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> list[dict[str, str]]:
        return [
            {"name": tool.name, "description": tool.description}
            for tool in self._tools.values()
        ]

    def call(self, name: str, input_data: dict[str, Any]) -> ToolResult:
        if name not in self._tools:
            return ToolResult(ok=False, error=f"Unknown tool: {name}")
        return self._tools[name].run(input_data)
