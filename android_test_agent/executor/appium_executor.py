from __future__ import annotations

from typing import Any

from android_test_agent.agent.capabilities import build_android_capabilities
from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.dsl.action_runtime import AndroidDslActionRuntime
from android_test_agent.dsl.locator_resolver import LocatorResolver


class AppiumExecutor:
    """Small Appium wrapper used by DSLExecutor."""

    def __init__(self, config: AndroidTestConfig) -> None:
        self._config = config
        self._locator_resolver = LocatorResolver(config)
        self._runtime = AndroidDslActionRuntime(
            config,
            locator_resolver=self._locator_resolver,
            failure_prefix="direct_dsl",
        )
        self._driver: Any | None = None

    def start(self) -> None:
        from appium import webdriver
        from appium.options.android import UiAutomator2Options

        options = UiAutomator2Options().load_capabilities(self._capabilities())
        self._driver = webdriver.Remote(self._config.appium_server_url, options=options)
        self._driver.implicitly_wait(self._config.implicit_wait_seconds)

    def stop(self) -> None:
        if self._driver:
            self._driver.quit()
            self._driver = None

    def run_step(self, step: dict[str, Any]) -> None:
        if not self._driver:
            raise RuntimeError("Appium driver has not started")

        self._runtime.run_step(self._driver, step)

    def _capabilities(self) -> dict[str, Any]:
        return build_android_capabilities(self._config, absolutize_app=True)
