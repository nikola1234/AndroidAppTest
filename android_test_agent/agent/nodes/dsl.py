from __future__ import annotations

from copy import deepcopy
from typing import Any

from android_test_agent.agent.runtime_skills import RuntimeSkillLoader
from android_test_agent.agent.state import AgentState
from android_test_agent.dsl.schema import action_target_fields, validate_intent_dsl
from android_test_agent.llm.base import LLMClient


class DslNode:
    """Create an intent-level DSL from a planned Android test flow."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm
        self._skills = RuntimeSkillLoader()

    def __call__(self, state: AgentState) -> AgentState:
        plan = state["plan"]
        dsl = state.get("dsl") if state.get("retry_count") else None
        if not dsl:
            include_references = bool(state.get("retry_count") or state.get("metadata", {}).get("last_debug"))
            dsl = self._from_llm(plan, include_references=include_references) or self._from_plan(plan)
        dsl = self._to_intent_dsl(dsl)
        validate_intent_dsl(dsl)
        return {**state, "intent_dsl": dsl, "dsl": dsl}

    def _from_llm(self, plan: dict[str, Any], include_references: bool = False) -> dict[str, Any] | None:
        if not self._llm:
            return None
        system_prompt = self._skills.compose(
            "dsl",
            "tools",
            references=["dsl_schema"] if include_references else None,
            resources=["supported_actions", "dsl_schema"],
            task_prompt="Convert an Android test plan to strict JSON DSL.",
        )
        user_prompt = f"Plan:\n{plan}"
        try:
            result = self._llm.complete_json(system_prompt, user_prompt)
        except Exception:
            return None
        if isinstance(result, dict) and result.get("steps"):
            return result
        return None

    def _from_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": plan["name"],
            "description": plan.get("description", ""),
            "steps": plan["steps"],
        }

    def _to_intent_dsl(self, dsl: dict[str, Any]) -> dict[str, Any]:
        updated = deepcopy(dsl)
        for step in updated.get("steps", []):
            for field in action_target_fields(str(step.get("action"))):
                target = step.get(field)
                if isinstance(target, dict):
                    step[field] = self._clean_target(target)
                elif isinstance(target, str):
                    step[field] = {
                        "name": self._infer_target_name(target),
                        "intent": target,
                    }
        return updated

    def _clean_target(self, target: dict[str, Any]) -> dict[str, Any]:
        if self._has_trusted_locator(target):
            return deepcopy(target)

        locator = target.get("locator") if isinstance(target.get("locator"), dict) else target
        locator_value = (
            locator.get("value")
            or locator.get("id")
            or locator.get("text")
            or target.get("value")
            or target.get("text")
        )
        cleaned = {
            key: value
            for key, value in target.items()
            if key not in {"locator", "by", "value", "id", "text"} and value is not None
        }
        if not cleaned.get("name"):
            cleaned["name"] = self._infer_target_name(str(locator_value or target))
        if not cleaned.get("intent") and locator_value:
            cleaned["intent"] = str(locator_value)
        return cleaned

    def _has_trusted_locator(self, target: dict[str, Any]) -> bool:
        locator = target.get("locator")
        return (
            isinstance(locator, dict)
            and bool(locator.get("by"))
            and bool(locator.get("value"))
            and bool(target.get("locator_source"))
        )

    def _infer_target_name(self, value: str) -> str:
        candidate = value.strip().split("/")[-1].split(":")[-1]
        normalized = "".join(char.lower() if char.isalnum() else "_" for char in candidate)
        return "_".join(part for part in normalized.split("_") if part) or "target"
