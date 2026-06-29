from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from android_test_agent.agent.capabilities import build_android_capabilities
from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.dsl.locator_resolver import LocatorResolutionError, LocatorResolver


class AppiumExecutor:
    """Small Appium wrapper used by DSLExecutor."""

    def __init__(self, config: AndroidTestConfig) -> None:
        self._config = config
        self._locator_resolver = LocatorResolver(config)
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

        action = step["action"]
        if action == "launch_app":
            self._launch_app()
            return
        if action == "tap":
            self._wait_for(step["target"], action).click()
            return
        if action == "input":
            element = self._wait_for(step["target"], action)
            element.clear()
            element.send_keys(str(step["value"]))
            return
        if action == "wait_visible":
            self._wait_for(step["target"], action)
            return
        if action == "assert_visible":
            assert self._wait_for(step["target"], action).is_displayed()
            return
        if action == "assert_text":
            self._wait_for_text(str(step["text"]))
            return
        if action == "back":
            self._driver.back()
            return
        raise ValueError(f"Unsupported action: {action}")

    def _wait_for(self, target: Any, action: str):
        from selenium.webdriver.support.ui import WebDriverWait

        if not self._driver:
            raise RuntimeError("Appium driver has not started")
        try:
            resolved_target = self._locator_resolver.resolve_target(
                target,
                page_source=self._driver.page_source,
                action=action,
            )
        except LocatorResolutionError as exc:
            self._write_locator_failure_artifacts(action, target, exc)
            raise

        attempts: list[dict[str, Any]] = []
        last_error: Exception | None = None
        for candidate_target in self._candidate_targets(resolved_target):
            by, value = self._resolve_locator(candidate_target)
            try:
                self._driver.implicitly_wait(0)
                try:
                    element = WebDriverWait(self._driver, self._config.explicit_wait_seconds).until(
                        lambda driver: self._find_matching_element(driver, by, value, candidate_target, action)
                    )
                finally:
                    self._driver.implicitly_wait(self._config.implicit_wait_seconds)
            except Exception as exc:
                last_error = exc
                attempts.append(
                    {
                        "locator": candidate_target.get("locator"),
                        "source": candidate_target.get("locator_source"),
                        "score": candidate_target.get("locator_score"),
                        "error": str(exc),
                    }
                )
                continue

            self._locator_resolver.remember(candidate_target, action=action, page_source=self._driver.page_source)
            return element

        error = last_error or LocatorResolutionError("No locator candidates were available")
        failure_target = {"target": target, "resolved_target": resolved_target, "attempts": attempts}
        self._write_locator_failure_artifacts(action, failure_target, error)
        raise error

    def _resolve_locator(self, target: Any) -> tuple[str, str]:
        from selenium.webdriver.common.by import By

        locator = target["locator"]
        by = locator["by"]
        value = locator["value"]

        mapping = {
            "id": By.ID,
            "android_uiautomator": "-android uiautomator",
            "accessibility_id": "accessibility id",
            "xpath": By.XPATH,
            "text": By.XPATH,
        }
        if by == "text":
            value = f"//*[@text={self._xpath_literal(value)}]"
        if by not in mapping:
            raise ValueError(f"Unsupported locator strategy: {by}")
        return mapping[by], value

    def _wait_for_text(self, text: str):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        if not self._driver:
            raise RuntimeError("Appium driver has not started")
        try:
            self._driver.implicitly_wait(0)
            try:
                return WebDriverWait(self._driver, self._config.explicit_wait_seconds).until(
                    lambda driver: self._find_visible_text(driver, By.XPATH, self._text_xpath(text))
                )
            finally:
                self._driver.implicitly_wait(self._config.implicit_wait_seconds)
        except Exception as exc:
            self._write_locator_failure_artifacts("assert_text", {"text": text}, exc)
            raise

    def _find_visible_text(self, driver: Any, by: str, value: str):
        elements = driver.find_elements(by, value)
        visible_elements = [element for element in elements if self._safe_is_displayed(element)]
        return visible_elements[0] if visible_elements else False

    def _find_matching_element(self, driver: Any, by: str, value: str, target: dict[str, Any], action: str):
        elements = driver.find_elements(by, value)
        visible_elements = [element for element in elements if self._safe_is_displayed(element)]
        if not visible_elements:
            return False
        if len(visible_elements) == 1:
            return visible_elements[0]
        return self._best_runtime_element(visible_elements, target, action) or visible_elements[0]

    def _best_runtime_element(self, elements: list[Any], target: dict[str, Any], action: str):
        metadata = target.get("locator_metadata") if isinstance(target, dict) else None
        if not isinstance(metadata, dict) or not metadata:
            return None

        scored = [
            (self._runtime_element_score(element, metadata, action), element)
            for element in elements
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1] if scored and scored[0][0] > 0 else None

    def _runtime_element_score(self, element: Any, metadata: dict[str, Any], action: str) -> float:
        score = 0.0
        expected_text = self._normalized(metadata.get("text"))
        expected_desc = self._normalized(metadata.get("content_desc"))
        expected_class = self._normalized(metadata.get("class"))
        expected_bounds = str(metadata.get("bounds") or "")

        actual_text = self._normalized(self._element_attribute(element, "text", "name"))
        actual_desc = self._normalized(
            self._element_attribute(element, "content-desc", "contentDescription", "name")
        )
        actual_class = self._normalized(self._element_attribute(element, "class", "className"))
        actual_bounds = str(self._element_attribute(element, "bounds") or "")

        if expected_text and actual_text == expected_text:
            score += 0.45
        elif expected_text and expected_text in actual_text:
            score += 0.25
        if expected_desc and actual_desc == expected_desc:
            score += 0.35
        if expected_class and actual_class == expected_class:
            score += 0.15
        if expected_bounds and actual_bounds == expected_bounds:
            score += 0.25
        if action == "tap" and self._truthy(self._element_attribute(element, "clickable")):
            score += 0.15
        if metadata.get("enabled") is True and self._truthy(self._element_attribute(element, "enabled")):
            score += 0.05
        return score

    def _element_attribute(self, element: Any, *names: str) -> str:
        for name in names:
            try:
                value = element.get_attribute(name)
            except Exception:
                value = None
            if value not in (None, ""):
                return str(value)
        text = getattr(element, "text", "")
        return str(text or "")

    def _safe_is_displayed(self, element: Any) -> bool:
        try:
            return bool(element.is_displayed())
        except Exception:
            return False

    def _truthy(self, value: Any) -> bool:
        return str(value).lower() in {"true", "1", "yes"}

    def _normalized(self, value: Any) -> str:
        return str(value or "").strip().lower()

    def _text_xpath(self, text: str) -> str:
        literal = self._xpath_literal(text)
        return f"//*[@text={literal} or @content-desc={literal}]"

    def _xpath_literal(self, value: Any) -> str:
        value = str(value)
        if "'" not in value:
            return "'" + value + "'"
        if '"' not in value:
            return '"' + value + '"'
        return "concat(" + ', "\'", '.join("'" + part + "'" for part in value.split("'")) + ")"

    def _candidate_targets(self, resolved_target: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add_candidate(locator: Any, candidate: dict[str, Any] | None = None) -> None:
            if not self._is_locator(locator):
                return
            key = (str(locator["by"]), str(locator["value"]))
            if key in seen:
                return
            seen.add(key)
            candidate_target = dict(resolved_target)
            candidate_target["locator"] = {"by": key[0], "value": key[1]}
            if candidate:
                candidate_target["locator_source"] = candidate.get("source", candidate_target.get("locator_source"))
                candidate_target["locator_score"] = candidate.get("score", candidate_target.get("locator_score"))
                candidate_target["locator_reason"] = candidate.get("reason", candidate_target.get("locator_reason"))
                if candidate.get("metadata"):
                    candidate_target["locator_metadata"] = candidate["metadata"]
            candidates.append(candidate_target)

        add_candidate(resolved_target.get("locator"))
        for candidate in resolved_target.get("locator_candidates", []):
            if isinstance(candidate, dict):
                add_candidate(candidate.get("locator"), candidate)

        return candidates

    def _is_locator(self, value: Any) -> bool:
        return isinstance(value, dict) and bool(value.get("by")) and bool(value.get("value"))

    def _write_locator_failure_artifacts(self, action: str, target: Any, error: Exception) -> None:
        if not self._driver:
            return
        output_dir = self._config.artifacts_dir / "locator_failures"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        prefix = output_dir / f"direct_dsl_{timestamp}"
        page_source = getattr(self._driver, "page_source", "")
        if page_source:
            prefix.with_suffix(".xml").write_text(page_source, encoding="utf-8")
        prefix.with_suffix(".json").write_text(
            json.dumps(
                {"action": action, "target": target, "error": str(error)},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        try:
            self._driver.save_screenshot(str(prefix.with_suffix(".png")))
        except Exception:
            pass

    def _launch_app(self) -> None:
        if not self._driver:
            raise RuntimeError("Appium driver has not started")
        capabilities = self._capabilities()
        app_package = capabilities.get("appium:appPackage")
        app_activity = capabilities.get("appium:appActivity")
        if not app_package:
            return
        if app_activity:
            component = app_activity if "/" in app_activity else f"{app_package}/{app_activity}"
            try:
                self._driver.execute_script(
                    "mobile: startActivity",
                    {"component": component, "stopApp": True},
                )
                return
            except Exception:
                pass
        self._driver.activate_app(app_package)

    def _capabilities(self) -> dict[str, Any]:
        return build_android_capabilities(self._config, absolutize_app=True)
