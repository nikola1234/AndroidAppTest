from __future__ import annotations

from copy import deepcopy
from typing import Any

from android_test_agent.agent.runtime_skills import RuntimeSkillLoader
from android_test_agent.agent.state import AgentState
from android_test_agent.llm.base import LLMClient


class PlannerNode:
    """Create structured test steps from analyzed requirements."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm
        self._skills = RuntimeSkillLoader()

    def __call__(self, state: AgentState) -> AgentState:
        requirements = state["analyzed_requirements"]
        include_references = bool(state.get("metadata", {}).get("last_debug"))
        plan = (
            self._from_existing_steps(requirements)
            or self._from_llm(requirements, include_references=include_references)
            or self._fallback(requirements)
        )
        return {**state, "plan": self._strip_generated_locators(plan)}

    def _from_existing_steps(self, requirements: dict[str, Any]) -> dict[str, Any] | None:
        steps = requirements.get("steps")
        if not isinstance(steps, list) or not steps:
            return None
        return {
            "name": requirements["name"],
            "description": requirements.get("description", ""),
            "steps": steps,
            "assertions": [requirements.get("expected_result")] if requirements.get("expected_result") else [],
        }

    def _from_llm(self, requirements: dict[str, Any], include_references: bool = False) -> dict[str, Any] | None:
        if not self._llm:
            return None
        system_prompt = self._skills.compose(
            "planning",
            "tools",
            references=["appium_patterns", "failure_routing"] if include_references else None,
            resources=["supported_actions"],
            task_prompt=(
                "You are an Android test planner. Return strict JSON with fields: "
                "name, description, steps, assertions."
            ),
        )
        user_prompt = f"Requirements:\n{requirements}"
        try:
            result = self._llm.complete_json(system_prompt, user_prompt)
        except Exception:
            return None
        if isinstance(result, dict) and isinstance(result.get("steps"), list):
            return result
        return None

    def _fallback(self, requirements: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": requirements["name"],
            "description": requirements.get("description", ""),
            "steps": [
                {"action": "launch_app"},
                {
                    "action": "assert_text",
                    "text": requirements.get("expected_result") or requirements["name"],
                },
            ],
            "assertions": [requirements.get("expected_result")] if requirements.get("expected_result") else [],
        }

    def _strip_generated_locators(self, plan: dict[str, Any]) -> dict[str, Any]:
        updated = deepcopy(plan)
        for step in updated.get("steps", []):
            target = step.get("target")
            if not isinstance(target, dict):
                continue
            if "locator" not in target:
                continue
            # Locators belong to the resolver stage; planner output remains intent-level.
            target.pop("locator", None)
        return updated
