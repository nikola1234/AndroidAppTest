from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from android_test_agent.agent.capabilities import build_android_capabilities
from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.dsl.locator_resolver import LocatorResolutionError, LocatorResolver


KEY_CODES: dict[str, int] = {
    "UNKNOWN": 0,
    "BACK": 4,
    "HOME": 3,
    "MENU": 82,
    "ENTER": 66,
    "TAB": 61,
    "SPACE": 62,
    "DEL": 67,
    "DELETE": 67,
    "ESCAPE": 111,
    "SEARCH": 84,
    "DPAD_UP": 19,
    "DPAD_DOWN": 20,
    "DPAD_LEFT": 21,
    "DPAD_RIGHT": 22,
    "DPAD_CENTER": 23,
}


class AndroidDslActionRuntime:
    """Execute Android test DSL steps against an Appium driver."""

    def __init__(
        self,
        config: AndroidTestConfig,
        *,
        locator_resolver: LocatorResolver | None = None,
        artifacts_dir: Path | None = None,
        failure_prefix: str = "dsl",
        remember_runtime_locators: bool = True,
    ) -> None:
        self._config = config
        self._locator_resolver = locator_resolver or LocatorResolver(config)
        self._artifacts_dir = artifacts_dir or config.artifacts_dir
        self._failure_prefix = failure_prefix
        self._remember_runtime_locators = remember_runtime_locators

    def run_step(self, driver: Any, step: dict[str, Any]) -> None:
        action = step["action"]

        if action == "launch_app":
            self.launch_app(driver)
            return
        if action == "tap":
            self.wait_for(driver, step["target"], action).click()
            return
        if action == "input":
            element = self.wait_for(driver, step["target"], action)
            element.clear()
            element.send_keys(str(step["value"]))
            return
        if action == "wait_visible":
            self.wait_for(driver, step["target"], action)
            return
        if action == "assert_visible":
            assert self.wait_for(driver, step["target"], action).is_displayed()
            return
        if action == "assert_text":
            self.wait_for_text(driver, str(step["text"]))
            return
        if action == "scroll_to_text":
            self.scroll_to_text(driver, str(step["text"]))
            return
        if action == "back":
            driver.back()
            return
        if action == "long_press":
            self.long_press(driver, step)
            return
        if action == "swipe":
            self.swipe(driver, step)
            return
        if action == "scroll":
            self.scroll(driver, step)
            return
        if action == "drag_and_drop":
            self.drag_and_drop(driver, step)
            return
        if action == "clear":
            self.wait_for(driver, step["target"], action).clear()
            return
        if action == "press_key":
            self.press_key(driver, step["key"])
            return
        if action == "hide_keyboard":
            self.hide_keyboard(driver)
            return
        if action in {"assert_checked", "assert_enabled", "assert_selected"}:
            self.assert_element_state(driver, step, action)
            return
        if action in {"assert_text_equals", "assert_text_contains"}:
            self.assert_element_text(driver, step, action)
            return
        if action in {"wait_gone", "assert_not_visible"}:
            self.wait_for_absent(driver, step["target"], action)
            return
        if action == "tap_coordinates":
            self.tap_coordinates(driver, step)
            return
        if action == "background_app":
            self.background_app(driver, step)
            return
        if action == "activate_app":
            driver.activate_app(self.app_package(step))
            return
        if action == "terminate_app":
            driver.terminate_app(self.app_package(step))
            return
        if action == "change_orientation":
            driver.orientation = str(step["orientation"]).upper()
            return
        if action == "accept_permission":
            self.accept_permission(driver)
            return
        if action == "dismiss_dialog":
            self.dismiss_dialog(driver)
            return
        if action in {"pinch", "zoom"}:
            self.pinch_or_zoom(driver, step, action)
            return
        if action == "w3c_actions":
            self.perform_w3c_actions(driver, step["actions"])
            return

        raise ValueError(f"Unsupported action: {action}")

    def wait_for(self, driver: Any, target: Any, action: str):
        try:
            resolved_target = self._locator_resolver.resolve_target(
                target,
                page_source=driver.page_source,
                action=action,
            )
        except LocatorResolutionError as exc:
            self.write_locator_failure_artifacts(driver, action, target, exc)
            raise

        attempts: list[dict[str, Any]] = []
        last_error: Exception | None = None
        for candidate_target in self.candidate_targets(resolved_target):
            by, value = self.appium_locator(candidate_target["locator"])
            try:
                driver.implicitly_wait(0)
                try:
                    element = WebDriverWait(driver, self._config.explicit_wait_seconds).until(
                        lambda current_driver: self.find_matching_element(
                            current_driver,
                            by,
                            value,
                            candidate_target,
                            action,
                        )
                    )
                finally:
                    driver.implicitly_wait(self._config.implicit_wait_seconds)
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

            if self._remember_runtime_locators:
                self._locator_resolver.remember(candidate_target, action=action, page_source=driver.page_source)
            return element

        error = last_error or LocatorResolutionError("No locator candidates were available")
        failure_target = {"target": target, "resolved_target": resolved_target, "attempts": attempts}
        self.write_locator_failure_artifacts(driver, action, failure_target, error)
        raise error

    def wait_for_absent(self, driver: Any, target: Any, action: str) -> None:
        try:
            resolved_target = self._locator_resolver.resolve_target(
                target,
                page_source=driver.page_source,
                action=action,
            )
        except LocatorResolutionError:
            return

        candidates = self.candidate_targets(resolved_target)
        if not candidates:
            return

        try:
            driver.implicitly_wait(0)
            try:
                WebDriverWait(driver, self._config.explicit_wait_seconds).until(
                    lambda current_driver: not self._any_visible_candidate(current_driver, candidates)
                )
            finally:
                driver.implicitly_wait(self._config.implicit_wait_seconds)
        except Exception as exc:
            self.write_locator_failure_artifacts(driver, action, target, exc)
            raise

    def _any_visible_candidate(self, driver: Any, candidates: list[dict[str, Any]]) -> bool:
        for candidate in candidates:
            by, value = self.appium_locator(candidate["locator"])
            if any(self.safe_is_displayed(element) for element in driver.find_elements(by, value)):
                return True
        return False

    def appium_locator(self, locator: dict[str, Any]) -> tuple[str, str]:
        by = locator["by"]
        value = locator["value"]
        mapping = {
            "id": By.ID,
            "android_uiautomator": "-android uiautomator",
            "accessibility_id": "accessibility id",
            "xpath": By.XPATH,
            "text": By.XPATH,
        }
        if by not in mapping:
            raise ValueError(f"Unsupported locator strategy: {by}")
        if by == "text":
            value = f"//*[@text={self.xpath_literal(value)}]"
        return mapping[by], value

    def candidate_targets(self, resolved_target: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add_candidate(locator: Any, candidate: dict[str, Any] | None = None) -> None:
            if not isinstance(locator, dict) or not locator.get("by") or not locator.get("value"):
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

    def find_matching_element(self, driver: Any, by: str, value: str, target: dict[str, Any], action: str):
        elements = driver.find_elements(by, value)
        visible_elements = [element for element in elements if self.safe_is_displayed(element)]
        if not visible_elements:
            return False
        if len(visible_elements) == 1:
            return visible_elements[0]
        return self.best_runtime_element(visible_elements, target, action) or visible_elements[0]

    def best_runtime_element(self, elements: list[Any], target: dict[str, Any], action: str):
        metadata = target.get("locator_metadata") if isinstance(target, dict) else None
        if not isinstance(metadata, dict) or not metadata:
            return None
        scored = [(self.runtime_element_score(element, metadata, action), element) for element in elements]
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1] if scored and scored[0][0] > 0 else None

    def runtime_element_score(self, element: Any, metadata: dict[str, Any], action: str) -> float:
        score = 0.0
        expected_text = self.normalized(metadata.get("text"))
        expected_desc = self.normalized(metadata.get("content_desc"))
        expected_class = self.normalized(metadata.get("class"))
        expected_bounds = str(metadata.get("bounds") or "")

        actual_text = self.normalized(self.element_attribute(element, "text", "name"))
        actual_desc = self.normalized(self.element_attribute(element, "content-desc", "contentDescription", "name"))
        actual_class = self.normalized(self.element_attribute(element, "class", "className"))
        actual_bounds = str(self.element_attribute(element, "bounds") or "")

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
        if action in {"tap", "long_press", "drag_and_drop"} and self.truthy(
            self.element_attribute(element, "clickable")
        ):
            score += 0.15
        if metadata.get("enabled") is True and self.truthy(self.element_attribute(element, "enabled")):
            score += 0.05
        return score

    def wait_for_text(self, driver: Any, text: str):
        try:
            driver.implicitly_wait(0)
            try:
                return WebDriverWait(driver, self._config.explicit_wait_seconds).until(
                    lambda current_driver: self.find_visible_text(current_driver, text)
                )
            finally:
                driver.implicitly_wait(self._config.implicit_wait_seconds)
        except Exception as exc:
            self.write_locator_failure_artifacts(driver, "assert_text", {"text": text}, exc)
            raise

    def find_visible_text(self, driver: Any, text: str):
        literal = self.xpath_literal(text)
        elements = driver.find_elements(By.XPATH, f"//*[@text={literal} or @content-desc={literal}]")
        visible_elements = [element for element in elements if self.safe_is_displayed(element)]
        return visible_elements[0] if visible_elements else False

    def scroll_to_text(self, driver: Any, text: str):
        selector = (
            "new UiScrollable(new UiSelector().scrollable(true))"
            f".scrollIntoView(new UiSelector().text({self.uiselector_literal(text)}))"
        )
        try:
            driver.implicitly_wait(0)
            try:
                driver.find_element("-android uiautomator", selector)
                return self.wait_for_text(driver, text)
            finally:
                driver.implicitly_wait(self._config.implicit_wait_seconds)
        except Exception as exc:
            self.write_locator_failure_artifacts(driver, "scroll_to_text", {"text": text}, exc)
            raise

    def long_press(self, driver: Any, step: dict[str, Any]) -> None:
        element = self.wait_for(driver, step["target"], "long_press")
        args = {"elementId": element.id, "duration": int(step.get("duration_ms", step.get("duration", 1000)))}
        driver.execute_script("mobile: longClickGesture", args)

    def swipe(self, driver: Any, step: dict[str, Any]) -> None:
        if step.get("start") is not None and step.get("end") is not None:
            self.perform_pointer_path(driver, step["start"], step["end"], step.get("duration_ms", 500))
            return
        args = self.gesture_area_args(driver, step, "swipe")
        args["direction"] = self.direction(step)
        args["percent"] = float(step.get("percent", 0.75))
        if step.get("speed") is not None:
            args["speed"] = int(step["speed"])
        driver.execute_script("mobile: swipeGesture", args)

    def scroll(self, driver: Any, step: dict[str, Any]) -> None:
        if step.get("start") is not None and step.get("end") is not None:
            self.perform_pointer_path(driver, step["start"], step["end"], step.get("duration_ms", 500))
            return
        args = self.gesture_area_args(driver, step, "scroll")
        args["direction"] = self.direction(step)
        args["percent"] = float(step.get("percent", 0.75))
        if step.get("speed") is not None:
            args["speed"] = int(step["speed"])
        driver.execute_script("mobile: scrollGesture", args)

    def drag_and_drop(self, driver: Any, step: dict[str, Any]) -> None:
        if step.get("start") is not None and step.get("end") is not None:
            self.perform_pointer_path(driver, step["start"], step["end"], step.get("duration_ms", 700))
            return

        source = self.wait_for(driver, step["source"], "drag_and_drop")
        target = self.wait_for(driver, step["target"], "drag_and_drop")
        target_center = self.center_of_rect(target.rect)
        args = {
            "elementId": source.id,
            "endX": target_center["x"],
            "endY": target_center["y"],
        }
        if step.get("duration_ms") is not None:
            args["duration"] = int(step["duration_ms"])
        driver.execute_script("mobile: dragGesture", args)

    def assert_element_state(self, driver: Any, step: dict[str, Any], action: str) -> None:
        element = self.wait_for(driver, step["target"], action)
        if action == "assert_enabled":
            assert element.is_enabled()
            return
        attribute = "checked" if action == "assert_checked" else "selected"
        assert self.truthy(self.element_attribute(element, attribute))

    def assert_element_text(self, driver: Any, step: dict[str, Any], action: str) -> None:
        element = self.wait_for(driver, step["target"], action)
        expected = str(step["text"])
        actual = self.element_text(element)
        if action == "assert_text_equals":
            assert actual == expected
            return
        assert expected in actual

    def tap_coordinates(self, driver: Any, step: dict[str, Any]) -> None:
        driver.execute_script("mobile: clickGesture", {"x": int(step["x"]), "y": int(step["y"])})

    def press_key(self, driver: Any, key: Any) -> None:
        keycode = self.key_code(key)
        if hasattr(driver, "press_keycode"):
            driver.press_keycode(keycode)
            return
        driver.execute_script("mobile: pressKey", {"keycode": keycode})

    def hide_keyboard(self, driver: Any) -> None:
        try:
            driver.hide_keyboard()
        except Exception:
            return

    def background_app(self, driver: Any, step: dict[str, Any]) -> None:
        seconds = step.get("seconds", step.get("duration"))
        if seconds is None:
            driver.background_app(1)
            return
        driver.background_app(int(seconds))

    def accept_permission(self, driver: Any) -> None:
        if self._handle_alert(driver, accept=True):
            return
        self._tap_first_text(driver, ["Allow", "ALLOW", "允许", "始终允许", "仅在使用中允许", "OK", "确定"])

    def dismiss_dialog(self, driver: Any) -> None:
        if self._handle_alert(driver, accept=False):
            return
        self._tap_first_text(driver, ["Cancel", "CANCEL", "取消", "No", "NO", "否", "Dismiss", "关闭"])

    def pinch_or_zoom(self, driver: Any, step: dict[str, Any], action: str) -> None:
        args = self.gesture_area_args(driver, step, action)
        args["percent"] = float(step.get("percent", 0.5))
        if step.get("speed") is not None:
            args["speed"] = int(step["speed"])
        script = "mobile: pinchCloseGesture" if action == "pinch" else "mobile: pinchOpenGesture"
        driver.execute_script(script, args)

    def perform_pointer_path(self, driver: Any, start: Any, end: Any, duration_ms: Any = 500) -> None:
        start_point = self.point(start)
        end_point = self.point(end)
        actions = [
            {
                "type": "pointer",
                "id": "finger1",
                "parameters": {"pointerType": "touch"},
                "actions": [
                    {"type": "pointerMove", "duration": 0, "x": start_point["x"], "y": start_point["y"]},
                    {"type": "pointerDown", "button": 0},
                    {"type": "pause", "duration": int(duration_ms) // 5},
                    {"type": "pointerMove", "duration": int(duration_ms), "x": end_point["x"], "y": end_point["y"]},
                    {"type": "pointerUp", "button": 0},
                ],
            }
        ]
        self.perform_w3c_actions(driver, actions)

    def perform_w3c_actions(self, driver: Any, actions: Any) -> None:
        if hasattr(driver, "perform_actions"):
            driver.perform_actions(actions)
        else:
            driver.execute("actions", {"actions": actions})
        if hasattr(driver, "release_actions"):
            driver.release_actions()

    def gesture_area_args(self, driver: Any, step: dict[str, Any], action: str) -> dict[str, int]:
        if isinstance(step.get("area"), dict):
            rect = self.rect_from_area(step["area"])
        elif step.get("target"):
            element = self.wait_for(driver, step["target"], action)
            rect = self.rect_from_area(element.rect)
        else:
            rect = self.viewport_rect(driver)
        return {
            "left": int(rect["x"]),
            "top": int(rect["y"]),
            "width": int(rect["width"]),
            "height": int(rect["height"]),
        }

    def direction(self, step: dict[str, Any]) -> str:
        direction = str(step.get("direction", "")).lower()
        if direction not in {"up", "down", "left", "right"}:
            raise ValueError(f"Unsupported direction: {direction}")
        return direction

    def viewport_rect(self, driver: Any) -> dict[str, int]:
        if hasattr(driver, "get_window_rect"):
            rect = driver.get_window_rect()
            return self.rect_from_area(rect)
        size = driver.get_window_size()
        return {"x": 0, "y": 0, "width": int(size["width"]), "height": int(size["height"])}

    def rect_from_area(self, area: dict[str, Any]) -> dict[str, int]:
        x = area.get("x", area.get("left", 0))
        y = area.get("y", area.get("top", 0))
        width = area.get("width")
        height = area.get("height")
        if width is None and area.get("right") is not None:
            width = int(area["right"]) - int(x)
        if height is None and area.get("bottom") is not None:
            height = int(area["bottom"]) - int(y)
        if width is None or height is None:
            raise ValueError(f"Gesture area requires width and height: {area}")
        return {"x": int(x), "y": int(y), "width": int(width), "height": int(height)}

    def center_of_rect(self, rect: dict[str, Any]) -> dict[str, int]:
        normalized = self.rect_from_area(rect)
        return {
            "x": normalized["x"] + normalized["width"] // 2,
            "y": normalized["y"] + normalized["height"] // 2,
        }

    def point(self, value: Any) -> dict[str, int]:
        if isinstance(value, dict):
            return {"x": int(value["x"]), "y": int(value["y"])}
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return {"x": int(value[0]), "y": int(value[1])}
        raise ValueError(f"Point requires x/y values: {value}")

    def app_package(self, step: dict[str, Any]) -> str:
        app_package = step.get("app_package") or self._capabilities().get("appium:appPackage")
        if not app_package:
            raise ValueError("App package is required for this action")
        return str(app_package)

    def launch_app(self, driver: Any) -> None:
        capabilities = self._capabilities()
        app_package = capabilities.get("appium:appPackage")
        app_activity = capabilities.get("appium:appActivity")
        if not app_package:
            return
        if app_activity:
            component = app_activity if "/" in app_activity else f"{app_package}/{app_activity}"
            try:
                driver.execute_script("mobile: startActivity", {"component": component, "stopApp": True})
                return
            except Exception:
                pass
        driver.activate_app(app_package)

    def _capabilities(self) -> dict[str, Any]:
        return build_android_capabilities(self._config, absolutize_app=True)

    def _handle_alert(self, driver: Any, *, accept: bool) -> bool:
        try:
            alert = driver.switch_to.alert
            if accept:
                alert.accept()
            else:
                alert.dismiss()
            return True
        except Exception:
            return False

    def _tap_first_text(self, driver: Any, texts: list[str]) -> bool:
        for text in texts:
            literal = self.xpath_literal(text)
            elements = driver.find_elements(By.XPATH, f"//*[@text={literal} or @content-desc={literal}]")
            for element in elements:
                if self.safe_is_displayed(element):
                    element.click()
                    return True
        return False

    def write_locator_failure_artifacts(self, driver: Any, action: str, target: Any, error: Exception) -> None:
        output_dir = self._artifacts_dir / "locator_failures"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        prefix = output_dir / f"{self._failure_prefix}_{timestamp}"
        page_source = getattr(driver, "page_source", "")
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
            driver.save_screenshot(str(prefix.with_suffix(".png")))
        except Exception:
            pass

    def element_attribute(self, element: Any, *names: str) -> str:
        for name in names:
            try:
                value = element.get_attribute(name)
            except Exception:
                value = None
            if value not in (None, ""):
                return str(value)
        return str(getattr(element, "text", "") or "")

    def element_text(self, element: Any) -> str:
        return self.element_attribute(element, "text", "name")

    def safe_is_displayed(self, element: Any) -> bool:
        try:
            return bool(element.is_displayed())
        except Exception:
            return False

    def truthy(self, value: Any) -> bool:
        return str(value).lower() in {"true", "1", "yes"}

    def normalized(self, value: Any) -> str:
        return str(value or "").strip().lower()

    def xpath_literal(self, value: Any) -> str:
        value = str(value)
        if "'" not in value:
            return "'" + value + "'"
        if '"' not in value:
            return '"' + value + '"'
        separator = ', ' + '"' + "'" + '"' + ', '
        return "concat(" + separator.join("'" + part + "'" for part in value.split("'")) + ")"

    def uiselector_literal(self, value: Any) -> str:
        value = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{value}"'

    def key_code(self, key: Any) -> int:
        if isinstance(key, int):
            return key
        value = str(key).strip()
        if value.isdigit():
            return int(value)
        normalized = value.upper().replace("KEYCODE_", "")
        if normalized not in KEY_CODES:
            raise ValueError(f"Unsupported Android key: {key}")
        return KEY_CODES[normalized]
