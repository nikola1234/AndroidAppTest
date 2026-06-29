from __future__ import annotations

from copy import deepcopy
from typing import Any


class RetryPolicy:
    """Conservative retry strategy for generated Android tests."""

    def should_retry(self, failure_type: str | None, retry_count: int, max_retries: int) -> bool:
        if retry_count >= max_retries:
            return False
        return failure_type in {"locator_not_found", "timeout", "assertion", "unknown"}

    def repair_dsl(self, dsl: dict[str, Any], failure_type: str | None) -> dict[str, Any]:
        if failure_type == "timeout":
            return self._add_wait_before_actions(dsl)
        return dsl

    def _add_wait_before_actions(self, dsl: dict[str, Any]) -> dict[str, Any]:
        updated = deepcopy(dsl)
        new_steps = []
        for step in updated["steps"]:
            if step.get("action") in {"tap", "input", "assert_visible"} and step.get("target"):
                wait_step = {"action": "wait_visible", "target": step["target"]}
                if not new_steps or new_steps[-1] != wait_step:
                    new_steps.append(wait_step)
            new_steps.append(step)
        updated["steps"] = new_steps
        return updated
