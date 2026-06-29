from __future__ import annotations

import subprocess
import sys
from typing import Any

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.agent.state import ExecutionResult
from android_test_agent.executor.appium_executor import AppiumExecutor


class DSLExecutor:
    """Interpret the DSL directly with an Appium executor."""

    def __init__(self, appium_executor: AppiumExecutor) -> None:
        self._appium_executor = appium_executor

    def run(self, dsl: dict[str, Any]) -> ExecutionResult:
        try:
            self._appium_executor.start()
            for step in dsl["steps"]:
                self._appium_executor.run_step(step)
        except Exception as exc:
            return {
                "status": "failed",
                "stdout": "",
                "stderr": str(exc),
            }
        finally:
            self._appium_executor.stop()
        return {
            "status": "passed",
            "stdout": "DSL executed successfully.",
            "stderr": "",
        }


class PytestExecutor:
    """Execute generated pytest/Appium code."""

    def __init__(self, config: AndroidTestConfig) -> None:
        self._config = config

    def run(self, test_path: str) -> ExecutionResult:
        if not self._config.execute_generated_tests:
            return {
                "status": "dry_run",
                "generated_test_path": test_path,
                "stdout": "Generated test code successfully. Execution is disabled.",
                "stderr": "",
            }

        command = [sys.executable, "-m", "pytest", test_path, "-q"]
        completed = subprocess.run(
            command,
            cwd=self._config.project_root,
            text=True,
            capture_output=True,
            timeout=600,
        )
        return {
            "status": "passed" if completed.returncode == 0 else "failed",
            "command": command,
            "return_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "generated_test_path": test_path,
        }
