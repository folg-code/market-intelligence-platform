"""FastAPI application: lifespan wiring (database engine + the in-process
APScheduler driving the 5-minute processing cycle, ADR-0004/ADR-0011) and
the `/health` endpoint.

The dashboard read path (Phase 7) attaches to this app later.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from moj_projekt.config.settings import Settings, get_settings
from moj_projekt.cycle.run_once import run_once
from moj_projekt.persistence.health import check_database_health

_CONNECT_TIMEOUT_SECONDS = 3
_CYCLE_JOB_ID = "processing_cycle"


def _create_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": _CONNECT_TIMEOUT_SECONDS},
    )


def _run_cycle_job(engine: Engine) -> None:
    """One scheduler tick.

    A fresh ``Session`` per invocation, never one shared across ticks
    (root ``CLAUDE.md``: "The clock is injected"; ADR-0011 requires the
    cycle to be resumable and non-overlapping) - APScheduler calls this
    repeatedly over the app's lifetime, and a long-lived Session would
    accumulate identity-map/transaction state across unrelated ticks. This
    delegates to :func:`~moj_projekt.cycle.run_once.run_once`, the exact
    same orchestration path :mod:`moj_projekt.cycle.run_once`'s direct
    entrypoint and the integration tests use - the scheduler is just one
    more caller of it, not a second code path.
    """
    with Session(engine) as session:
        run_once(session)


def build_scheduler(engine: Engine, settings: Settings) -> BackgroundScheduler:
    """Build (but do not start) the APScheduler instance driving the
    5-minute processing cycle (ADR-0004, ADR-0011).

    ``BackgroundScheduler`` rather than ``AsyncIOScheduler``: nothing else
    in this codebase is async yet (plain SQLAlchemy ``Session``, sync
    repositories), and ``BackgroundScheduler`` runs jobs on its own worker
    thread without requiring the job function or anything it calls to be
    a coroutine - simpler to reason about alongside synchronous
    persistence code than bridging sync DB calls into an event loop would
    be.

    Exposed as a standalone, importable function - not inlined into
    :func:`lifespan` - so a test can build the same scheduler and inspect
    the registered job's ``coalesce``/``max_instances``/
    ``misfire_grace_time`` without starting the app or waiting on real
    wall-clock time (the practical way to cover the "after simulated
    downtime, one catch-up cycle runs" acceptance criterion - see
    ``tests/unit/test_scheduler_wiring.py``).
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_cycle_job,
        args=(engine,),
        id=_CYCLE_JOB_ID,
        trigger="interval",
        seconds=settings.cycle_interval_seconds,
        # Overlap prevention at the scheduler level (ADR-0011) - the
        # data-level guard in run_cycle() is the independent second layer.
        max_instances=1,
        # A downtime window coalesces into one catch-up cycle, not a
        # backlog of missed ticks (ADR-0011), bounded by a configured
        # grace period rather than an unbounded one.
        coalesce=True,
        misfire_grace_time=settings.cycle_misfire_grace_seconds,
    )
    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = _create_engine()
    app.state.engine = engine
    scheduler = build_scheduler(engine, get_settings())
    scheduler.start()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown(wait=True)
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
