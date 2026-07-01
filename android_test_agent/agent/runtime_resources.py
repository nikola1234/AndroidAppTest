from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any


RESOURCE_DIR = Path(__file__).with_name("runtime_skills") / "resources"


@lru_cache(maxsize=16)
def load_runtime_resource(name: str) -> dict[str, Any]:
    safe_name = "".join(char for char in name if char.isalnum() or char in {"-", "_"})
    path = RESOURCE_DIR / f"{safe_name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def supported_actions() -> dict[str, dict[str, Any]]:
    data = load_runtime_resource("supported_actions")
    actions = data.get("actions", {})
    return actions if isinstance(actions, dict) else {}
