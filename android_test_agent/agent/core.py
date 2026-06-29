from __future__ import annotations

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.agent.graph import AgentGraph
from android_test_agent.agent.nodes import (
    AnalyzerNode,
    CodegenNode,
    DebugNode,
    DslNode,
    ElementNode,
    ExecutorNode,
    HumanReviewNode,
    LlmCodegenNode,
    PlannerNode,
    RetrierNode,
    ValidatorNode,
    WaitStrategyNode,
)
from android_test_agent.agent.state import AgentState
from android_test_agent.llm.base import LLMClient


class AndroidTestAgent:
    """Orchestrates the Android test generation and execution workflow."""

    def __init__(self, config: AndroidTestConfig, llm: LLMClient | None = None) -> None:
        self._config = config
        self._config.ensure_directories()
        self._llm = llm or self._build_llm(config)

        self._graph = AgentGraph(
            config=config,
            analyzer=AnalyzerNode(self._llm),
            planner=PlannerNode(self._llm),
            dsl=DslNode(self._llm),
            human_review=HumanReviewNode(config),
            element=ElementNode(config, self._llm),
            codegen=self._build_codegen_node(config),
            executor=ExecutorNode(config),
            validator=ValidatorNode(),
            retrier=RetrierNode(),
            wait_strategy=WaitStrategyNode(),
            debug=DebugNode(),
        )

    def run(self, raw_case: str, thread_id: str | None = None) -> AgentState:
        return self._graph.run(raw_case, thread_id=thread_id)

    def resume_from_checkpoint(self, checkpoint_path: str, thread_id: str | None = None) -> AgentState:
        return self._graph.resume_from_checkpoint(checkpoint_path, thread_id=thread_id)

    def _build_llm(self, config: AndroidTestConfig) -> LLMClient | None:
        if config.llm_provider == "deepseek" and config.llm_api_key:
            from android_test_agent.llm.deepseek_client import DeepSeekClient

            return DeepSeekClient(config)
        return None

    def _build_codegen_node(self, config: AndroidTestConfig):
        if config.llm_codegen_enabled:
            return LlmCodegenNode(config, self._llm)
        return CodegenNode(config)
