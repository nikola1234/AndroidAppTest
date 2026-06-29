from __future__ import annotations

from android_test_agent.agent.state import AgentState
from android_test_agent.executor.retry_policy import RetryPolicy


class WaitStrategyNode:
    """Apply wait-focused repairs for timeout failures."""

    def __init__(self, retry_policy: RetryPolicy | None = None) -> None:
        self._retry_policy = retry_policy or RetryPolicy()

    def __call__(self, state: AgentState) -> AgentState:
        validation = state.get("validation_result", {})
        retry_count = state.get("retry_count", 0) + 1
        errors = list(state.get("errors", []))
        errors.append(validation.get("reason", "Timeout failure"))

        dsl = self._retry_policy.repair_dsl(state["dsl"], "timeout")
        metadata = dict(state.get("metadata", {}))
        metadata["last_repair"] = {
            "node": "wait_strategy",
            "failure_type": "timeout",
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
