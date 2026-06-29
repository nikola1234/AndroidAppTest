from __future__ import annotations

from pathlib import Path
from typing import Any

from android_test_agent.tools.adb_tool import ADBTool
from android_test_agent.tools.base import ToolResult


class LogcatTool:
    name = "logcat"
    description = "Collect Android logcat output."

    def __init__(self, adb: ADBTool | None = None) -> None:
        self._adb = adb or ADBTool()

    def run(self, input_data: dict[str, Any]) -> ToolResult:
        output_path = Path(input_data.get("output_path", "artifacts/logcat/logcat.txt"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = str(input_data.get("lines", "500"))

        result = self._adb.run({"args": ["logcat", "-d", "-t", lines]})
        if not result.ok:
            return result
        output_path.write_text(result.output, encoding="utf-8")
        return ToolResult(ok=True, output=str(output_path), data={"path": str(output_path)})
