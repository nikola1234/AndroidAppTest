from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

import yaml

from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.agent.state import AgentState
from android_test_agent.dsl.generated_registry import output_name_from_case_path, source_case_key


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
        review_path = self._write_review_file(intent_dsl, state)
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
                f"Review {review_path}, then resume with:\n{self._resume_command(updated, review_path)}"
            )

        print("\nIntent DSL review required. Review file:")
        print(review_path)
        print(yaml.safe_dump(intent_dsl, allow_unicode=True, sort_keys=False))
        answer = self._input("Approve this intent DSL and continue? [y/N]: ").strip().lower()
        if answer not in {"y", "yes"}:
            raise HumanReviewRejected(
                "Intent DSL rejected. Edit the review YAML, then resume with:\n"
                f"{self._resume_command(updated, review_path)}"
            )

        review = {**review, "approved": True}
        metadata["human_review"] = review
        return {
            **updated,
            "human_review": review,
            "metadata": metadata,
        }

    def _write_review_file(self, intent_dsl: dict, state: AgentState) -> str:
        output_dir = self._config.reports_dir / "reviews"
        output_dir.mkdir(parents=True, exist_ok=True)
        metadata = state.get("metadata", {})
        test_name = output_name_from_case_path(
            metadata.get("source_case_path"),
            str(intent_dsl.get("name") or "intent_dsl"),
        )
        path = output_dir / f"{test_name}_intent_dsl.yaml"
        case_key = source_case_key(state.get("raw_case"))
        self._cleanup_previous_review(output_dir, case_key, path, intent_dsl)
        path.write_text(yaml.safe_dump(intent_dsl, allow_unicode=True, sort_keys=False), encoding="utf-8")
        self._remember_review(output_dir, case_key, path)
        return str(path)

    def _cleanup_previous_review(
        self,
        output_dir: Path,
        case_key: str | None,
        path: Path,
        intent_dsl: dict,
    ) -> None:
        registry = self._read_registry(output_dir)
        entry = registry.get(case_key or "")
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            self._delete_file(Path(entry["path"]))

        self._delete_file(path)
        legacy_name = self._safe_name(str(intent_dsl.get("name") or "intent_dsl"))
        self._delete_file(output_dir / f"{legacy_name}_intent_dsl.yaml")

        if case_key:
            registry.pop(case_key, None)
            self._write_registry(output_dir, registry)

    def _remember_review(self, output_dir: Path, case_key: str | None, path: Path) -> None:
        if not case_key:
            return
        registry = self._read_registry(output_dir)
        registry[case_key] = {"path": str(path)}
        self._write_registry(output_dir, registry)

    def _resume_command(self, state: AgentState, review_path: str) -> str:
        checkpoint_path = self._dsl_checkpoint_path(state)
        if not checkpoint_path:
            raise HumanReviewRejected(
                "Intent DSL rejected, but no DSL checkpoint was recorded. "
                f"Edit {review_path}, then rerun the case to regenerate a checkpoint."
            )
        return (
            f"python main.py --resume-from-checkpoint {self._quote(str(checkpoint_path))} "
            f"--approved-intent-dsl {self._quote(review_path)}"
        )

    def _dsl_checkpoint_path(self, state: AgentState) -> str | None:
        metadata = state.get("metadata", {})
        last_checkpoint = metadata.get("last_checkpoint")
        if isinstance(last_checkpoint, str) and last_checkpoint.endswith("_dsl.json"):
            return last_checkpoint

        checkpoint_files = metadata.get("checkpoint_files", [])
        if isinstance(checkpoint_files, list):
            for checkpoint_path in reversed(checkpoint_files):
                if isinstance(checkpoint_path, str) and checkpoint_path.endswith("_dsl.json"):
                    return checkpoint_path
        return None

    def _quote(self, value: str) -> str:
        return f'"{value.replace(chr(34), "`" + chr(34))}"'

    def _read_registry(self, output_dir: Path) -> dict[str, Any]:
        path = output_dir / ".review_cases.json"
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _write_registry(self, output_dir: Path, registry: dict[str, Any]) -> None:
        (output_dir / ".review_cases.json").write_text(
            json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _delete_file(self, path: Path) -> None:
        try:
            if path.exists() and path.is_file():
                path.unlink()
        except OSError:
            return

    def _safe_name(self, value: str) -> str:
        normalized = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
        return "_".join(part for part in normalized.split("_") if part) or "intent_dsl"
