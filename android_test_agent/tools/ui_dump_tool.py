from __future__ import annotations

from pathlib import Path
from typing import Any

from android_test_agent.tools.adb_tool import ADBTool
from android_test_agent.tools.base import ToolResult


class UIDumpTool:
    name = "ui_dump"
    description = "Dump the current Android UI hierarchy XML."

    def __init__(self, adb: ADBTool | None = None) -> None:
        self._adb = adb or ADBTool()

    def run(self, input_data: dict[str, Any]) -> ToolResult:
        output_path = Path(input_data.get("output_path", "artifacts/ui_dumps/ui_dump.xml"))
        timeout = int(input_data.get("timeout", 60))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        dump = self._adb.run({"args": ["shell", "uiautomator", "dump", "/sdcard/window.xml"], "timeout": timeout})
        if not dump.ok:
            return dump
        pull = self._adb.run({"args": ["pull", "/sdcard/window.xml", str(output_path)], "timeout": timeout})
        if not pull.ok:
            return pull
        return ToolResult(ok=True, output=str(output_path), data={"path": str(output_path)})
