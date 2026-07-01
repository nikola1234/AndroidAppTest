from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AndroidTestConfig:
    """Runtime configuration for the Android test agent."""

    project_root: Path = Path(".")
    generated_dir: Path = Path("generated")
    artifacts_dir: Path = Path("artifacts")
    reports_dir: Path = Path("reports")
    checkpoint_dir: Path = Path("reports/checkpoints")
    checkpoint_db_path: Path = Path("reports/checkpoints/langgraph.sqlite")
    knowledge_dir: Path = Path("knowledge")

    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-chat"
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.deepseek.com"
    llm_temperature: float = 0.2
    llm_log_calls: bool = True

    appium_server_url: str = "http://127.0.0.1:4723"
    platform_name: str = "Android"
    device_name: str = "Android Emulator"
    app_package: str | None = None
    app_activity: str | None = None
    apk_path: str | None = None
    reinstall_app: bool = False
    implicit_wait_seconds: int = 3
    explicit_wait_seconds: int = 15

    execute_generated_tests: bool = False
    max_retries: int = 1
    review_intent_dsl: bool = False
    llm_codegen_enabled: bool = False

    @classmethod
    def from_env(cls, project_root: str | Path = ".") -> "AndroidTestConfig":
        root = Path(project_root).resolve()
        return cls(
            project_root=root,
            generated_dir=root / os.getenv("ATA_GENERATED_DIR", "generated"),
            artifacts_dir=root / os.getenv("ATA_ARTIFACTS_DIR", "artifacts"),
            reports_dir=root / os.getenv("ATA_REPORTS_DIR", "reports"),
            checkpoint_dir=root / os.getenv("ATA_CHECKPOINT_DIR", "reports/checkpoints"),
            checkpoint_db_path=root
            / os.getenv("ATA_CHECKPOINT_DB_PATH", "reports/checkpoints/langgraph.sqlite"),
            knowledge_dir=root / os.getenv("ATA_KNOWLEDGE_DIR", "knowledge"),
            llm_provider=os.getenv("ATA_LLM_PROVIDER", "deepseek"),
            llm_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            llm_api_key=os.getenv("DEEPSEEK_API_KEY"),
            llm_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            llm_temperature=float(os.getenv("ATA_LLM_TEMPERATURE", "0.2")),
            llm_log_calls=os.getenv("ATA_LLM_LOG_CALLS", "true").lower() in {"1", "true", "yes"},
            appium_server_url=os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723"),
            platform_name=os.getenv("ANDROID_PLATFORM_NAME", "Android"),
            device_name=os.getenv("ANDROID_DEVICE_NAME", "Android Emulator"),
            app_package=os.getenv("ANDROID_APP_PACKAGE"),
            app_activity=os.getenv("ANDROID_APP_ACTIVITY"),
            apk_path=os.getenv("ANDROID_APK_PATH"),
            reinstall_app=os.getenv("ANDROID_REINSTALL_APP", "false").lower()
            in {"1", "true", "yes"},
            implicit_wait_seconds=int(os.getenv("ATA_IMPLICIT_WAIT_SECONDS", "3")),
            explicit_wait_seconds=int(os.getenv("ATA_EXPLICIT_WAIT_SECONDS", "15")),
            execute_generated_tests=os.getenv("ATA_EXECUTE_GENERATED_TESTS", "false").lower()
            in {"1", "true", "yes"},
            max_retries=int(os.getenv("ATA_MAX_RETRIES", "1")),
            review_intent_dsl=os.getenv("ATA_REVIEW_INTENT_DSL", "false").lower() in {"1", "true", "yes"},
            llm_codegen_enabled=os.getenv("ATA_LLM_CODEGEN_ENABLED", "false").lower()
            in {"1", "true", "yes"},
        )

    def ensure_directories(self) -> None:
        for path in [
            self.generated_dir,
            self.artifacts_dir,
            self.artifacts_dir / "screenshots",
            self.artifacts_dir / "ui_dumps",
            self.artifacts_dir / "logcat",
            self.artifacts_dir / "appium_logs",
            self.artifacts_dir / "generated_code",
            self.artifacts_dir / "traces",
            self.reports_dir,
            self.checkpoint_dir,
            self.checkpoint_db_path.parent,
            self.knowledge_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)
