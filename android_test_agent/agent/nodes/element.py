from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
import time
from typing import Any
import xml.etree.ElementTree as ET

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.agent.state import AgentState
from android_test_agent.dsl.locator_resolver import LocatorResolutionError, LocatorResolver
from android_test_agent.dsl.schema import validate_intent_dsl
from android_test_agent.llm.base import LLMClient
from android_test_agent.tools.adb_tool import ADBTool
from android_test_agent.tools.screenshot_tool import ScreenshotTool
from android_test_agent.tools.ui_dump_tool import UIDumpTool

TARGET_ACTIONS = {"tap", "input", "wait_visible", "assert_visible"}


class ElementNode:
    """Resolve intent-level DSL targets with known element sources before codegen."""

    def __init__(
        self,
        config: AndroidTestConfig,
        llm: LLMClient | None = None,
        locator_resolver: LocatorResolver | None = None,
        ui_dump_tool: UIDumpTool | None = None,
        screenshot_tool: ScreenshotTool | None = None,
        adb_tool: ADBTool | None = None,
    ) -> None:
        self._config = config
        self._locator_resolver = locator_resolver or LocatorResolver(config, llm=llm)
        self._ui_dump_tool = ui_dump_tool or UIDumpTool()
        self._screenshot_tool = screenshot_tool or ScreenshotTool()
        self._adb = adb_tool or ADBTool()

    def __call__(self, state: AgentState) -> AgentState:
        intent_dsl = self._input_dsl(state)
        validate_intent_dsl(intent_dsl)

        collection = self._collect_element_sources()
        page_source = str(collection.get("page_source", ""))
        resolved_dsl, resolution = self._resolve_dsl(intent_dsl, page_source)
        resolution["collection"] = {
            key: value for key, value in collection.items() if key != "page_source"
        }

        artifacts = dict(state.get("artifacts", {}))
        if collection.get("ui_dump_path"):
            artifacts["element_node_ui_dump"] = str(collection["ui_dump_path"])
        if collection.get("screenshot_path"):
            artifacts["screenshot"] = str(collection["screenshot_path"])

        metadata = dict(state.get("metadata", {}))
        metadata["element_resolution"] = resolution

        return {
            **state,
            "intent_dsl": intent_dsl,
            "resolved_dsl": resolved_dsl,
            "dsl": resolved_dsl,
            "element_resolution": resolution,
            "artifacts": artifacts,
            "metadata": metadata,
        }

    def _input_dsl(self, state: AgentState) -> dict[str, Any]:
        if state.get("retry_count") and state.get("dsl"):
            return deepcopy(state["dsl"])
        return deepcopy(state["intent_dsl"])

    def _collect_element_sources(self) -> dict[str, Any]:
        if not self._config.execute_generated_tests:
            return {
                "page_source": "",
                "ui_dump_error": "UI dump skipped because execution is disabled.",
                "screenshot_error": "Screenshot skipped because execution is disabled.",
                "parallel_sources": ["manual_mapping", "element_memory"],
            }

        results: dict[str, Any] = {
            "parallel_sources": ["app_launch", "ui_dump", "screenshot", "manual_mapping", "element_memory"]
        }
        results.update(self._launch_configured_app())

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(self._collect_ui_dump): "ui_dump",
                executor.submit(self._collect_screenshot): "screenshot",
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    results.update(future.result())
                except Exception as exc:
                    results[f"{source}_error"] = str(exc)
            return results

    def _collect_ui_dump(self) -> dict[str, Any]:
        output_path = self._config.artifacts_dir / "ui_dumps" / "element_node_pre_execution.xml"
        result = self._ui_dump_tool.run({"output_path": str(output_path), "timeout": 10})
        if not result.ok:
            return {"page_source": "", "ui_dump_error": result.error or result.output or "UI dump failed."}

        path = Path(result.data.get("path", output_path) if result.data else output_path)
        if not path.exists():
            return {"page_source": "", "ui_dump_error": f"UI dump file does not exist: {path}"}
        page_source = path.read_text(encoding="utf-8")
        package_check = self._validate_dump_package(page_source)
        if package_check:
            return {
                "page_source": "",
                "ui_dump_path": str(path),
                **package_check,
            }
        return {"page_source": page_source, "ui_dump_path": str(path)}

    def _collect_screenshot(self) -> dict[str, Any]:
        output_path = self._config.artifacts_dir / "screenshots" / "element_node_pre_execution.png"
        result = self._screenshot_tool.run({"output_path": str(output_path), "timeout": 10})
        if not result.ok:
            return {"screenshot_error": result.error or result.output or "Screenshot failed."}
        path = Path(result.data.get("path", output_path) if result.data else output_path)
        if not path.exists():
            return {"screenshot_error": f"Screenshot file does not exist: {path}"}
        return {"screenshot_path": str(path)}

    def _launch_configured_app(self) -> dict[str, Any]:
        app_package = self._config.app_package
        app_activity = self._config.app_activity
        if not app_package:
            return {"app_launch_skipped": "ANDROID_APP_PACKAGE is not configured."}
        if not app_activity:
            return {"app_launch_skipped": "ANDROID_APP_ACTIVITY is not configured."}

        component = app_activity if "/" in app_activity else f"{app_package}/{app_activity}"
        result = self._adb.run({"args": ["shell", "am", "start", "-S", "-n", component], "timeout": 15})
        launch_result: dict[str, Any] = {"app_launch_component": component}
        if not result.ok:
            launch_result["app_launch_error"] = result.error or result.output or "ADB app launch failed."
            return launch_result

        # Give the launched activity a short window to draw before taking dump/screenshot.
        time.sleep(2)
        launch_result["app_launch_output"] = result.output.strip()
        return launch_result

    def _validate_dump_package(self, page_source: str) -> dict[str, Any]:
        expected_package = self._config.app_package
        if not expected_package:
            return {}

        packages = self._packages_in_page_source(page_source)
        if not packages or expected_package in packages:
            return {}
        return {
            "ui_dump_error": (
                "UI dump package mismatch; skipped pre-execution locator resolution. "
                f"Expected {expected_package}, found {', '.join(sorted(packages))}."
            ),
            "ui_dump_packages": sorted(packages),
        }

    def _packages_in_page_source(self, page_source: str) -> set[str]:
        if not page_source.strip():
            return set()
        try:
            root = ET.fromstring(page_source)
        except ET.ParseError:
            return set()
        packages: set[str] = set()
        for node in root.iter():
            package_name = node.attrib.get("package")
            if package_name:
                packages.add(package_name)
        return packages

    def _resolve_dsl(self, dsl: dict[str, Any], page_source: str) -> tuple[dict[str, Any], dict[str, Any]]:
        resolved = deepcopy(dsl)
        stats: dict[str, Any] = {
            "resolved_targets": 0,
            "unresolved_targets": 0,
            "targets": [],
        }

        target_steps = [
            (index, step)
            for index, step in enumerate(resolved.get("steps", []), start=1)
            if step.get("action") in TARGET_ACTIONS and step.get("target")
        ]
        if not target_steps:
            return resolved, stats

        max_workers = min(4, len(target_steps))
        results: dict[int, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._resolve_step_target, index, step, page_source): index
                for index, step in target_steps
            }
            for future in as_completed(futures):
                index = futures[future]
                results[index] = future.result()

        for index, step in target_steps:
            result = results[index]
            if not result["resolved"]:
                stats["unresolved_targets"] += 1
                stats["targets"].append(result["stats"])
                continue
            step["target"] = result["target"]
            stats["resolved_targets"] += 1
            stats["targets"].append(result["stats"])
            if result["target"].get("locator_source") == "ui_hierarchy":
                self._locator_resolver.remember(result["target"], action=step.get("action"), page_source=page_source)

        return resolved, stats

    def _resolve_step_target(self, index: int, step: dict[str, Any], page_source: str) -> dict[str, Any]:
        action = step.get("action")
        target = step.get("target")
        try:
            resolved_target = self._locator_resolver.resolve_target(
                target,
                page_source=page_source,
                action=action,
            )
        except LocatorResolutionError as exc:
            return {
                "resolved": False,
                "stats": {
                    "step": index,
                    "action": action,
                    "target": target,
                    "resolved": False,
                    "reason": str(exc),
                },
            }

        return {
            "resolved": True,
            "target": resolved_target,
            "stats": {
                "step": index,
                "action": action,
                "target": self._target_name(resolved_target),
                "resolved": True,
                "source": resolved_target.get("locator_source"),
                "score": resolved_target.get("locator_score"),
                "locator": resolved_target.get("locator"),
                "candidate_count": len(resolved_target.get("locator_candidates", [])),
            },
        }

    def _target_name(self, target: dict[str, Any]) -> str:
        return str(target.get("name") or target.get("intent") or target.get("locator", {}).get("value") or "target")
