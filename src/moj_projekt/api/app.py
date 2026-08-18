"""FastAPI application: lifespan wiring and the `/health` endpoint.

The scheduler (S001-T011) and the dashboard read path (Phase 7) attach to
this app later; today it only proves the app can talk to the database.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from moj_projekt.config.settings import get_settings
from moj_projekt.persistence.health import check_database_health

_CONNECT_TIMEOUT_SECONDS = 3


def _create_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": _CONNECT_TIMEOUT_SECONDS},
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = _create_engine()
    app.state.engine = engine
    try:
        yield
    finally:
        engine.dispose()


def create_app() -> FastAPI:
    """Build the FastAPI app. The app container holds no other state."""
    app = FastAPI(title="Market Intelligence Platform", lifespan=lifespan)

    @app.get("/health")
    def health() -> JSONResponse:
        result = check_database_health(app.state.engine)
        payload: dict[str, Any] = {
            "status": "ok" if result.healthy else "degraded",
            "database": result.database,
            "pgvector": result.pgvector,
        }
        if result.detail is not None:
            payload["detail"] = result.detail
        return JSONResponse(payload, status_code=200 if result.healthy else 503)

    return app


app = create_app()
