from __future__ import annotations

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.agent.state import AgentState
from android_test_agent.executor.dsl_executor import PytestExecutor


class ExecutorNode:
    """Run generated tests, or perform a dry-run when no device is configured."""

    def __init__(self, config: AndroidTestConfig) -> None:
        self._executor = PytestExecutor(config)

    def __call__(self, state: AgentState) -> AgentState:
        test_path = state["generated_files"]["pytest"]
        result = self._executor.run(test_path)
        return {**state, "execution_result": result}
