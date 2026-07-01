from __future__ import annotations

import subprocess
import sys
import time
from typing import Any

from android_test_agent.tools.base import ToolResult


class ADBTool:
    name = "adb"
    description = "Run adb commands against the connected Android device."

    def run(self, input_data: dict[str, Any]) -> ToolResult:
        args = input_data.get("args", [])
        if not isinstance(args, list):
            return ToolResult(ok=False, error="args must be a list")
        command = ["adb", *map(str, args)]
        timeout = int(input_data.get("timeout", 60))
        started_at = time.monotonic()
        print(
            f"[android-test-agent] adb call started: command={self._format_command(command)}, timeout={timeout}s",
            file=sys.stderr,
        )
        try:
            completed = subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            self._print_finished(started_at, ok=False, error="adb executable was not found in PATH")
            return ToolResult(ok=False, error="adb executable was not found in PATH")
        except subprocess.TimeoutExpired as exc:
            self._print_finished(started_at, ok=False, error=exc.stderr or "adb command timed out")
            return ToolResult(ok=False, output=exc.stdout or "", error=exc.stderr or "adb command timed out")
        self._print_finished(
            started_at,
            ok=completed.returncode == 0,
            return_code=completed.returncode,
            stderr=completed.stderr,
        )
        return ToolResult(
            ok=completed.returncode == 0,
            output=completed.stdout,
            error=completed.stderr,
            data={"return_code": completed.returncode},
        )

    def _print_finished(
        self,
        started_at: float,
        *,
        ok: bool,
        return_code: int | None = None,
        stderr: str = "",
        error: str = "",
    ) -> None:
        elapsed = time.monotonic() - started_at
        details = [f"ok={str(ok).lower()}", f"elapsed={elapsed:.2f}s"]
        if return_code is not None:
            details.append(f"return_code={return_code}")
        message = (error or stderr or "").strip()
        if message:
            details.append(f"error={message[:300]}")
        print("[android-test-agent] adb call finished: " + ", ".join(details), file=sys.stderr)

    def _format_command(self, command: list[str]) -> str:
        return " ".join(self._quote_arg(arg) for arg in command)

    def _quote_arg(self, value: str) -> str:
        if not value or any(char.isspace() for char in value):
            return '"' + value.replace('"', '\\"') + '"'
        return value
