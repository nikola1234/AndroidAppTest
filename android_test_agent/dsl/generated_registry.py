from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from android_test_agent.agent.config import AndroidTestConfig


class GeneratedFileRegistry:
    """Track generated files by source case so stale outputs can be removed."""

    def __init__(self, config: AndroidTestConfig) -> None:
        self._path = config.generated_dir / ".generated_cases.json"

    def cleanup_previous(self, case_key: str | None) -> None:
        if not case_key:
            return
        registry = self._read()
        entry = registry.get(case_key)
        if not isinstance(entry, dict):
            return
        for value in entry.get("files", {}).values():
            if isinstance(value, str):
                self._delete_file(value)
        registry.pop(case_key, None)
        self._write(registry)

    def remember(self, case_key: str | None, files: dict[str, str]) -> None:
        if not case_key:
            return
        registry = self._read()
        registry[case_key] = {"files": files}
        self._write(registry)

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, registry: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _delete_file(self, path_value: str) -> None:
        path = Path(path_value)
        try:
            if path.exists() and path.is_file():
                path.unlink()
        except OSError:
            return


def source_case_key(raw_case: str | None) -> str | None:
    if not raw_case:
        return None
    return hashlib.sha256(raw_case.encode("utf-8")).hexdigest()[:16]
