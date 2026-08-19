"""Database connectivity and pgvector availability check.

Used by the `/health` endpoint (ADR-0013). This deliberately checks whether
the `vector` extension is *available* to be enabled
(`pg_available_extensions`), not whether it has already been created -
enabling the extension is the Alembic baseline migration's job (S001-T004),
not the health check's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

DatabaseStatus = Literal["ok", "error"]
PgvectorStatus = Literal["available", "unavailable", "unknown"]

_PGVECTOR_EXTENSION_NAME = "vector"


@dataclass(frozen=True)
class HealthCheckResult:
    """Outcome of one database health check."""

    database: DatabaseStatus
    pgvector: PgvectorStatus
    detail: str | None = None

    @property
    def healthy(self) -> bool:
        return self.database == "ok" and self.pgvector == "available"


def check_database_health(engine: Engine) -> HealthCheckResult:
    """Connect to `engine` and report connectivity plus pgvector availability.

    Never raises: any connection or query failure is captured and reported
    as an ``error``/``unknown`` result, so a database outage degrades the
    health endpoint instead of crashing it.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            row = connection.execute(
                text("SELECT 1 FROM pg_available_extensions WHERE name = :name"),
                {"name": _PGVECTOR_EXTENSION_NAME},
            ).first()
    except SQLAlchemyError as exc:
        return HealthCheckResult(database="error", pgvector="unknown", detail=str(exc))

    pgvector_status: PgvectorStatus = "available" if row is not None else "unavailable"
    return HealthCheckResult(database="ok", pgvector=pgvector_status)
