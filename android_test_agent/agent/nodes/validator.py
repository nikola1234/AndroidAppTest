from __future__ import annotations

import re

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
        raw_output = f"{stdout}\n{stderr}"
        failure_type = self._classify_failure(combined)
        exception_class = self._exception_class(raw_output)
        error_signature = self._error_signature(raw_output, exception_class)
        stack_summary = self._stack_summary(raw_output)
        failing_action = self._failing_action(raw_output)
        failing_target = self._failing_target(raw_output)
        suggestions = self._suggestions(failure_type)
        result = {
            "passed": False,
            "reason": "Generated test failed during execution.",
            "failure_type": failure_type,
            "exception_class": exception_class,
            "error_signature": error_signature,
            "stack_summary": stack_summary,
            "failing_action": failing_action,
            "failing_target": failing_target,
            "fingerprint": self._fingerprint(
                failure_type,
                exception_class,
                failing_action,
                failing_target,
                error_signature,
            ),
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

    def _exception_class(self, output: str) -> str:
        patterns = [
            r"\b([A-Za-z_][A-Za-z0-9_]*(?:Exception|Error))\b",
            r"E\s+([A-Za-z_][A-Za-z0-9_]*(?:Exception|Error))\b",
        ]
        ignored = {"AssertionError"} if "assert" not in output.lower() else set()
        for pattern in patterns:
            for match in re.finditer(pattern, output):
                candidate = match.group(1)
                if candidate not in ignored:
                    return candidate
        return ""

    def _error_signature(self, output: str, exception_class: str) -> str:
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if exception_class:
            for line in lines:
                if exception_class in line:
                    return self._normalize_signature(line)
        for line in reversed(lines):
            if line.startswith(("E ", "E\t")) or "error" in line.lower() or "exception" in line.lower():
                return self._normalize_signature(line)
        return self._normalize_signature(lines[-1]) if lines else ""

    def _stack_summary(self, output: str) -> list[str]:
        frames: list[str] = []
        for line in output.splitlines():
            if "android_test_agent" not in line and "generated" not in line:
                continue
            cleaned = line.strip()
            if not cleaned or cleaned in frames:
                continue
            frames.append(cleaned)
            if len(frames) >= 5:
                break
        return frames

    def _failing_action(self, output: str) -> str:
        patterns = [
            r"action['\"]?\s*[:=]\s*['\"]([A-Za-z_][A-Za-z0-9_]*)",
            r"Unsupported action:\s*([A-Za-z_][A-Za-z0-9_]*)",
            r"run_step\(driver,\s*\{[^}]*['\"]action['\"]:\s*['\"]([A-Za-z_][A-Za-z0-9_]*)",
        ]
        return self._first_match(output, patterns)

    def _failing_target(self, output: str) -> str:
        patterns = [
            r"target['\"]?\s*[:=]\s*['\"]([^'\"]{1,120})",
            r"Target has no resolvable name or intent:\s*(.{1,120})",
            r"No locator candidates found for target ['\"]([^'\"]+)['\"]",
        ]
        return self._first_match(output, patterns)

    def _first_match(self, output: str, patterns: list[str]) -> str:
        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE | re.DOTALL)
            if match:
                return self._short_token(match.group(1))
        return ""

    def _fingerprint(
        self,
        failure_type: str,
        exception_class: str,
        failing_action: str,
        failing_target: str,
        error_signature: str,
    ) -> str:
        parts = [
            failure_type,
            exception_class or "unknown_exception",
            failing_action or "unknown_action",
            failing_target or "unknown_target",
            error_signature or "unknown_error",
        ]
        return ":".join(self._fingerprint_part(part) for part in parts)

    def _normalize_signature(self, value: str) -> str:
        value = re.sub(r"0x[0-9a-fA-F]+", "0x", value)
        value = re.sub(r"\d{4,}", "<num>", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()[:240]

    def _short_token(self, value: str) -> str:
        value = re.sub(r"\s+", " ", str(value)).strip()
        return value[:120]

    def _fingerprint_part(self, value: str) -> str:
        normalized = self._normalize_signature(value).lower()
        normalized = re.sub(r"[^a-z0-9_\-\.\u4e00-\u9fff]+", "_", normalized)
        normalized = normalized.strip("_")
        return normalized[:80] or "unknown"
