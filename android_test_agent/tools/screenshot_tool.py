from __future__ import annotations

from pathlib import Path
from typing import Any

from android_test_agent.tools.adb_tool import ADBTool
from android_test_agent.tools.base import ToolResult


class ScreenshotTool:
    name = "screenshot"
    description = "Capture an Android device screenshot."

    def __init__(self, adb: ADBTool | None = None) -> None:
        self._adb = adb or ADBTool()

    def run(self, input_data: dict[str, Any]) -> ToolResult:
        output_path = Path(input_data.get("output_path", "artifacts/screenshots/screenshot.png"))
        timeout = int(input_data.get("timeout", 60))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        remote_path = "/sdcard/screen.png"

        capture = self._adb.run({"args": ["shell", "screencap", "-p", remote_path], "timeout": timeout})
        if not capture.ok:
            return capture
        pull = self._adb.run({"args": ["pull", remote_path, str(output_path)], "timeout": timeout})
        if not pull.ok:
            return pull
        return ToolResult(ok=True, output=str(output_path), data={"path": str(output_path)})
