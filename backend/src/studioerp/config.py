"""Application configuration (kernel k0).

Pydantic settings loaded from ``backend/.env`` then ``../.env`` (repo root),
with a production guard rejecting weak secrets. Single cached instance via
:func:`get_settings`.

Ported from the reference monolith ``app/core/config.py`` with behaviour
intact.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_repo_root = Path(__file__).resolve().parents[3]  # studioerp-v2/ (repo root, holds top-level .env)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_repo_root / ".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "StudioERP API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    jwt_issuer: str = "studioerp"
    jwt_audience: str = "studioerp-api"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"

    cors_origins: str = "*"

    first_superuser_email: str = "admin@studioerp.dev"
    first_superuser_password: str = "change-me"

    upload_dir: str = "/app/uploads"

    login_max_attempts: int = 5
    login_rate_window_seconds: int = 300
    seed_demo: bool = False
    gzip_min_size: int = 1024

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@studioerp.dev"
    email_enabled: bool = False
    smtp_timeout_seconds: int = 30

    frontend_url: str = "https://studioerp.dev"

    supabase_url: str = ""
    supabase_key: str = ""
    supabase_storage_bucket: str = "studio-erp-uploads"
    storage_timeout_seconds: int = 30

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/backup/google/callback"
    backup_ui_redirect: str = "http://localhost:5173/settings?tab=backup"

    timesheet_reminder_enabled: bool = True
    timesheet_reminder_hour: int = 17
    timesheet_autosubmit_enabled: bool = True
    timesheet_autosubmit_hour: int = 9

    security_headers_enabled: bool = False

    @model_validator(mode="after")
    def _guard_production(self) -> "Settings":
        if self.environment.lower() == "production":
            if not self.secret_key or self.secret_key in {"change-me-in-production", "dev"}:
                raise ValueError("SECRET_KEY must be a strong random value in production")
            if not self.first_superuser_password or self.first_superuser_password == "change-me":
                raise ValueError("FIRST_SUPERUSER_PASSWORD must be changed in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
