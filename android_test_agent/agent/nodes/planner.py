from __future__ import annotations

from copy import deepcopy
import re
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
        text_assertions = self._text_assertions(requirements)
        return {
            "name": requirements["name"],
            "description": requirements.get("description", ""),
            "steps": [{"action": "launch_app"}, *text_assertions],
            "assertions": [requirements.get("expected_result")] if requirements.get("expected_result") else [],
        }

    def _text_assertions(self, requirements: dict[str, Any]) -> list[dict[str, str]]:
        expected = str(requirements.get("expected_result") or "").strip()
        description = str(requirements.get("description") or "")
        source = expected or description
        tokens = self._visible_text_tokens(source)
        if tokens:
            if self._requires_scroll(expected, description) and len(tokens) > 4:
                return self._scrolling_text_assertions(tokens)
            return [{"action": "assert_text", "text": token} for token in tokens]
        return [{"action": "assert_text", "text": expected or requirements["name"]}]

    def _scrolling_text_assertions(self, tokens: list[str]) -> list[dict[str, str]]:
        first_screen_count = min(4, len(tokens))
        steps = [{"action": "assert_text", "text": token} for token in tokens[:first_screen_count]]
        for token in tokens[first_screen_count:]:
            steps.append({"action": "scroll_to_text", "text": token})
            steps.append({"action": "assert_text", "text": token})
        return steps

    def _requires_scroll(self, *values: str) -> bool:
        text = " ".join(values)
        return any(keyword in text for keyword in ("滚动", "向下", "滑动", "下滑", "scroll"))

    def _visible_text_tokens(self, text: str) -> list[str]:
        ignored = {
            "Android",
            "ApiDemos",
            "Appium",
            "DSL",
            "LLM",
            "UI",
            "Agent",
            "Test",
        }
        tokens = re.findall(r"\b[A-Z][A-Za-z0-9_]{1,}\b", text)
        unique: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token in ignored or token in seen:
                continue
            seen.add(token)
            unique.append(token)
        return unique

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
