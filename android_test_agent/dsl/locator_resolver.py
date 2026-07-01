from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from android_test_agent.agent.runtime_skills import RuntimeSkillLoader
from android_test_agent.agent.config import AndroidTestConfig
from android_test_agent.memory.element_memory import ElementMemory
from android_test_agent.tools.ui_hierarchy_parser import LocatorCandidate, UIHierarchyParser


class LocatorResolutionError(RuntimeError):
    """Raised when an intent-level target cannot be resolved on the current page."""


@dataclass(slots=True)
class LocatorMatch:
    locator: dict[str, str]
    score: float
    source: str
    reason: str
    metadata: dict[str, Any]


class LocatorResolver:
    """Resolve intent-level DSL targets into concrete Android locators."""

    def __init__(
        self,
        config: AndroidTestConfig,
        element_memory: ElementMemory | None = None,
        parser: UIHierarchyParser | None = None,
        llm: Any | None = None,
        manual_mapping_path: str | Path | None = None,
    ) -> None:
        self._config = config
        self._element_memory = element_memory or ElementMemory(
            config.knowledge_dir / "elements" / "element_memory.json"
        )
        self._parser = parser or UIHierarchyParser()
        self._llm = llm
        self._skills = RuntimeSkillLoader()
        self._manual_mapping_path = Path(manual_mapping_path) if manual_mapping_path else (
            config.project_root / "config" / "elements.yaml"
        )
        self._manual_mappings = self._load_manual_mappings()

    def resolve_target(
        self,
        target: Any,
        *,
        page_source: str = "",
        action: str | None = None,
    ) -> dict[str, Any]:
        existing = self._existing_locator(target)
        if existing and self._locator_allowed_for_app(existing):
            return self._with_existing_locator(target, existing, page_source=page_source, action=action)

        query = self._target_query(target)
        if not query:
            raise LocatorResolutionError(f"Target has no resolvable name or intent: {target!r}")

        matches: list[LocatorMatch] = []
        matches.extend(self._manual_matches(target, query))
        matches.extend(self._memory_matches(query))
        matches.extend(self._ui_matches(page_source, self._target_dict(target), action))

        if not matches:
            raise LocatorResolutionError(f"No locator candidates found for target '{query}'")

        matches.sort(key=lambda match: match.score, reverse=True)
        selected = self._select_with_llm(query, matches) or matches[0]
        return self._with_locator(
            target,
            selected.locator,
            selected.source,
            selected.score,
            selected.reason,
            selected.metadata,
            self._ordered_candidates(matches, selected),
        )

    def _with_existing_locator(
        self,
        target: Any,
        locator: dict[str, str],
        *,
        page_source: str,
        action: str | None,
    ) -> dict[str, Any]:
        target_dict = self._target_dict(target)
        if target_dict.get("locator_candidates"):
            return self._with_locator(target, locator, "provided", 1.0, "target already has locator")

        selected = LocatorMatch(
            locator=locator,
            score=1.0,
            source="provided",
            reason="target already has locator",
            metadata={},
        )
        matches = [selected]
        query = self._target_query(target)
        if query and page_source:
            matches.extend(self._ui_matches(page_source, target_dict, action))
        return self._with_locator(
            target,
            locator,
            "provided",
            1.0,
            "target already has locator",
            candidates=self._ordered_candidates(matches, selected),
        )

    def remember(
        self,
        target: Any,
        *,
        action: str | None = None,
        page_source: str = "",
    ) -> None:
        target_dict = self._target_dict(target)
        locator = target_dict.get("locator")
        if not self._is_locator(locator):
            return
        name = str(target_dict.get("name") or self._infer_name(locator["value"]))
        item = {
            "name": name,
            "intent": target_dict.get("intent", ""),
            "aliases": [alias for alias in [target_dict.get("label"), target_dict.get("description")] if alias],
            "locator": locator,
            "action": action,
            "source": target_dict.get("locator_source", "runtime"),
            "score": target_dict.get("locator_score"),
            "app_package": self._config.app_package,
            "locator_package": self._locator_package(locator),
            "page_hash": self._page_hash(page_source),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._element_memory.add(item)

    def _existing_locator(self, target: Any) -> dict[str, str] | None:
        if isinstance(target, dict):
            locator = target.get("locator")
            if self._is_locator(locator):
                return {"by": str(locator["by"]), "value": str(locator["value"])}
            if self._is_locator(target):
                return {"by": str(target["by"]), "value": str(target["value"])}
        if isinstance(target, str) and self._looks_like_locator_value(target):
            return {"by": "id", "value": target}
        return None

    def _with_locator(
        self,
        target: Any,
        locator: dict[str, str],
        source: str,
        score: float,
        reason: str,
        metadata: dict[str, Any] | None = None,
        candidates: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        target_dict = self._target_dict(target)
        target_dict["locator"] = locator
        target_dict["locator_source"] = source
        target_dict["locator_score"] = round(score, 3)
        target_dict["locator_reason"] = reason
        if candidates is not None:
            target_dict["locator_candidates"] = candidates
        if metadata:
            target_dict["locator_metadata"] = metadata
        return target_dict

    def _ordered_candidates(
        self,
        matches: list[LocatorMatch],
        selected: LocatorMatch,
    ) -> list[dict[str, Any]]:
        ordered = [selected, *[match for match in matches if match is not selected]]
        candidates: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for match in ordered:
            key = (match.locator["by"], match.locator["value"])
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "locator": match.locator,
                    "source": match.source,
                    "score": round(match.score, 3),
                    "reason": match.reason,
                    "metadata": match.metadata,
                }
            )
        return candidates

    def _manual_matches(self, target: Any, query: str) -> list[LocatorMatch]:
        target_dict = self._target_dict(target)
        target_name = str(target_dict.get("name", "")).lower()
        query_lower = query.lower()
        matches: list[LocatorMatch] = []
        for item in self._manual_mappings:
            locator = item.get("locator")
            if not self._is_locator(locator):
                continue
            normalized_locator = {"by": str(locator["by"]), "value": str(locator["value"])}
            if not self._locator_allowed_for_app(normalized_locator):
                continue
            names = [str(item.get("name", "")), *[str(alias) for alias in item.get("aliases", [])]]
            normalized_names = [name.lower() for name in names if name]
            if target_name and target_name in normalized_names:
                score = 1.0
                reason = "manual exact name match"
            elif any(name and name in query_lower for name in normalized_names):
                score = 0.95
                reason = "manual alias match"
            elif any(token in " ".join(normalized_names) for token in query_lower.split()):
                score = 0.8
                reason = "manual token match"
            else:
                continue
            matches.append(
                LocatorMatch(
                    locator=normalized_locator,
                    score=score,
                    source="manual_mapping",
                    reason=reason,
                    metadata={"name": item.get("name"), "aliases": item.get("aliases", [])},
                )
            )
        return matches

    def _memory_matches(self, query: str) -> list[LocatorMatch]:
        matches: list[LocatorMatch] = []
        for item in self._element_memory.search(query, limit=5):
            locator = item.get("locator")
            if not self._is_locator(locator):
                continue
            normalized_locator = {"by": str(locator["by"]), "value": str(locator["value"])}
            if not self._memory_item_allowed_for_app(item, normalized_locator):
                continue
            matches.append(
                LocatorMatch(
                    locator=normalized_locator,
                    score=float(item.get("score") or 0.85),
                    source="element_memory",
                    reason="historical element memory match",
                    metadata={
                        key: item.get(key)
                        for key in (
                            "name",
                            "intent",
                            "aliases",
                            "app_package",
                            "locator_package",
                            "page_hash",
                        )
                    },
                )
            )
        return matches

    def _ui_matches(self, page_source: str, target: dict[str, Any], action: str | None) -> list[LocatorMatch]:
        candidates = self._parser.find_candidates(page_source, target, action=action, limit=5)
        return [self._from_ui_candidate(candidate) for candidate in candidates]

    def _from_ui_candidate(self, candidate: LocatorCandidate) -> LocatorMatch:
        return LocatorMatch(
            locator=candidate.locator,
            score=candidate.score,
            source=candidate.source,
            reason=candidate.reason,
            metadata={
                "resource_id": candidate.element.resource_id,
                "text": candidate.element.text,
                "content_desc": candidate.element.content_desc,
                "class": candidate.element.class_name,
                "bounds": candidate.element.bounds,
                "clickable": candidate.element.clickable,
                "enabled": candidate.element.enabled,
            },
        )

    def _select_with_llm(self, query: str, matches: list[LocatorMatch]) -> LocatorMatch | None:
        if not self._llm or len(matches) <= 1:
            return None
        payload = [
            {
                "index": index,
                "locator": match.locator,
                "source": match.source,
                "score": match.score,
                "reason": match.reason,
                "metadata": match.metadata,
            }
            for index, match in enumerate(matches)
        ]
        system_prompt = self._skills.compose(
            "locator",
            "tools",
            references=["locator_candidate_scoring"] if self._needs_locator_reference(matches) else None,
            resources=["locator_sources"],
            task_prompt=(
                "Choose the best Android locator candidate for the target. "
                "Return strict JSON: {\"index\": number}."
            ),
        )
        user_prompt = f"Target: {query}\nCandidates:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        try:
            result = self._llm.complete_json(system_prompt, user_prompt)
        except Exception:
            return None
        index = result.get("index")
        if isinstance(index, int) and 0 <= index < len(matches):
            return matches[index]
        return None

    def _needs_locator_reference(self, matches: list[LocatorMatch]) -> bool:
        if len(matches) >= 4:
            return True
        if len(matches) < 2:
            return False
        return abs(matches[0].score - matches[1].score) <= 0.15

    def _load_manual_mappings(self) -> list[dict[str, Any]]:
        if not self._manual_mapping_path.exists():
            return []
        data = yaml.safe_load(self._manual_mapping_path.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict) and "elements" in data:
            data = data["elements"]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if not isinstance(data, dict):
            return []

        items: list[dict[str, Any]] = []
        for name, value in data.items():
            if isinstance(value, dict) and "locator" in value:
                item = dict(value)
                item.setdefault("name", name)
            elif self._is_locator(value):
                item = {"name": name, "locator": value}
            elif isinstance(value, dict) and ("by" in value or "value" in value):
                item = {"name": name, "locator": value}
            else:
                continue
            items.append(item)
        return items

    def _target_query(self, target: Any) -> str:
        target_dict = self._target_dict(target)
        parts = [
            target_dict.get("name"),
            target_dict.get("intent"),
            target_dict.get("label"),
            target_dict.get("description"),
        ]
        return " ".join(str(part) for part in parts if part)

    def _target_dict(self, target: Any) -> dict[str, Any]:
        if isinstance(target, dict):
            return dict(target)
        if isinstance(target, str):
            return {"name": self._infer_name(target), "intent": target}
        return {"name": self._infer_name(str(target)), "intent": str(target)}

    def _is_locator(self, value: Any) -> bool:
        return isinstance(value, dict) and bool(value.get("by")) and bool(value.get("value"))

    def _memory_item_allowed_for_app(self, item: dict[str, Any], locator: dict[str, str]) -> bool:
        expected_package = self._config.app_package
        if not expected_package:
            return True

        memory_package = item.get("app_package")
        if memory_package and memory_package != expected_package:
            return False

        return self._locator_allowed_for_app(locator)

    def _locator_allowed_for_app(self, locator: dict[str, str]) -> bool:
        expected_package = self._config.app_package
        locator_package = self._locator_package(locator)
        if not expected_package or not locator_package:
            return True
        return locator_package in {expected_package, "android"}

    def _locator_package(self, locator: dict[str, str]) -> str | None:
        value = str(locator.get("value") or "")
        resource_id = value if locator.get("by") == "id" else ""
        if not resource_id:
            match = re.search(r'resourceId\("([^"]+)"\)', value)
            if match:
                resource_id = match.group(1)
        if not resource_id:
            match = re.search(r"@resource-id\s*=\s*['\"]([^'\"]+)['\"]", value)
            if match:
                resource_id = match.group(1)
        if ":id/" not in resource_id:
            return None
        return resource_id.split(":id/", maxsplit=1)[0]

    def _looks_like_locator_value(self, value: str) -> bool:
        return ":id/" in value or value.startswith("/") or value.startswith("//*[@")

    def _infer_name(self, value: str) -> str:
        candidate = value.strip().split("/")[-1].split(":")[-1]
        normalized = "".join(char.lower() if char.isalnum() else "_" for char in candidate)
        return "_".join(part for part in normalized.split("_") if part) or "target"

    def _page_hash(self, page_source: str) -> str:
        if not page_source:
            return ""
        return hashlib.sha256(page_source.encode("utf-8")).hexdigest()[:16]
