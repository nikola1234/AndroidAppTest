from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any


class RuntimeSkillLoader:
    """Load markdown prompt skills used by runtime LLM calls."""

    def __init__(self, skill_dir: str | Path | None = None) -> None:
        self._skill_dir = Path(skill_dir) if skill_dir else Path(__file__).with_name("runtime_skills")

    def compose(
        self,
        *names: str,
        task_prompt: str,
        references: list[str] | tuple[str, ...] | None = None,
        resources: list[str] | tuple[str, ...] | None = None,
    ) -> str:
        sections = [self.load("system"), self.load("common")]
        sections.extend(self.load(name) for name in names)
        sections.extend(self.load_reference(name) for name in references or [])
        sections.extend(self.format_resource(name) for name in resources or [])
        sections.append("# Task Instructions\n\n" + task_prompt.strip())
        return "\n\n---\n\n".join(section for section in sections if section.strip())

    @lru_cache(maxsize=32)
    def load(self, name: str) -> str:
        safe_name = "".join(char for char in name if char.isalnum() or char in {"-", "_"})
        path = self._skill_dir / f"{safe_name}.md"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    @lru_cache(maxsize=32)
    def load_resource(self, name: str) -> dict[str, Any]:
        safe_name = "".join(char for char in name if char.isalnum() or char in {"-", "_"})
        path = self._skill_dir / "resources" / f"{safe_name}.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def format_resource(self, name: str) -> str:
        data = self.load_resource(name)
        if not data:
            return ""
        return "# Runtime Resource: " + name + "\n\n```json\n" + json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ) + "\n```"

    @lru_cache(maxsize=32)
    def load_reference(self, name: str) -> str:
        safe_name = "".join(char for char in name if char.isalnum() or char in {"-", "_"})
        path = self._skill_dir / "references" / f"{safe_name}.md"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()
