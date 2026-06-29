from __future__ import annotations

from android_test_agent.agent.state import AgentState


class DebugNode:
    """Record diagnostics for failures that require replanning or human review."""

    def __call__(self, state: AgentState) -> AgentState:
        validation = state.get("validation_result", {})
        retry_count = state.get("retry_count", 0) + 1
        failure_type = validation.get("failure_type") or "unknown"
        errors = list(state.get("errors", []))
        errors.append(validation.get("reason", "Generated test failed"))

        metadata = dict(state.get("metadata", {}))
        metadata["last_debug"] = {
            "failure_type": failure_type,
            "retry_count": retry_count,
            "suggestions": validation.get("suggestions", []),
            "execution_status": state.get("execution_result", {}).get("status"),
        }
        return {
            **state,
            "retry_count": retry_count,
            "errors": errors,
            "metadata": metadata,
        }
