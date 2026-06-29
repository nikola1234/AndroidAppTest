from __future__ import annotations

from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from android_test_agent.agent.config import AndroidTestConfig


APP_PACKAGE_RE = re.compile(
    r"(?:appPackage|app_package|packageName|包名)\s*[:：=]\s*"
    r"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)"
)
APP_ACTIVITY_RE = re.compile(
    r"(?:appActivity|app_activity|启动Activity|activity)\s*[:：=]\s*"
    r"([A-Za-z_.$][A-Za-z0-9_.$]*(?:/[A-Za-z_.$][A-Za-z0-9_.$]*)?)"
)

PLACEHOLDER_MARKERS = (
    "你的",
    "your_",
    "your-",
    "<",
    ">",
    "c:\\path\\to\\",
    "/path/to/",
)


def build_android_capabilities(
    config: AndroidTestConfig,
    dsl: dict[str, Any] | None = None,
    *,
    absolutize_app: bool = False,
) -> dict[str, Any]:
    """Build Appium capabilities from config, allowing case metadata to override app identity."""

    case_metadata = extract_app_metadata(dsl)
    device_name = clean_optional_value(config.device_name) or "Android Emulator"
    app_package = case_metadata.get("app_package") or clean_optional_value(config.app_package)
    app_activity = case_metadata.get("app_activity") or clean_optional_value(config.app_activity)
    apk_path = clean_optional_value(config.apk_path) if config.reinstall_app else None

    capabilities: dict[str, Any] = {
        "platformName": config.platform_name,
        "appium:automationName": "UiAutomator2",
        "appium:deviceName": device_name,
    }
    if app_package:
        capabilities["appium:appPackage"] = app_package
    if app_activity:
        capabilities["appium:appActivity"] = app_activity
    if apk_path:
        capabilities["appium:app"] = _app_path(config, apk_path, absolutize_app=absolutize_app)
        capabilities["appium:enforceAppInstall"] = True
    return capabilities


def extract_app_metadata(dsl: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(dsl, dict):
        return {}

    text = "\n".join(
        str(value)
        for value in (
            dsl.get("name"),
            dsl.get("description"),
            dsl.get("app_package"),
            dsl.get("app_activity"),
        )
        if value
    )
    metadata: dict[str, str] = {}
    package_match = APP_PACKAGE_RE.search(text)
    activity_match = APP_ACTIVITY_RE.search(text)
    if package_match:
        metadata["app_package"] = package_match.group(1)
    if activity_match:
        metadata["app_activity"] = activity_match.group(1)
    return metadata


def clean_optional_value(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned or _looks_like_placeholder(cleaned):
        return None
    return cleaned


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.lower()
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def _app_path(config: AndroidTestConfig, apk_path: str, *, absolutize_app: bool) -> str:
    path = Path(apk_path)
    if not path.is_absolute():
        path = Path(config.project_root) / path
    path = _resolve_apk_path(path)
    if not absolutize_app:
        try:
            path = path.relative_to(config.project_root)
        except ValueError:
            pass
    return str(path)


def _resolve_apk_path(path: Path) -> Path:
    if path.is_dir():
        apks = sorted(path.glob("*.apk"))
        if not apks:
            raise FileNotFoundError(f"No APK files found in {path}")
        if len(apks) > 1:
            raise ValueError(f"Multiple APK files found in {path}; set ANDROID_APK_PATH to one APK file")
        return apks[0]
    if not path.exists():
        raise FileNotFoundError(f"APK path does not exist: {path}")
    if path.suffix.lower() != ".apk":
        raise ValueError(f"ANDROID_APK_PATH must point to an APK file or a directory containing one APK: {path}")
    return path
