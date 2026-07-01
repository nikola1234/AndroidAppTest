from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
from urllib.parse import urlparse

import requests

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
        self._appium_server = AppiumServerManager(config)

    def run(self, test_path: str) -> ExecutionResult:
        if not self._config.execute_generated_tests:
            return {
                "status": "dry_run",
                "generated_test_path": test_path,
                "stdout": "Generated test code successfully. Execution is disabled.",
                "stderr": "",
            }

        appium_server = self._appium_server.ensure_ready()
        if not appium_server.get("ready"):
            self._appium_server.stop()
            return {
                "status": "failed",
                "stdout": "",
                "stderr": str(appium_server.get("error") or "Appium server is not ready."),
                "generated_test_path": test_path,
                "appium_server": appium_server,
            }

        command = [sys.executable, "-m", "pytest", test_path, "-q"]
        try:
            completed = subprocess.run(
                command,
                cwd=self._config.project_root,
                text=True,
                capture_output=True,
                timeout=600,
            )
            appium_server["status_before_cleanup"] = self._appium_server.status()
            return {
                "status": "passed" if completed.returncode == 0 else "failed",
                "command": command,
                "return_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "generated_test_path": test_path,
                "appium_server": appium_server,
            }
        finally:
            self._appium_server.stop()


class AppiumServerManager:
    """Ensure Appium is available for generated pytest execution."""

    def __init__(self, config: AndroidTestConfig) -> None:
        self._config = config
        self._process: subprocess.Popen[str] | None = None
        self._process_output_file: Any | None = None

    def ensure_ready(self) -> dict[str, Any]:
        status = self.status()
        if status.get("ready"):
            return {
                "ready": True,
                "managed": False,
                "server_url": self._config.appium_server_url,
                "status": status,
            }

        return self._start_managed_appium()

    def status(self) -> dict[str, Any]:
        url = self._config.appium_server_url.rstrip("/")
        try:
            response = requests.get(f"{url}/status", timeout=3)
            response.raise_for_status()
        except requests.RequestException as exc:
            return {"ready": False, "error": str(exc)}
        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text}
        return {"ready": True, "data": data}

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        self._process = None
        if self._process_output_file:
            self._process_output_file.close()
            self._process_output_file = None

    def _start_managed_appium(self) -> dict[str, Any]:
        host, port = self._host_and_port()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        log_dir = self._config.artifacts_dir / "appium_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        appium_log_path = log_dir / f"appium_{timestamp}.log"
        process_output_path = log_dir / f"appium_{timestamp}_process.log"
        command = [
            "appium",
            "--address",
            host,
            "--port",
            str(port),
            "--log",
            str(appium_log_path),
            "--log-level",
            "debug",
        ]

        try:
            self._process_output_file = process_output_path.open("w", encoding="utf-8")
            self._process = subprocess.Popen(
                command,
                cwd=self._config.project_root,
                stdout=self._process_output_file,
                stderr=subprocess.STDOUT,
                text=True,
                env=os.environ.copy(),
            )
        except FileNotFoundError:
            self._close_process_output_file()
            return {
                "ready": False,
                "managed": True,
                "server_url": self._config.appium_server_url,
                "command": command,
                "log_path": str(appium_log_path),
                "process_output_path": str(process_output_path),
                "error": "appium executable was not found in PATH.",
            }
        except OSError as exc:
            self._close_process_output_file()
            return {
                "ready": False,
                "managed": True,
                "server_url": self._config.appium_server_url,
                "command": command,
                "log_path": str(appium_log_path),
                "process_output_path": str(process_output_path),
                "error": str(exc),
            }

        for _ in range(30):
            if self._process.poll() is not None:
                self.stop()
                return {
                    "ready": False,
                    "managed": True,
                    "server_url": self._config.appium_server_url,
                    "command": command,
                    "log_path": str(appium_log_path),
                    "process_output_path": str(process_output_path),
                    "error": "Managed Appium process exited before becoming ready.",
                }
            status = self.status()
            if status.get("ready"):
                return {
                    "ready": True,
                    "managed": True,
                    "server_url": self._config.appium_server_url,
                    "command": command,
                    "log_path": str(appium_log_path),
                    "process_output_path": str(process_output_path),
                    "status": status,
                }
            time.sleep(1)

        self.stop()
        return {
            "ready": False,
            "managed": True,
            "server_url": self._config.appium_server_url,
            "command": command,
            "log_path": str(appium_log_path),
            "process_output_path": str(process_output_path),
            "error": "Timed out waiting for managed Appium server to become ready.",
        }

    def _host_and_port(self) -> tuple[str, int]:
        parsed = urlparse(self._config.appium_server_url)
        return parsed.hostname or "127.0.0.1", parsed.port or 4723

    def _close_process_output_file(self) -> None:
        if self._process_output_file:
            self._process_output_file.close()
            self._process_output_file = None
