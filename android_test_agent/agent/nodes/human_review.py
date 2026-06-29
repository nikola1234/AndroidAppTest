from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import yaml

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.agent.state import AgentState


class HumanReviewRejected(RuntimeError):
    """Raised when the user rejects the intent DSL during interactive review."""


class HumanReviewNode:
    """Optionally pause after intent DSL generation for human approval."""

    def __init__(
        self,
        config: AndroidTestConfig,
        input_func: Callable[[str], str] | None = None,
    ) -> None:
        self._config = config
        self._input = input_func or input

    def __call__(self, state: AgentState) -> AgentState:
        intent_dsl = state["intent_dsl"]
        review_path = self._write_review_file(intent_dsl)
        review = {
            "required": self._config.review_intent_dsl,
            "approved": not self._config.review_intent_dsl,
            "path": review_path,
        }

        artifacts = dict(state.get("artifacts", {}))
        artifacts["intent_dsl_review"] = review_path

        metadata = dict(state.get("metadata", {}))
        metadata["human_review"] = review

        updated: AgentState = {
            **state,
            "human_review": review,
            "artifacts": artifacts,
            "metadata": metadata,
        }
        if not self._config.review_intent_dsl:
            return updated

        if not sys.stdin.isatty():
            raise HumanReviewRejected(
                "Intent DSL review is required, but stdin is not interactive. "
                f"Review {review_path}, then rerun without --review-intent-dsl or resume from the DSL checkpoint."
            )

        print("\nIntent DSL review required. Review file:")
        print(review_path)
        print(yaml.safe_dump(intent_dsl, allow_unicode=True, sort_keys=False))
        answer = self._input("Approve this intent DSL and continue? [y/N]: ").strip().lower()
        if answer not in {"y", "yes"}:
            raise HumanReviewRejected(f"Intent DSL rejected. Edit the source case or review {review_path}.")

        review = {**review, "approved": True}
        metadata["human_review"] = review
        return {
            **updated,
            "human_review": review,
            "metadata": metadata,
        }

    def _write_review_file(self, intent_dsl: dict) -> str:
        output_dir = self._config.reports_dir / "reviews"
        output_dir.mkdir(parents=True, exist_ok=True)
        test_name = self._safe_name(str(intent_dsl.get("name") or "intent_dsl"))
        path = output_dir / f"{test_name}_intent_dsl.yaml"
        path.write_text(yaml.safe_dump(intent_dsl, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return str(path)

    def _safe_name(self, value: str) -> str:
        normalized = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
        return "_".join(part for part in normalized.split("_") if part) or "intent_dsl"
