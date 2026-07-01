from __future__ import annotations

import re
from typing import Any

import yaml

from android_test_agent.agent.runtime_skills import RuntimeSkillLoader
from android_test_agent.agent.state import AgentState
from android_test_agent.llm.base import LLMClient


class AnalyzerNode:
    """Turn a raw test case into normalized requirements."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm
        self._skills = RuntimeSkillLoader()

    def __call__(self, state: AgentState) -> AgentState:
        raw_case = state["raw_case"]
        analyzed = self._from_yaml(raw_case) or self._from_llm(raw_case) or self._fallback(raw_case)
        return {**state, "analyzed_requirements": analyzed}

    def _from_yaml(self, raw_case: str) -> dict[str, Any] | None:
        try:
            data = yaml.safe_load(raw_case)
        except yaml.YAMLError:
            return None
        if isinstance(data, dict) and data.get("name"):
            return {
                "name": data["name"],
                "description": data.get("description", raw_case),
                "preconditions": data.get("preconditions", []),
                "expected_result": data.get("expected_result"),
                "steps": data.get("steps"),
            }
        return None

    def _from_llm(self, raw_case: str) -> dict[str, Any] | None:
        if not self._llm:
            return None
        system_prompt = self._skills.compose(
            "requirements",
            task_prompt=(
                "You extract Android app testing requirements. "
                "Return strict JSON with fields: name, description, preconditions, expected_result."
            ),
        )
        user_prompt = f"Test case:\n{raw_case}"
        try:
            result = self._llm.complete_json(system_prompt, user_prompt)
        except Exception:
            return None
        if isinstance(result, dict) and result.get("name"):
            return result
        return None

    def _fallback(self, raw_case: str) -> dict[str, Any]:
        title = self._title(raw_case)
        return {
            "name": title,
            "description": raw_case,
            "preconditions": [],
            "expected_result": self._section(raw_case, "期望结果")
            or "Test finishes without functional errors.",
        }

    def _title(self, raw_case: str) -> str:
        for line in raw_case.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:60]
        return "generated_android_test"

    def _section(self, raw_case: str, heading: str) -> str:
        pattern = re.compile(
            rf"{re.escape(heading)}\s*[:：]\s*(.*?)(?=\n\s*[\w\u4e00-\u9fff ]+\s*[:：]|\Z)",
            re.DOTALL,
        )
        match = pattern.search(raw_case)
        if not match:
            return ""
        return " ".join(line.strip() for line in match.group(1).splitlines() if line.strip())
