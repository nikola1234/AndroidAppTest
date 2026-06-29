from __future__ import annotations

from android_test_agent.agent.state import AgentState, ValidationResult


class ValidatorNode:
    """Classify execution results for reporting and retry decisions."""

    def __call__(self, state: AgentState) -> AgentState:
        execution = state["execution_result"]
        status = execution["status"]
        if status in {"passed", "dry_run"}:
            result: ValidationResult = {
                "passed": True,
                "reason": "Generated test passed." if status == "passed" else "Dry-run completed.",
                "failure_type": None,
                "suggestions": [],
            }
            return {**state, "validation_result": result}

        stdout = execution.get("stdout", "")
        stderr = execution.get("stderr", "")
        combined = f"{stdout}\n{stderr}".lower()
        failure_type = self._classify_failure(combined)
        suggestions = self._suggestions(failure_type)
        result = {
            "passed": False,
            "reason": "Generated test failed during execution.",
            "failure_type": failure_type,
            "suggestions": suggestions,
        }
        return {**state, "validation_result": result}

    def _classify_failure(self, output: str) -> str:
        if (
            "locatorresolutionerror" in output
            or "no locator candidates" in output
            or "nosuchelement" in output
            or "no such element" in output
        ):
            return "locator_not_found"
        if (
            "sessionnotcreated" in output
            or "could not connect" in output
            or "connection refused" in output
            or "max retries exceeded" in output
            or "failed to establish a new connection" in output
        ):
            return "environment"
        if "timeout" in output:
            return "timeout"
        if "assert" in output:
            return "assertion"
        return "unknown"

    def _suggestions(self, failure_type: str) -> list[str]:
        mapping = {
            "locator_not_found": [
                "Refresh UI dump and regenerate locator candidates.",
                "Search element memory for historical locator mappings.",
            ],
            "timeout": [
                "Add wait_visible before the failing action.",
                "Check whether the app is still loading or stuck on a different page.",
            ],
            "environment": [
                "Verify Appium server, adb device connection, appPackage and appActivity.",
            ],
            "assertion": [
                "Review expected result with screenshot and UI dump before changing assertions.",
            ],
            "unknown": [
                "Collect screenshot, UI dump and logcat for root-cause analysis.",
            ],
        }
        return mapping[failure_type]
