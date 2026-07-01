from __future__ import annotations

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET
from typing import Any


@dataclass(slots=True)
class UIElement:
    """A normalized node from Android UI hierarchy XML."""

    resource_id: str = ""
    text: str = ""
    content_desc: str = ""
    class_name: str = ""
    clickable: bool = False
    enabled: bool = True
    bounds: str = ""

    @property
    def resource_name(self) -> str:
        return self.resource_id.rsplit("/", maxsplit=1)[-1]


@dataclass(slots=True)
class LocatorCandidate:
    locator: dict[str, str]
    score: float
    source: str
    element: UIElement
    reason: str


class UIHierarchyParser:
    """Parse Android hierarchy XML and rank locator candidates for intent targets."""

    def parse(self, xml_text: str) -> list[UIElement]:
        if not xml_text.strip():
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        elements: list[UIElement] = []
        for node in root.iter():
            attributes = node.attrib
            element = UIElement(
                resource_id=attributes.get("resource-id", ""),
                text=attributes.get("text", ""),
                content_desc=attributes.get("content-desc", ""),
                class_name=attributes.get("class", ""),
                clickable=attributes.get("clickable", "false").lower() == "true",
                enabled=attributes.get("enabled", "true").lower() == "true",
                bounds=attributes.get("bounds", ""),
            )
            if element.enabled and self._has_locator_signal(element):
                elements.append(element)
        return elements

    def find_candidates(
        self,
        xml_text: str,
        target: dict[str, Any],
        action: str | None = None,
        limit: int = 5,
    ) -> list[LocatorCandidate]:
        query = self._target_query(target)
        if not query:
            return []

        elements = self.parse(xml_text)
        locator_counts = self._locator_counts(elements)
        candidates: list[LocatorCandidate] = []
        for element in elements:
            score, reason = self._score(element, query, action)
            if score <= 0:
                continue
            for locator in self._locator_candidates(element):
                locator_score, locator_reason = self._locator_score(score, locator, locator_counts)
                candidates.append(
                    LocatorCandidate(
                        locator=locator,
                        score=locator_score,
                        source="ui_hierarchy",
                        element=element,
                        reason=f"{reason}; {locator_reason}",
                    )
                )

        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        return candidates[:limit]

    def _has_locator_signal(self, element: UIElement) -> bool:
        return bool(element.resource_id or element.text or element.content_desc)

    def _target_query(self, target: dict[str, Any]) -> str:
        parts = [
            str(target.get("name", "")),
            str(target.get("intent", "")),
            str(target.get("label", "")),
            str(target.get("description", "")),
        ]
        return " ".join(part for part in parts if part and part != "None")

    def _score(self, element: UIElement, query: str, action: str | None) -> tuple[float, str]:
        score = 0.0
        semantic_score = 0.0
        reasons: list[str] = []
        query_tokens = self._tokens(query)
        haystacks = {
            "resource-id": element.resource_name,
            "text": element.text,
            "content-desc": element.content_desc,
            "class": element.class_name,
        }

        for label, value in haystacks.items():
            if not value:
                continue
            value_tokens = self._tokens(value)
            overlap = query_tokens & value_tokens
            if overlap:
                weight = 0.35 if label == "resource-id" else 0.3
                match_score = weight * len(overlap)
                score += match_score
                semantic_score += match_score
                reasons.append(f"{label} token match: {', '.join(sorted(overlap))}")
            if self._normalized(query) and self._normalized(query) in self._normalized(value):
                score += 0.4
                semantic_score += 0.4
                reasons.append(f"{label} contains query")
            if self._normalized(value) and self._normalized(value) in self._normalized(query):
                score += 0.25
                semantic_score += 0.25
                reasons.append(f"query contains {label}")

        role_score, role_reason = self._role_score(element, action, query)
        score += role_score
        if role_reason:
            reasons.append(role_reason)

        if semantic_score <= 0 and role_score <= 0:
            return 0.0, ""

        if element.resource_id:
            score += 0.1
        if element.clickable and action == "tap":
            score += 0.15
            reasons.append("clickable tap target")

        return score, "; ".join(reasons)

    def _role_score(self, element: UIElement, action: str | None, query: str) -> tuple[float, str]:
        class_name = element.class_name.lower()
        normalized_query = self._normalized(query)
        if action == "input" and "edittext" in class_name:
            return 0.25, "input-like element"
        if "checkbox" in normalized_query and "checkbox" in class_name:
            return 0.25, "checkbox-like element"
        if "radio" in normalized_query and "radiobutton" in class_name:
            return 0.25, "radio-like element"
        if (
            ("toggle" in normalized_query or "switch" in normalized_query)
            and ("togglebutton" in class_name or "switch" in class_name)
        ):
            return 0.25, "toggle-like element"
        if action == "tap" and "button" in class_name:
            return 0.2, "tap-like element"
        return 0.0, ""

    def _locator_candidates(self, element: UIElement) -> list[dict[str, str]]:
        locators: list[dict[str, str]] = []
        ui_selector = self._android_uiautomator_selector(element)
        if ui_selector:
            locators.append({"by": "android_uiautomator", "value": ui_selector})
        if element.resource_id:
            locators.append({"by": "id", "value": element.resource_id})
        if element.content_desc:
            locators.append({"by": "accessibility_id", "value": element.content_desc})
        if element.text:
            locators.append({"by": "text", "value": element.text})
        return locators

    def _locator_counts(self, elements: list[UIElement]) -> dict[tuple[str, str], int]:
        counts: dict[tuple[str, str], int] = {}
        for element in elements:
            for locator in self._locator_candidates(element):
                key = (locator["by"], locator["value"])
                counts[key] = counts.get(key, 0) + 1
        return counts

    def _android_uiautomator_selector(self, element: UIElement) -> str:
        selectors: list[str] = []
        if element.resource_id:
            selectors.append(f'resourceId("{self._escape_uiselector_value(element.resource_id)}")')
        if element.text:
            selectors.append(f'text("{self._escape_uiselector_value(element.text)}")')
        elif element.content_desc:
            selectors.append(f'description("{self._escape_uiselector_value(element.content_desc)}")')
        elif element.class_name:
            selectors.append(f'className("{self._escape_uiselector_value(element.class_name)}")')
        if not selectors:
            return ""
        return "new UiSelector()." + ".".join(selectors)

    def _locator_score(
        self,
        base_score: float,
        locator: dict[str, str],
        locator_counts: dict[tuple[str, str], int],
    ) -> tuple[float, str]:
        count = locator_counts.get((locator["by"], locator["value"]), 0)
        score = base_score
        reasons = [f"locator by {locator['by']}"]

        if count == 1:
            score += 0.08
            reasons.append("unique current-page match")
        elif count > 1:
            score -= 0.12
            reasons.append(f"duplicated current-page match ({count})")
        else:
            reasons.append("uniqueness unknown")

        if locator["by"] == "android_uiautomator":
            condition_count = len(re.findall(r"\.(resourceId|text|description|className)\(", locator["value"]))
            if condition_count >= 2:
                score += 0.08
                reasons.append(f"combined UiSelector conditions ({condition_count})")
            else:
                score += 0.02
                reasons.append("single UiSelector condition")
        elif locator["by"] in {"id", "accessibility_id"}:
            score += 0.03
            reasons.append("stable native attribute")
        elif locator["by"] == "xpath":
            score -= 0.05
            reasons.append("xpath fallback")

        score = max(score, 0.0)
        return score / (1.0 + score), "; ".join(reasons)

    def _escape_uiselector_value(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _tokens(self, value: str) -> set[str]:
        normalized = self._normalized(value)
        if not normalized:
            return set()
        tokens = set(re.split(r"[^a-z0-9\u4e00-\u9fff]+", normalized))
        tokens.discard("")
        tokens.add(normalized)
        return tokens

    def _normalized(self, value: str) -> str:
        value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
        return value.replace("-", "_").replace("/", "_").replace(":", "_").lower().strip()
