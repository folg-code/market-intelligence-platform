"""Typed application settings, loaded from the environment.

Every configuration value the app needs comes through this module - no
`os.environ` read belongs anywhere else in the codebase (ADR-0013). Locally,
values come from a `.env` file (copied from `.env.example`, not committed);
in the container they come from `compose.yaml`'s `environment:` block, which
is itself backed by `.env`.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    ``postgres_password`` has no default: a missing password fails fast at
    startup rather than silently connecting with a guessable value.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"

    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "moj_projekt"
    postgres_user: str = "moj_projekt"
    postgres_password: str

    @property
    def database_url(self) -> str:
        """SQLAlchemy connection URL for the `psycopg` driver (ADR-0005)."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance, built once and cached."""
    return Settings()
