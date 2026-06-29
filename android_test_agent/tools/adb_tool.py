from __future__ import annotations

import subprocess
from typing import Any

from android_test_agent.tools.base import ToolResult


class ADBTool:
    name = "adb"
    description = "Run adb commands against the connected Android device."

    def run(self, input_data: dict[str, Any]) -> ToolResult:
        args = input_data.get("args", [])
        if not isinstance(args, list):
            return ToolResult(ok=False, error="args must be a list")
        try:
            completed = subprocess.run(
                ["adb", *map(str, args)],
                text=True,
                capture_output=True,
                timeout=int(input_data.get("timeout", 60)),
            )
        except FileNotFoundError:
            return ToolResult(ok=False, error="adb executable was not found in PATH")
        except subprocess.TimeoutExpired as exc:
            return ToolResult(ok=False, output=exc.stdout or "", error=exc.stderr or "adb command timed out")
        return ToolResult(
            ok=completed.returncode == 0,
            output=completed.stdout,
            error=completed.stderr,
            data={"return_code": completed.returncode},
        )
