from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.agent.state import AgentState
from android_test_agent.tools.appium_tool import AppiumTool
from android_test_agent.tools.logcat_tool import LogcatTool
from android_test_agent.tools.screenshot_tool import ScreenshotTool
from android_test_agent.tools.ui_dump_tool import UIDumpTool


class FailureArtifactsNode:
    """Collect device and server diagnostics after a generated test fails."""

    def __init__(
        self,
        config: AndroidTestConfig,
        logcat_tool: LogcatTool | None = None,
        ui_dump_tool: UIDumpTool | None = None,
        screenshot_tool: ScreenshotTool | None = None,
        appium_tool: AppiumTool | None = None,
    ) -> None:
        self._config = config
        self._logcat_tool = logcat_tool or LogcatTool()
        self._ui_dump_tool = ui_dump_tool or UIDumpTool()
        self._screenshot_tool = screenshot_tool or ScreenshotTool()
        self._appium_tool = appium_tool or AppiumTool(config)

    def __call__(self, state: AgentState) -> AgentState:
        validation = state.get("validation_result", {})
        if validation.get("passed") is not False:
            return state

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        prefix = self._artifact_prefix(state, timestamp)
        artifacts = dict(state.get("artifacts", {}))
        collected: dict[str, Any] = {}

        self._collect_logcat(prefix, artifacts, collected)
        self._collect_ui_dump(prefix, artifacts, collected)
        self._collect_screenshot(prefix, artifacts, collected)
        self._collect_managed_appium_logs(state, artifacts, collected)
        self._collect_appium_status(prefix, artifacts, collected)

        execution_result = dict(state.get("execution_result", {}))
        execution_result["diagnostic_artifacts"] = {
            key: value for key, value in collected.items() if isinstance(value, str)
        }

        metadata = dict(state.get("metadata", {}))
        metadata["failure_artifacts"] = collected

        trace_path = self._write_trace(prefix, state, execution_result, validation, collected)
        artifacts["failure_trace"] = str(trace_path)
        collected["trace"] = str(trace_path)

        return {
            **state,
            "execution_result": execution_result,
            "artifacts": artifacts,
            "metadata": metadata,
        }

    def _artifact_prefix(self, state: AgentState, timestamp: str) -> str:
        generated_test_path = state.get("execution_result", {}).get("generated_test_path")
        if generated_test_path:
            name = Path(str(generated_test_path)).stem
        else:
            name = "generated_test"
        return f"{name}_{timestamp}"

    def _collect_logcat(self, prefix: str, artifacts: dict[str, str], collected: dict[str, Any]) -> None:
        path = self._config.artifacts_dir / "logcat" / f"{prefix}.txt"
        result = self._logcat_tool.run({"output_path": str(path), "lines": "1000"})
        if result.ok and result.data:
            artifacts["failure_logcat"] = str(result.data.get("path", path))
            collected["logcat"] = artifacts["failure_logcat"]
            return
        collected["logcat_error"] = result.error or result.output or "Logcat collection failed."

    def _collect_ui_dump(self, prefix: str, artifacts: dict[str, str], collected: dict[str, Any]) -> None:
        path = self._config.artifacts_dir / "ui_dumps" / f"{prefix}.xml"
        result = self._ui_dump_tool.run({"output_path": str(path), "timeout": 15})
        if result.ok and result.data:
            artifacts["failure_ui_dump"] = str(result.data.get("path", path))
            collected["ui_dump"] = artifacts["failure_ui_dump"]
            return
        collected["ui_dump_error"] = result.error or result.output or "UI dump collection failed."

    def _collect_screenshot(self, prefix: str, artifacts: dict[str, str], collected: dict[str, Any]) -> None:
        path = self._config.artifacts_dir / "screenshots" / f"{prefix}.png"
        result = self._screenshot_tool.run({"output_path": str(path), "timeout": 15})
        if result.ok and result.data:
            artifacts["failure_screenshot"] = str(result.data.get("path", path))
            collected["screenshot"] = artifacts["failure_screenshot"]
            return
        collected["screenshot_error"] = result.error or result.output or "Screenshot collection failed."

    def _collect_managed_appium_logs(
        self,
        state: AgentState,
        artifacts: dict[str, str],
        collected: dict[str, Any],
    ) -> None:
        appium_server = state.get("execution_result", {}).get("appium_server")
        if not isinstance(appium_server, dict):
            return

        log_path = appium_server.get("log_path")
        if log_path and Path(str(log_path)).exists():
            artifacts["failure_appium_log"] = str(log_path)
            collected["appium_log"] = str(log_path)

        process_output_path = appium_server.get("process_output_path")
        if process_output_path and Path(str(process_output_path)).exists():
            artifacts["failure_appium_process_log"] = str(process_output_path)
            collected["appium_process_log"] = str(process_output_path)

    def _collect_appium_status(self, prefix: str, artifacts: dict[str, str], collected: dict[str, Any]) -> None:
        path = self._config.artifacts_dir / "appium_logs" / f"{prefix}_status.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        result = self._appium_tool.run({})
        payload = {
            "ok": result.ok,
            "server_url": self._config.appium_server_url,
            "output": result.output,
            "error": result.error,
            "data": result.data,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts["failure_appium_status"] = str(path)
        collected["appium_status"] = str(path)
        if not result.ok:
            collected["appium_status_error"] = result.error or result.output or "Appium status check failed."

    def _write_trace(
        self,
        prefix: str,
        state: AgentState,
        execution_result: dict[str, Any],
        validation: dict[str, Any],
        collected: dict[str, Any],
    ) -> Path:
        path = self._config.artifacts_dir / "traces" / f"{prefix}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_files": state.get("generated_files", {}),
            "execution_result": execution_result,
            "validation_result": validation,
            "artifacts": collected,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
