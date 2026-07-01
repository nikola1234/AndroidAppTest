from __future__ import annotations

import json

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.agent.nodes.failure_knowledge import FailureKnowledgeNode
from android_test_agent.agent.nodes.validator import ValidatorNode
from android_test_agent.memory.failure_memory import FailureMemory


def test_validator_extracts_failure_fingerprint() -> None:
    state = {
        "execution_result": {
            "status": "failed",
            "stdout": """
E   selenium.common.exceptions.NoSuchElementException: Message: no such element: login_button
android_test_agent.dsl.action_runtime.wait_for
generated.tests.test_login.run_step
No locator candidates found for target 'login_button'
""",
            "stderr": "",
        }
    }

    result = ValidatorNode()(state)["validation_result"]

    assert result["passed"] is False
    assert result["failure_type"] == "locator_not_found"
    assert result["exception_class"] == "NoSuchElementException"
    assert result["failing_target"] == "login_button"
    assert "locator_not_found" in result["fingerprint"]
    assert result["stack_summary"]


def test_failure_memory_upserts_by_fingerprint(tmp_path) -> None:
    memory = FailureMemory(tmp_path / "failure_memory.json")

    first = memory.upsert_by_fingerprint(
        {
            "fingerprint": "timeout:timeoutexception:tap:login:waiting",
            "suggested_fix": ["Add wait_visible before tapping login."],
        }
    )
    second = memory.upsert_by_fingerprint(
        {
            "fingerprint": "timeout:timeoutexception:tap:login:waiting",
            "suggested_fix": ["Increase explicit wait for login."],
        }
    )

    assert first["occurrence_count"] == 1
    assert second["occurrence_count"] == 2
    assert memory.find_by_fingerprint("timeout:timeoutexception:tap:login:waiting")["suggested_fix"] == [
        "Increase explicit wait for login."
    ]


def test_failure_knowledge_merges_historical_suggestions(tmp_path) -> None:
    config = _config(tmp_path)
    memory = FailureMemory(tmp_path / "knowledge" / "failures" / "failure_memory.json")
    memory.upsert_by_fingerprint(
        {
            "fingerprint": "locator_not_found:nosuchelementexception:tap:login:no_such_element",
            "failure_type": "locator_not_found",
            "exception_class": "NoSuchElementException",
            "failing_action": "tap",
            "failing_target": "login",
            "error_signature": "no such element",
            "suggested_fix": ["Use accessibility_id for the login button."],
            "status": "verified",
            "confidence": 0.9,
        }
    )
    state = {
        "validation_result": {
            "passed": False,
            "failure_type": "locator_not_found",
            "exception_class": "NoSuchElementException",
            "error_signature": "no such element",
            "failing_action": "tap",
            "failing_target": "login",
            "fingerprint": "locator_not_found:nosuchelementexception:tap:login:no_such_element",
            "stack_summary": [],
            "suggestions": ["Refresh UI dump and regenerate locator candidates."],
        },
        "execution_result": {"status": "failed"},
        "artifacts": {"failure_trace": "artifacts/traces/failure.json"},
        "metadata": {},
    }

    updated = FailureKnowledgeNode(config, memory=memory)(state)

    suggestions = updated["validation_result"]["suggestions"]
    assert "Refresh UI dump and regenerate locator candidates." in suggestions
    assert "Use accessibility_id for the login button." in suggestions
    assert updated["metadata"]["last_failure_fingerprint"]
    stored = json.loads((tmp_path / "knowledge" / "failures" / "failure_memory.json").read_text(encoding="utf-8"))
    assert stored[0]["occurrence_count"] == 2


def test_failure_knowledge_marks_last_failure_verified(tmp_path) -> None:
    config = _config(tmp_path)
    memory = FailureMemory(tmp_path / "knowledge" / "failures" / "failure_memory.json")
    memory.upsert_by_fingerprint(
        {
            "fingerprint": "timeout:timeoutexception:tap:login:waiting",
            "status": "observed",
            "confidence": 0.5,
            "suggested_fix": ["Add wait_visible before tapping login."],
        }
    )
    state = {
        "validation_result": {"passed": True, "reason": "Generated test passed."},
        "generated_files": {"pytest": "generated/tests/test_login.py"},
        "metadata": {"last_failure_fingerprint": "timeout:timeoutexception:tap:login:waiting"},
        "retry_count": 1,
    }

    updated = FailureKnowledgeNode(config, memory=memory)(state)

    stored = memory.find_by_fingerprint("timeout:timeoutexception:tap:login:waiting")
    assert stored["status"] == "verified"
    assert stored["confidence"] > 0.5
    assert stored["occurrence_count"] == 1
    assert updated["metadata"]["failure_knowledge"]["status"] == "verified"


def _config(tmp_path) -> AndroidTestConfig:
    return AndroidTestConfig(
        project_root=tmp_path,
        generated_dir=tmp_path / "generated",
        artifacts_dir=tmp_path / "artifacts",
        reports_dir=tmp_path / "reports",
        checkpoint_dir=tmp_path / "reports" / "checkpoints",
        checkpoint_db_path=tmp_path / "reports" / "checkpoints" / "langgraph.sqlite",
        knowledge_dir=tmp_path / "knowledge",
    )
