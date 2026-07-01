"""Device and automation tools."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ADBTool": ("android_test_agent.tools.adb_tool", "ADBTool"),
    "AppiumTool": ("android_test_agent.tools.appium_tool", "AppiumTool"),
    "LocatorCandidate": ("android_test_agent.tools.ui_hierarchy_parser", "LocatorCandidate"),
    "LogcatTool": ("android_test_agent.tools.logcat_tool", "LogcatTool"),
    "ScreenshotTool": ("android_test_agent.tools.screenshot_tool", "ScreenshotTool"),
    "UIElement": ("android_test_agent.tools.ui_hierarchy_parser", "UIElement"),
    "UIHierarchyParser": ("android_test_agent.tools.ui_hierarchy_parser", "UIHierarchyParser"),
    "UIDumpTool": ("android_test_agent.tools.ui_dump_tool", "UIDumpTool"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
