from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import yaml

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.agent.runtime_skills import RuntimeSkillLoader
from android_test_agent.agent.state import AgentState
from android_test_agent.dsl.generated_registry import GeneratedFileRegistry, source_case_key
from android_test_agent.dsl.schema import normalize_test_name, validate_intent_dsl
from android_test_agent.llm.base import LLMClient


class LlmCodegenNode:
    """Generate pytest/Appium code with an LLM, guarded by compile checks."""

    def __init__(self, config: AndroidTestConfig, llm: LLMClient | None) -> None:
        self._config = config
        self._llm = llm
        self._skills = RuntimeSkillLoader()
        self._registry = GeneratedFileRegistry(config)

    def __call__(self, state: AgentState) -> AgentState:
        if not self._llm:
            raise RuntimeError("LLM codegen is enabled, but no LLM client is configured.")

        dsl = state.get("resolved_dsl") or state["dsl"]
        validate_intent_dsl(dsl)
        case_key = source_case_key(state.get("raw_case"))
        self._registry.cleanup_previous(case_key)
        generated_files = self._write(dsl)
        self._registry.remember(case_key, generated_files)
        metadata = dict(state.get("metadata", {}))
        metadata["codegen_mode"] = "llm"
        return {**state, "dsl": dsl, "generated_files": generated_files, "metadata": metadata}

    def _write(self, dsl: dict[str, Any]) -> dict[str, str]:
        test_name = normalize_test_name(dsl["name"])
        dsl_dir = self._config.generated_dir / "dsl"
        tests_dir = self._config.generated_dir / "tests"
        dsl_dir.mkdir(parents=True, exist_ok=True)
        tests_dir.mkdir(parents=True, exist_ok=True)

        dsl_path = dsl_dir / f"{test_name}.yaml"
        test_path = tests_dir / f"test_{test_name}.py"
        dsl_path.write_text(yaml.safe_dump(dsl, allow_unicode=True, sort_keys=False), encoding="utf-8")

        code = self._generate_checked_code(dsl, test_name)
        test_path.write_text(code, encoding="utf-8")
        return {"dsl": str(dsl_path), "pytest": str(test_path)}

    def _generate_checked_code(self, dsl: dict[str, Any], test_name: str) -> str:
        code = self._generate_code(dsl, test_name)
        error = self._compile_error(code, test_name)
        if not error:
            return code

        repaired = self._repair_code(dsl, test_name, code, error)
        repaired_error = self._compile_error(repaired, test_name)
        if repaired_error:
            raise RuntimeError(f"LLM-generated pytest did not compile after repair: {repaired_error}")
        return repaired

    def _generate_code(self, dsl: dict[str, Any], test_name: str) -> str:
        system_prompt = self._system_prompt(
            "Generate the complete pytest/Appium Python file from the supplied resolved DSL."
        )
        user_prompt = self._user_prompt(dsl, test_name)
        return self._extract_code(self._llm.complete(system_prompt, user_prompt))

    def _repair_code(
        self,
        dsl: dict[str, Any],
        test_name: str,
        code: str,
        error: str,
    ) -> str:
        system_prompt = self._system_prompt(
            "Repair the supplied pytest/Appium Python file. Return only corrected Python code."
        )
        user_prompt = (
            self._user_prompt(dsl, test_name)
            + "\n\nThe previous code failed Python compile().\n\n"
            + f"Compile error:\n{error}\n\nPrevious code:\n```python\n{code}\n```"
        )
        return self._extract_code(self._llm.complete(system_prompt, user_prompt))

    def _system_prompt(self, task_prompt: str) -> str:
        return self._skills.compose(
            "codegen",
            "tools",
            references=["appium_patterns", "dsl_schema", "locator_candidate_scoring"],
            resources=["supported_actions", "dsl_schema", "locator_sources"],
            task_prompt=task_prompt,
        )

    def _user_prompt(self, dsl: dict[str, Any], test_name: str) -> str:
        payload = {
            "test_name": test_name,
            "dsl": dsl,
            "appium_server_url": self._config.appium_server_url,
            "capabilities": self._capabilities(),
            "implicit_wait_seconds": self._config.implicit_wait_seconds,
            "explicit_wait_seconds": self._config.explicit_wait_seconds,
            "project_runtime_imports": {
                "config": "from android_test_agent.agent.config import AndroidTestConfig",
                "locator_resolver": (
                    "from android_test_agent.dsl.locator_resolver import "
                    "LocatorResolutionError, LocatorResolver"
                ),
            },
        }
        return "Generate pytest code for this payload:\n" + json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )

    def _capabilities(self) -> dict[str, Any]:
        capabilities: dict[str, Any] = {
            "platformName": self._config.platform_name,
            "appium:automationName": "UiAutomator2",
            "appium:deviceName": self._config.device_name,
        }
        if self._config.app_package:
            capabilities["appium:appPackage"] = self._config.app_package
        if self._config.app_activity:
            capabilities["appium:appActivity"] = self._config.app_activity
        if self._config.apk_path:
            capabilities["appium:app"] = str(Path(self._config.apk_path))
        return capabilities

    def _extract_code(self, text: str) -> str:
        stripped = text.strip()
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("code"), str):
            return payload["code"].strip()

        fenced = re.search(r"```(?:python)?\s*(.*?)```", stripped, re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1).strip()
        return stripped

    def _compile_error(self, code: str, test_name: str) -> str:
        if "def test_" not in code:
            return "Generated code must contain a pytest test function named def test_*."
        try:
            compile(code, f"test_{test_name}.py", "exec")
        except SyntaxError as exc:
            return f"{exc.__class__.__name__}: {exc}"
        return ""
