from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    devin_api_key: str = ""
    devin_org_id: str = ""
    devin_api_base_url: str = "https://api.devin.ai/v3"
    devin_live_enabled: bool = False

    github_token: str = ""
    github_webhook_secret: str = ""
    github_scan_repositories: str = ""
    remediate_label: str = "devin-remediate"
    scheduled_label: str = "devin-scheduled"

    database_url: str = "sqlite:///./data/app.db"

    max_active_sessions: int = 3
    max_retries: int = 3
    max_ci_repair_attempts: int = 2
    max_ci_non_code_failures: int = 3
    devin_session_timeout_minutes: int = 60

    max_acu_per_task: int | None = None
    daily_acu_cap: int | None = None

    devin_session_poll_interval_seconds: int = 15
    devin_poll_max_failures: int = 10

    devin_remediation_playbook_id: str = ""

    devin_scheduled_enabled: bool = False
    devin_schedule_cron: str = "0 9 * * 1-5"
    devin_automation_id: str = ""
    devin_schedule_id: str = ""
    orchestrator_public_url: str = ""
    scheduled_intake_token: str = ""

    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def github_scan_repositories_list(self) -> list[str]:
        if not self.github_scan_repositories.strip():
            return []
        return [
            repo.strip()
            for repo in self.github_scan_repositories.split(",")
            if repo.strip()
        ]

    @field_validator("max_acu_per_task", "daily_acu_cap", mode="before")
    @classmethod
    def parse_optional_int(cls, value: str | int | None) -> int | None:
        if value is None or value == "":
            return None
        return int(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
