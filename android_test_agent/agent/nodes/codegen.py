from __future__ import annotations

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.agent.state import AgentState
from android_test_agent.dsl.codegen import PytestAppiumCodeGenerator
from android_test_agent.dsl.generated_registry import GeneratedFileRegistry, source_case_key
from android_test_agent.dsl.schema import validate_intent_dsl


class CodegenNode:
    """Generate stable pytest/Appium code from the resolved DSL."""

    def __init__(self, config: AndroidTestConfig) -> None:
        self._generator = PytestAppiumCodeGenerator(config)
        self._registry = GeneratedFileRegistry(config)

    def __call__(self, state: AgentState) -> AgentState:
        dsl = state.get("resolved_dsl") or state["dsl"]
        validate_intent_dsl(dsl)
        case_key = source_case_key(state.get("raw_case"))
        self._registry.cleanup_previous(case_key)
        generated_files = self._generator.write(dsl)
        self._registry.remember(case_key, generated_files)
        return {**state, "dsl": dsl, "generated_files": generated_files}
