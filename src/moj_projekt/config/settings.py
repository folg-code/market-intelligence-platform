"""Typed application settings, loaded from the environment.

Every configuration value the app needs comes through this module - no
`os.environ` read belongs anywhere else in the codebase (ADR-0013). Locally,
values come from a `.env` file (copied from `.env.example`, not committed);
in the container they come from `compose.yaml`'s `environment:` block, which
is itself backed by `.env`.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from pydantic import Field
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

    # LLM provider key (ADR-0010, ADR-0013). Optional here so unit tests and
    # the default cycle never need a real key; AnthropicClient rejects a
    # missing/blank value with a clear error (D-S002-04 clause 13).
    anthropic_api_key: str | None = None

    # The 5-minute processing cycle (ADR-0004: "The interval itself should
    # be configuration, so tuning does not require a code change") and its
    # APScheduler job settings (ADR-0011: max_instances=1, coalesce=True,
    # "a bounded misfire grace" so downtime produces one catch-up cycle,
    # not a backlog). The grace default is well under the interval itself,
    # so a missed tick still catches up promptly rather than firing right
    # up against the next scheduled tick.
    cycle_interval_seconds: int = 300
    cycle_misfire_grace_seconds: int = 60
    # Per-cycle extract cap (ADR-0015): bounds a single cycle's spend so an
    # ingest surge cannot consume the monthly ceiling before the budget
    # guard is next evaluated. Must be >= 1.
    cycle_extract_document_cap: int = Field(default=20, ge=1)
    # Monthly LLM cost ceiling and the soft threshold as a fraction of it
    # (ADR-0015 clause 4). Defaults $10 and 80%. Both are configuration.
    llm_monthly_ceiling_usd: Decimal = Field(default=Decimal("10"), gt=0)
    llm_monthly_soft_threshold_ratio: Decimal = Field(default=Decimal("0.80"), gt=0, lt=1)

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
