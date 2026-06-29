from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from android_test_agent.agent.state import AgentState


class StateCheckpointWriter:
    """Persist readable per-node state snapshots alongside LangGraph checkpoints."""

    def __init__(self, checkpoint_dir: str | Path) -> None:
        self._checkpoint_dir = Path(checkpoint_dir)
        self._step = 0

    def write(self, thread_id: str, node_name: str, state: AgentState) -> str:
        output_dir = self._checkpoint_dir / self._safe_name(thread_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        self._step = max(self._step, self._latest_step(output_dir)) + 1
        path = output_dir / f"{self._step:03d}_{node_name}.json"
        payload = {
            "thread_id": thread_id,
            "node": node_name,
            "step": self._step,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "summary": self._summary(state),
            "state": self._sanitize(state),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def _summary(self, state: AgentState) -> dict[str, Any]:
        validation = state.get("validation_result", {})
        artifacts = state.get("artifacts", {})
        return {
            "name": state.get("dsl", {}).get("name") or state.get("plan", {}).get("name"),
            "retry_count": state.get("retry_count", 0),
            "generated_files": state.get("generated_files"),
            "execution_status": state.get("execution_result", {}).get("status"),
            "failure_type": validation.get("failure_type"),
            "passed": validation.get("passed"),
            "page_source": artifacts.get("page_source") or artifacts.get("element_node_ui_dump"),
            "screenshot": artifacts.get("screenshot"),
        }

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._sanitize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        if isinstance(value, tuple):
            return [self._sanitize(item) for item in value]
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return repr(value)

    def _safe_name(self, value: str) -> str:
        return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value) or "default"

    def _latest_step(self, output_dir: Path) -> int:
        latest = 0
        for path in output_dir.glob("*.json"):
            prefix = path.stem.split("_", maxsplit=1)[0]
            if prefix.isdigit():
                latest = max(latest, int(prefix))
        return latest


def read_state_checkpoint(path: str | Path) -> dict[str, Any]:
    """Read a JSON checkpoint written by StateCheckpointWriter."""

    checkpoint_path = Path(path)
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    state = payload.get("state")
    if not isinstance(state, dict):
        raise ValueError(f"Checkpoint does not contain a state object: {checkpoint_path}")
    return {
        "path": str(checkpoint_path),
        "thread_id": str(payload.get("thread_id") or "default"),
        "node": str(payload.get("node") or ""),
        "step": payload.get("step"),
        "state": state,
    }
