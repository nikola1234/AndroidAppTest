from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.agent.state import AgentState
from android_test_agent.memory.failure_memory import FailureMemory


class FailureKnowledgeNode:
    """Persist and retrieve local failure knowledge for future retries."""

    def __init__(self, config: AndroidTestConfig, memory: FailureMemory | None = None) -> None:
        self._config = config
        self._memory = memory or FailureMemory(config.knowledge_dir / "failures" / "failure_memory.json")

    def __call__(self, state: AgentState) -> AgentState:
        validation = state.get("validation_result", {})
        if validation.get("passed") is True:
            return self._mark_last_failure_verified(state)
        if validation.get("passed") is not False:
            return state

        fingerprint = str(validation.get("fingerprint") or "")
        query = self._query(validation)
        matches = self._matches(fingerprint, query)
        suggestions = self._merge_suggestions(
            list(validation.get("suggestions", [])),
            matches,
        )
        updated_validation = {**validation, "suggestions": suggestions}

        item = self._memory_item(state, updated_validation, matches)
        stored = self._memory.upsert_by_fingerprint(item)

        metadata = dict(state.get("metadata", {}))
        metadata["last_failure_fingerprint"] = stored.get("fingerprint")
        metadata["failure_knowledge"] = {
            "fingerprint": stored.get("fingerprint"),
            "matches": len(matches),
            "occurrence_count": stored.get("occurrence_count"),
            "status": stored.get("status"),
        }
        return {**state, "validation_result": updated_validation, "metadata": metadata}

    def _mark_last_failure_verified(self, state: AgentState) -> AgentState:
        metadata = dict(state.get("metadata", {}))
        fingerprint = metadata.get("last_failure_fingerprint")
        if not fingerprint:
            return state

        existing = self._memory.find_by_fingerprint(str(fingerprint))
        if not existing:
            return state

        confidence = min(float(existing.get("confidence", 0.5)) + 0.2, 1.0)
        stored = self._memory.upsert_by_fingerprint(
            {
                **existing,
                "fingerprint": fingerprint,
                "status": "verified",
                "confidence": confidence,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "successful_fix": self._successful_fix(state),
            },
            increment=False,
        )
        metadata["failure_knowledge"] = {
            "fingerprint": stored.get("fingerprint"),
            "status": stored.get("status"),
            "confidence": stored.get("confidence"),
        }
        return {**state, "metadata": metadata}

    def _matches(self, fingerprint: str, query: str) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        if fingerprint:
            exact = self._memory.find_by_fingerprint(fingerprint)
            if exact:
                matches.append(exact)
        for item in self._memory.search(query, limit=5):
            if item.get("fingerprint") != fingerprint and item not in matches:
                matches.append(item)
        return matches

    def _merge_suggestions(
        self,
        suggestions: list[str],
        matches: list[dict[str, Any]],
    ) -> list[str]:
        merged = list(suggestions)
        seen = {suggestion.strip() for suggestion in merged}
        for match in matches:
            for fix in match.get("suggested_fix", []):
                if not isinstance(fix, str):
                    continue
                suggestion = fix.strip()
                if suggestion and suggestion not in seen:
                    merged.append(suggestion)
                    seen.add(suggestion)
        return merged

    def _memory_item(
        self,
        state: AgentState,
        validation: dict[str, Any],
        matches: list[dict[str, Any]],
    ) -> dict[str, Any]:
        artifacts = state.get("artifacts", {})
        failure_artifacts = state.get("metadata", {}).get("failure_artifacts", {})
        historical_status = self._best_status(matches)
        confidence = 0.5 if historical_status != "verified" else 0.8
        return {
            "fingerprint": validation.get("fingerprint"),
            "failure_type": validation.get("failure_type"),
            "exception_class": validation.get("exception_class", ""),
            "error_signature": validation.get("error_signature", ""),
            "failing_action": validation.get("failing_action", ""),
            "failing_target": validation.get("failing_target", ""),
            "stack_summary": validation.get("stack_summary", []),
            "suggested_fix": list(validation.get("suggestions", [])),
            "status": historical_status or "observed",
            "confidence": confidence,
            "artifacts": {
                "trace": artifacts.get("failure_trace") or failure_artifacts.get("trace"),
                "screenshot": artifacts.get("failure_screenshot") or failure_artifacts.get("screenshot"),
                "ui_dump": artifacts.get("failure_ui_dump") or failure_artifacts.get("ui_dump"),
                "logcat": artifacts.get("failure_logcat") or failure_artifacts.get("logcat"),
                "appium_status": artifacts.get("failure_appium_status") or failure_artifacts.get("appium_status"),
            },
            "last_execution_status": state.get("execution_result", {}).get("status"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _query(self, validation: dict[str, Any]) -> str:
        return " ".join(
            str(value)
            for value in [
                validation.get("fingerprint"),
                validation.get("failure_type"),
                validation.get("exception_class"),
                validation.get("error_signature"),
                validation.get("failing_action"),
                validation.get("failing_target"),
            ]
            if value
        )

    def _best_status(self, matches: list[dict[str, Any]]) -> str:
        if any(match.get("status") == "verified" for match in matches):
            return "verified"
        if any(match.get("status") == "observed" for match in matches):
            return "observed"
        return ""

    def _successful_fix(self, state: AgentState) -> dict[str, Any]:
        return {
            "retry_count": state.get("retry_count", 0),
            "generated_files": state.get("generated_files", {}),
            "validation_reason": state.get("validation_result", {}).get("reason"),
        }
