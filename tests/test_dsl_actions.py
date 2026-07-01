from __future__ import annotations

import pytest

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.dsl.codegen import PytestAppiumCodeGenerator
from android_test_agent.dsl.schema import action_target_fields, validate_intent_dsl


def test_validate_extended_actions() -> None:
    dsl = {
        "name": "extended actions",
        "steps": [
            {"action": "launch_app"},
            {"action": "long_press", "target": {"name": "item", "intent": "list item"}},
            {"action": "swipe", "direction": "up", "percent": 0.75},
            {"action": "scroll", "target": {"name": "list", "intent": "list"}, "direction": "down"},
            {
                "action": "drag_and_drop",
                "source": {"name": "source", "intent": "source item"},
                "target": {"name": "destination", "intent": "destination"},
            },
            {"action": "clear", "target": {"name": "field", "intent": "text field"}},
            {"action": "press_key", "key": "ENTER"},
            {"action": "hide_keyboard"},
            {"action": "assert_checked", "target": {"name": "checkbox", "intent": "checkbox"}},
            {"action": "assert_enabled", "target": {"name": "button", "intent": "submit"}},
            {"action": "assert_selected", "target": {"name": "tab", "intent": "active tab"}},
            {"action": "assert_text_equals", "target": {"name": "title", "intent": "title"}, "text": "Home"},
            {"action": "assert_text_contains", "target": {"name": "message", "intent": "message"}, "text": "Done"},
            {"action": "wait_gone", "target": {"name": "spinner", "intent": "loading spinner"}},
            {"action": "assert_not_visible", "target": {"name": "error", "intent": "error message"}},
            {"action": "tap_coordinates", "x": 100, "y": 200},
            {"action": "background_app", "seconds": 1},
            {"action": "activate_app"},
            {"action": "terminate_app"},
            {"action": "change_orientation", "orientation": "LANDSCAPE"},
            {"action": "accept_permission"},
            {"action": "dismiss_dialog"},
            {"action": "pinch", "area": {"x": 0, "y": 0, "width": 100, "height": 100}},
            {"action": "zoom", "target": {"name": "map", "intent": "map"}},
            {"action": "w3c_actions", "actions": []},
        ],
    }

    validate_intent_dsl(dsl)
    assert action_target_fields("drag_and_drop") == ["source", "target"]
    assert action_target_fields("scroll") == ["target"]


@pytest.mark.parametrize(
    ("step", "message"),
    [
        ({"action": "swipe"}, "requires direction or start/end"),
        ({"action": "drag_and_drop"}, "requires source/target or start/end"),
        ({"action": "tap_coordinates", "x": 0}, "requires y"),
        ({"action": "press_key"}, "requires key"),
        ({"action": "pinch"}, "requires target or area"),
    ],
)
def test_validate_extended_action_shapes(step: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_intent_dsl({"name": "invalid action", "steps": [step]})


def test_codegen_uses_shared_action_runtime_and_compiles(tmp_path) -> None:
    config = AndroidTestConfig(
        project_root=tmp_path,
        generated_dir=tmp_path / "generated",
        artifacts_dir=tmp_path / "artifacts",
        reports_dir=tmp_path / "reports",
        checkpoint_dir=tmp_path / "reports" / "checkpoints",
        checkpoint_db_path=tmp_path / "reports" / "checkpoints" / "langgraph.sqlite",
        knowledge_dir=tmp_path / "knowledge",
        app_package="com.example",
        app_activity=".MainActivity",
    )
    dsl = {
        "name": "extended codegen",
        "steps": [
            {"action": "launch_app"},
            {"action": "tap_coordinates", "x": 10, "y": 20},
            {"action": "press_key", "key": "BACK"},
            {"action": "w3c_actions", "actions": []},
        ],
    }

    code = PytestAppiumCodeGenerator(config).render_pytest(dsl)

    assert "from android_test_agent.dsl.action_runtime import AndroidDslActionRuntime" in code
    assert "ACTION_RUNTIME.run_step(driver, step)" in code
    compile(code, "generated_test.py", "exec")
