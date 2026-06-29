from __future__ import annotations

from typing import Any

from android_test_agent.agent.runtime_resources import supported_actions

DEFAULT_ACTION_SPECS: dict[str, dict[str, Any]] = {
    "launch_app": {"requires_target": False, "requires_value": False, "requires_text": False},
    "tap": {"requires_target": True, "requires_value": False, "requires_text": False},
    "input": {"requires_target": True, "requires_value": True, "requires_text": False},
    "wait_visible": {"requires_target": True, "requires_value": False, "requires_text": False},
    "assert_visible": {"requires_target": True, "requires_value": False, "requires_text": False},
    "assert_text": {"requires_target": False, "requires_value": False, "requires_text": True},
    "scroll_to_text": {"requires_target": False, "requires_value": False, "requires_text": True},
    "back": {"requires_target": False, "requires_value": False, "requires_text": False},
}

ACTION_SPECS = supported_actions() or DEFAULT_ACTION_SPECS
SUPPORTED_ACTIONS = set(ACTION_SPECS)

TARGET_ACTIONS = {
    action
    for action, spec in ACTION_SPECS.items()
    if isinstance(spec, dict) and spec.get("requires_target")
}


def validate_intent_dsl(dsl: dict[str, Any]) -> None:
    """Validate an intent-level DSL before runtime locator resolution."""

    if not isinstance(dsl.get("name"), str) or not dsl["name"].strip():
        raise ValueError("DSL requires a non-empty string field: name")

    steps = dsl.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("DSL requires a non-empty list field: steps")

    for index, step in enumerate(steps, start=1):
        action = step.get("action")
        if action not in SUPPORTED_ACTIONS:
            raise ValueError(f"Unsupported action at step {index}: {action}")
        if action in TARGET_ACTIONS and not step.get("target"):
            raise ValueError(f"Step {index} action '{action}' requires target")
        spec = ACTION_SPECS.get(action, {})
        if spec.get("requires_value") and "value" not in step:
            raise ValueError(f"Step {index} action 'input' requires value")
        if spec.get("requires_text") and not step.get("text"):
            raise ValueError(f"Step {index} action '{action}' requires text")


def validate_executable_dsl(dsl: dict[str, Any]) -> None:
    """Validate a DSL after all interactive targets have concrete locators."""

    validate_intent_dsl(dsl)
    for index, step in enumerate(dsl["steps"], start=1):
        if step.get("action") not in TARGET_ACTIONS:
            continue
        target = step.get("target")
        locator = target.get("locator") if isinstance(target, dict) else None
        if not isinstance(locator, dict):
            raise ValueError(f"Step {index} action '{step['action']}' requires target.locator")
        if not locator.get("by") or not locator.get("value"):
            raise ValueError(f"Step {index} action '{step['action']}' requires locator.by and locator.value")


def validate_test_dsl(dsl: dict[str, Any]) -> None:
    """Backward-compatible alias for validating intent-level DSL."""

    validate_intent_dsl(dsl)


def normalize_test_name(name: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "_" for char in name.strip())
    normalized = "_".join(part for part in normalized.split("_") if part)
    return normalized or "generated_test"
