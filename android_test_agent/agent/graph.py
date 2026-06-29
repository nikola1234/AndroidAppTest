from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from android_test_agent.agent.checkpoint import StateCheckpointWriter, read_state_checkpoint
from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.agent.state import AgentState
from android_test_agent.executor.retry_policy import RetryPolicy

Node = Callable[[AgentState], AgentState]


class AgentGraph:
    """LangGraph workflow for Android test generation and execution."""

    def __init__(
        self,
        config: AndroidTestConfig,
        analyzer: Node,
        planner: Node,
        dsl: Node,
        human_review: Node,
        element: Node,
        codegen: Node,
        executor: Node,
        validator: Node,
        retrier: Node,
        wait_strategy: Node,
        debug: Node,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._config = config
        self._analyzer = analyzer
        self._planner = planner
        self._dsl = dsl
        self._human_review = human_review
        self._element = element
        self._codegen = codegen
        self._executor = executor
        self._validator = validator
        self._retrier = retrier
        self._wait_strategy = wait_strategy
        self._debug = debug
        self._retry_policy = retry_policy or RetryPolicy()
        self._checkpoint_writer = StateCheckpointWriter(config.checkpoint_dir)
        self._checkpointer_context: Any | None = None
        self._checkpointer: Any | None = None
        self._graph = self._build_graph()

    def run(self, raw_case: str, thread_id: str | None = None) -> AgentState:
        checkpoint_thread_id = thread_id or f"ata-{uuid4().hex}"
        state: AgentState = {
            "raw_case": raw_case,
            "retry_count": 0,
            "errors": [],
            "artifacts": {},
            "metadata": {
                "agent_version": "0.1.0",
                "checkpoint_thread_id": checkpoint_thread_id,
                "checkpoint_files": [],
            },
        }
        return self._graph.invoke(
            state,
            config={"configurable": {"thread_id": checkpoint_thread_id}},
        )

    def resume_from_checkpoint(
        self,
        checkpoint_path: str,
        thread_id: str | None = None,
    ) -> AgentState:
        checkpoint = read_state_checkpoint(checkpoint_path)
        state: AgentState = checkpoint["state"]
        metadata = dict(state.get("metadata", {}))
        checkpoint_thread_id = thread_id or str(metadata.get("checkpoint_thread_id") or checkpoint["thread_id"])
        start_at = self._next_node_after_checkpoint(checkpoint["node"], state)
        metadata["checkpoint_thread_id"] = checkpoint_thread_id
        metadata["resumed_from_checkpoint"] = checkpoint["path"]
        metadata["resumed_from_node"] = checkpoint["node"]
        metadata["resume_start_at"] = start_at
        metadata.setdefault("checkpoint_files", [])
        state = {**state, "metadata": metadata}
        if start_at == "end":
            return state
        return self._graph.invoke(
            state,
            config={"configurable": {"thread_id": checkpoint_thread_id}},
        )

    def close(self) -> None:
        """Release LangGraph checkpoint resources held by this graph."""

        if self._checkpointer_context is None:
            return
        self._checkpointer_context.__exit__(None, None, None)
        self._checkpointer_context = None
        self._checkpointer = None

    def _build_graph(self) -> Any:
        try:
            from langgraph.graph import END, StateGraph
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "LangGraph is required for AgentGraph. Run `pip install -r requirements.txt`."
            ) from exc

        graph = StateGraph(AgentState)
        graph.add_node("analyzer", self._checkpointed("analyzer", self._analyzer))
        graph.add_node("planner", self._checkpointed("planner", self._planner))
        graph.add_node("dsl", self._checkpointed("dsl", self._dsl))
        graph.add_node("human_review", self._checkpointed("human_review", self._human_review))
        graph.add_node("element", self._checkpointed("element", self._element))
        graph.add_node("codegen", self._checkpointed("codegen", self._codegen))
        graph.add_node("executor", self._checkpointed("executor", self._executor))
        graph.add_node("validator", self._checkpointed("validator", self._validator))
        graph.add_node("retrier", self._checkpointed("retrier", self._retrier))
        graph.add_node("wait_strategy", self._checkpointed("wait_strategy", self._wait_strategy))
        graph.add_node("debug", self._checkpointed("debug", self._debug))

        graph.set_conditional_entry_point(
            self._entry_point,
            {
                "analyzer": "analyzer",
                "planner": "planner",
                "dsl": "dsl",
                "human_review": "human_review",
                "element": "element",
                "codegen": "codegen",
                "executor": "executor",
                "validator": "validator",
                "retrier": "retrier",
                "wait_strategy": "wait_strategy",
                "debug": "debug",
                "end": END,
            },
        )
        graph.add_edge("analyzer", "planner")
        graph.add_edge("planner", "dsl")
        graph.add_edge("dsl", "human_review")
        graph.add_edge("human_review", "element")
        graph.add_edge("element", "codegen")
        graph.add_edge("codegen", "executor")
        graph.add_edge("executor", "validator")
        graph.add_conditional_edges(
            "validator",
            self._route_after_validation,
            {
                "locator": "retrier",
                "timeout": "wait_strategy",
                "assertion": "debug",
                "unknown": "debug",
                "end": END,
            },
        )
        graph.add_edge("retrier", "dsl")
        graph.add_edge("wait_strategy", "element")
        graph.add_edge("debug", "planner")
        return graph.compile(checkpointer=self._build_checkpointer())

    def _build_checkpointer(self) -> Any:
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "langgraph-checkpoint-sqlite is required. Run `pip install -r requirements.txt`."
            ) from exc

        self._config.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._checkpointer_context = SqliteSaver.from_conn_string(str(self._config.checkpoint_db_path))
        self._checkpointer = self._checkpointer_context.__enter__()
        if hasattr(self._checkpointer, "setup"):
            self._checkpointer.setup()
        return self._checkpointer

    def _checkpointed(self, node_name: str, node: Node) -> Node:
        def wrapped(state: AgentState) -> AgentState:
            updated = node(state)
            metadata = dict(updated.get("metadata", {}))
            thread_id = str(metadata.get("checkpoint_thread_id") or "default")
            checkpoint_path = self._checkpoint_writer.write(thread_id, node_name, updated)
            checkpoint_files = list(metadata.get("checkpoint_files", []))
            checkpoint_files.append(checkpoint_path)
            metadata["last_checkpoint"] = checkpoint_path
            metadata["checkpoint_files"] = checkpoint_files
            return {**updated, "metadata": metadata}

        return wrapped

    def _entry_point(self, state: AgentState) -> str:
        metadata = state.get("metadata", {})
        return str(metadata.get("resume_start_at") or "analyzer")

    def _next_node_after_checkpoint(self, node_name: str, state: AgentState) -> str:
        mapping = {
            "analyzer": "planner",
            "planner": "dsl",
            "dsl": "human_review",
            "human_review": "element",
            "element": "codegen",
            "codegen": "executor",
            "executor": "validator",
            "retrier": "dsl",
            "wait_strategy": "element",
            "debug": "planner",
        }
        if node_name == "validator":
            route = self._route_after_validation(state)
            return {
                "locator": "retrier",
                "timeout": "wait_strategy",
                "assertion": "debug",
                "unknown": "debug",
                "end": "end",
            }.get(route, "end")
        return mapping.get(node_name, "analyzer")

    def _route_after_validation(self, state: AgentState) -> str:
        validation = state.get("validation_result", {})
        if validation.get("passed"):
            return "end"

        retry_count = state.get("retry_count", 0)
        failure_type = validation.get("failure_type")
        if not self._retry_policy.should_retry(failure_type, retry_count, self._config.max_retries):
            return "end"
        if failure_type == "locator_not_found":
            return "locator"
        if failure_type == "timeout":
            return "timeout"
        if failure_type == "assertion":
            return "assertion"
        if failure_type == "unknown":
            return "unknown"
        return "end"
