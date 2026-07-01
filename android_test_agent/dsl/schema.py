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
    "long_press": {"requires_target": True, "target_fields": ["target"]},
    "swipe": {"target_fields": ["target"]},
    "scroll": {"target_fields": ["target"]},
    "drag_and_drop": {"target_fields": ["source", "target"]},
    "clear": {"requires_target": True, "target_fields": ["target"]},
    "press_key": {"required_fields": ["key"]},
    "hide_keyboard": {},
    "assert_checked": {"requires_target": True, "target_fields": ["target"]},
    "assert_enabled": {"requires_target": True, "target_fields": ["target"]},
    "assert_selected": {"requires_target": True, "target_fields": ["target"]},
    "assert_text_equals": {"requires_target": True, "target_fields": ["target"], "requires_text": True},
    "assert_text_contains": {"requires_target": True, "target_fields": ["target"], "requires_text": True},
    "wait_gone": {"requires_target": True, "target_fields": ["target"]},
    "assert_not_visible": {"requires_target": True, "target_fields": ["target"]},
    "tap_coordinates": {"required_fields": ["x", "y"]},
    "background_app": {},
    "activate_app": {},
    "terminate_app": {},
    "change_orientation": {"required_fields": ["orientation"]},
    "accept_permission": {},
    "dismiss_dialog": {},
    "pinch": {"target_fields": ["target"]},
    "zoom": {"target_fields": ["target"]},
    "w3c_actions": {"required_fields": ["actions"]},
}

ACTION_SPECS = supported_actions() or DEFAULT_ACTION_SPECS
SUPPORTED_ACTIONS = set(ACTION_SPECS)


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
        spec = ACTION_SPECS.get(action, {})
        for field in required_target_fields(str(action)):
            if not step.get(field):
                raise ValueError(f"Step {index} action '{action}' requires {field}")
        for field in spec.get("required_fields", []):
            if not _has_field(step, str(field)):
                raise ValueError(f"Step {index} action '{action}' requires {field}")
        if spec.get("requires_value") and "value" not in step:
            raise ValueError(f"Step {index} action '{action}' requires value")
        if spec.get("requires_text") and not step.get("text"):
            raise ValueError(f"Step {index} action '{action}' requires text")
        _validate_action_shape(index, str(action), step)


def validate_executable_dsl(dsl: dict[str, Any]) -> None:
    """Validate a DSL after all interactive targets have concrete locators."""

    validate_intent_dsl(dsl)
    for index, step in enumerate(dsl["steps"], start=1):
        action = str(step.get("action"))
        for field in action_target_fields(action):
            if not step.get(field):
                continue
            target = step.get(field)
            locator = target.get("locator") if isinstance(target, dict) else None
            if not isinstance(locator, dict):
                raise ValueError(f"Step {index} action '{action}' requires {field}.locator")
            if not locator.get("by") or not locator.get("value"):
                raise ValueError(f"Step {index} action '{action}' requires {field}.locator.by and locator.value")


def validate_test_dsl(dsl: dict[str, Any]) -> None:
    """Backward-compatible alias for validating intent-level DSL."""

    validate_intent_dsl(dsl)


def action_target_fields(action: str) -> list[str]:
    spec = ACTION_SPECS.get(action, {})
    fields = spec.get("target_fields")
    if isinstance(fields, list):
        return [str(field) for field in fields]
    if spec.get("requires_target"):
        return ["target"]
    return []


def required_target_fields(action: str) -> list[str]:
    spec = ACTION_SPECS.get(action, {})
    fields = spec.get("required_target_fields")
    if isinstance(fields, list):
        return [str(field) for field in fields]
    if spec.get("requires_target"):
        return ["target"]
    return []


TARGET_ACTIONS = {action for action in ACTION_SPECS if action_target_fields(action)}


def normalize_test_name(name: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "_" for char in name.strip())
    normalized = "_".join(part for part in normalized.split("_") if part)
    return normalized or "generated_test"


def _has_field(step: dict[str, Any], field: str) -> bool:
    return field in step and step[field] is not None


def _validate_action_shape(index: int, action: str, step: dict[str, Any]) -> None:
    if action in {"swipe", "scroll"}:
        if not step.get("direction") and not (_has_field(step, "start") and _has_field(step, "end")):
            raise ValueError(f"Step {index} action '{action}' requires direction or start/end")
    if action == "drag_and_drop":
        has_element_targets = bool(step.get("source") and step.get("target"))
        has_coordinates = _has_field(step, "start") and _has_field(step, "end")
        if not has_element_targets and not has_coordinates:
            raise ValueError(f"Step {index} action 'drag_and_drop' requires source/target or start/end")
    if action in {"pinch", "zoom"} and not step.get("target") and not step.get("area"):
        raise ValueError(f"Step {index} action '{action}' requires target or area")
