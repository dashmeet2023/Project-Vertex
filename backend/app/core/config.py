"""
Project Vertex backend — application configuration.

All settings are read from environment variables (or a .env file).
Pydantic-Settings handles parsing and validation.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "vertex"
    POSTGRES_USER: str = "vertex_app"
    POSTGRES_PASSWORD: str = "changeme_dev"

    POSTGRES_SUPERUSER: str = "postgres"
    POSTGRES_SUPERUSER_PASSWORD: str = "changeme_super"

    APP_USER_PASSWORD: str = "changeme_app_user"
    APP_ADMIN_PASSWORD: str = "changeme_app_admin"

    # ── Token signing ─────────────────────────────────────────────────────────
    # JSON string: {"v1": "<hex secret>"}
    TOKEN_SIGNING_KEYS: str = '{"v1":"insecure_dev_secret_replace_in_production"}'
    TOKEN_ACTIVE_KID: str = "v1"
    TOKEN_TTL_SECONDS: int = 600

    # ── App ───────────────────────────────────────────────────────────────────
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    DEBUG: bool = False

    # ── Derived ───────────────────────────────────────────────────────────────
    DATABASE_URL: str | None = None

    @property
    def async_database_url(self) -> str:
        if self.DATABASE_URL:
            # Render provides 'postgres://', but SQLAlchemy async needs 'postgresql+asyncpg://'
            if self.DATABASE_URL.startswith("postgres://"):
                return self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def superuser_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_SUPERUSER}:{self.POSTGRES_SUPERUSER_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def signing_keys(self) -> dict[str, str]:
        return json.loads(self.TOKEN_SIGNING_KEYS)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
