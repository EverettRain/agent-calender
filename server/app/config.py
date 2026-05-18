from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Check CWD/.env (dev: cd server) AND parent/.env (production:
        # WorkingDirectory=app_src/ where the canonical .env lives at ../).
        # Later entries take precedence in pydantic-settings.
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    API_TOKEN: str = Field(..., min_length=8)

    DEEPSEEK_API_KEY: str = Field(..., min_length=8)
    DEEPSEEK_MODEL: str = "deepseek-v4-pro"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    DATABASE_URL: str = "sqlite+aiosqlite:///./data/data.db"

    TZ: str = "Asia/Shanghai"

    EXTRACTION_MAX_ATTEMPTS: int = Field(3, ge=1, le=10)
    EXTRACTION_VERIFY_ENABLED: bool = True
    EXTRACTION_VERIFY_MODEL: str = "deepseek-v4-flash"
    EXTRACTION_TOKEN_BUDGET_PER_INGEST: int = Field(8000, ge=500)

    DEFAULT_EVENT_OFFSETS_MINUTES: str = "0"
    DEFAULT_DEADLINE_OFFSETS_MINUTES: str = "1440,60"

    HOST: str = "127.0.0.1"
    PORT: int = 8080
    LOG_LEVEL: str = "INFO"

    # Notification scheduler
    SCHEDULER_ENABLED: bool = True
    NOTIFY_TICK_SECONDS: int = Field(60, ge=1, le=3600)

    # CORS — Electron renderer + (future) web ingest endpoints need cross-origin.
    # Default is permissive because we auth by bearer token (no cookies, no CSRF
    # surface). Tighten via env if you ever expose to anonymous browsers.
    CORS_ALLOW_ORIGINS: str = "*"

    def cors_origin_list(self) -> list[str]:
        raw = self.CORS_ALLOW_ORIGINS.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @field_validator("DEFAULT_EVENT_OFFSETS_MINUTES", "DEFAULT_DEADLINE_OFFSETS_MINUTES")
    @classmethod
    def _validate_offsets_csv(cls, v: str) -> str:
        if not v.strip():
            return ""
        for part in v.split(","):
            n = int(part.strip())
            if n < 0:
                raise ValueError(f"offset must be non-negative: {n}")
        return v

    def default_offsets(self, kind: str) -> list[int]:
        raw = (
            self.DEFAULT_EVENT_OFFSETS_MINUTES
            if kind == "event"
            else self.DEFAULT_DEADLINE_OFFSETS_MINUTES
        )
        if not raw.strip():
            return []
        return sorted({int(p.strip()) for p in raw.split(",") if p.strip()})


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
