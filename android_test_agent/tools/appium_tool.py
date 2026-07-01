from __future__ import annotations

from typing import Any

import requests

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.tools.base import ToolResult


class AppiumTool:
    name = "appium"
    description = "Check Appium server readiness."

    def __init__(self, config: AndroidTestConfig) -> None:
        self._config = config

    def run(self, input_data: dict[str, Any]) -> ToolResult:
        url = input_data.get("server_url", self._config.appium_server_url).rstrip("/")
        try:
            response = requests.get(f"{url}/status", timeout=5)
            response.raise_for_status()
        except requests.RequestException as exc:
            return ToolResult(ok=False, error=str(exc))
        return ToolResult(ok=True, output=response.text, data=response.json())
