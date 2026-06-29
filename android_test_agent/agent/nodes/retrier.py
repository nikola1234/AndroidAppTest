from __future__ import annotations

from copy import deepcopy
from typing import Any

from android_test_agent.agent.state import AgentState
from android_test_agent.executor.retry_policy import RetryPolicy


class RetrierNode:
    """Apply conservative automatic fixes before another execution attempt."""

    def __init__(self, retry_policy: RetryPolicy | None = None) -> None:
        self._retry_policy = retry_policy or RetryPolicy()

    def __call__(self, state: AgentState) -> AgentState:
        validation = state.get("validation_result", {})
        failure_type = validation.get("failure_type")
        retry_count = state.get("retry_count", 0) + 1
        errors = list(state.get("errors", []))
        errors.append(validation.get("reason", "Unknown failure"))

        dsl = self._retry_policy.repair_dsl(state["dsl"], failure_type)
        if failure_type == "locator_not_found":
            dsl = self._clear_resolved_locators(dsl)

        metadata = dict(state.get("metadata", {}))
        metadata["last_repair"] = {
            "node": "retrier",
            "failure_type": failure_type,
            "retry_count": retry_count,
        }
        return {
            **state,
            "dsl": dsl,
            "intent_dsl": dsl,
            "resolved_dsl": dsl,
            "retry_count": retry_count,
            "errors": errors,
            "metadata": metadata,
        }

    def _clear_resolved_locators(self, dsl: dict[str, Any]) -> dict[str, Any]:
        updated = deepcopy(dsl)
        for step in updated.get("steps", []):
            target = step.get("target")
            if not isinstance(target, dict):
                continue
            target.pop("locator", None)
            target.pop("locator_source", None)
            target.pop("locator_score", None)
            target.pop("locator_reason", None)
            target.pop("locator_metadata", None)
        return updated
