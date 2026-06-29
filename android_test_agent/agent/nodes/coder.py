from __future__ import annotations

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.agent.nodes.codegen import CodegenNode
from android_test_agent.llm.base import LLMClient


class CoderNode(CodegenNode):
    """Backward-compatible alias for the code generation node."""

    def __init__(self, config: AndroidTestConfig, llm: LLMClient | None = None) -> None:
        super().__init__(config)
