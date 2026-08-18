"""Unit tests for the APScheduler wiring (S001-T011) - no database.

Engine creation via ``create_engine`` is lazy (SQLAlchemy does not open a
connection until something executes against it), and ``BackgroundScheduler``
does not touch the engine until its job actually fires - both tests here
build/start a scheduler without ever connecting to a database.

Covers the "after simulated downtime, one catch-up cycle runs, not a
backlog" acceptance criterion via a config assertion rather than a
real-time test: inspecting the registered job's actual
``coalesce``/``max_instances``/``misfire_grace_time`` values on the
scheduler instance built exactly the way ``lifespan`` builds it, without
starting the app or waiting on real wall-clock time (documented in the PR
body under "Known Limitations").
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from moj_projekt.api.app import build_scheduler, create_app
from moj_projekt.config.settings import Settings, get_settings

_UNREACHABLE_DATABASE_URL = "postgresql+psycopg://user:pass@localhost:1/db"


def _fake_settings(*, cycle_interval_seconds: int, cycle_misfire_grace_seconds: int) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        postgres_password="unit-test-password",
        cycle_interval_seconds=cycle_interval_seconds,
        cycle_misfire_grace_seconds=cycle_misfire_grace_seconds,
    )


def test_scheduler_job_has_overlap_prevention_and_bounded_catch_up_config() -> None:
    engine = create_engine(_UNREACHABLE_DATABASE_URL)
    settings = _fake_settings(cycle_interval_seconds=300, cycle_misfire_grace_seconds=45)

    scheduler = build_scheduler(engine, settings)
    jobs = scheduler.get_jobs()

    assert len(jobs) == 1
    job = jobs[0]
    assert job.id
    # Overlap prevention at the scheduler level (ADR-0011) - independent of
    # the data-level guard in run_cycle().
    assert job.max_instances == 1
    # A downtime window coalesces into one catch-up cycle, not a backlog of
    # missed ticks (ADR-0011).
    assert job.coalesce is True
    # Bounded, and read from typed settings rather than a hardcoded number
    # (ADR-0004: "The interval itself should be configuration").
    assert job.misfire_grace_time == 45
    assert job.trigger.interval.total_seconds() == 300


def test_scheduler_interval_is_read_from_settings_not_hardcoded() -> None:
    engine = create_engine(_UNREACHABLE_DATABASE_URL)
    settings = _fake_settings(cycle_interval_seconds=120, cycle_misfire_grace_seconds=30)

    scheduler = build_scheduler(engine, settings)

    job = scheduler.get_jobs()[0]
    assert job.trigger.interval.total_seconds() == 120
    assert job.misfire_grace_time == 30


@pytest.fixture
def _isolated_settings_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # create_app()'s lifespan calls get_settings(), an lru_cache'd
    # singleton - isolate this test's Settings from whatever another test
    # (or a real .env file) may have already cached or would otherwise
    # supply, and restore the cache afterwards so this test cannot leak
    # into others.
    monkeypatch.setenv("POSTGRES_PASSWORD", "unit-test-password")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_scheduler_starts_with_the_app_and_stops_cleanly_on_shutdown(
    _isolated_settings_cache: None,
) -> None:
    app = create_app()

    # /health is not exercised here on purpose - port 1 never accepts a
    # connection, and this test's only concern is the scheduler lifecycle,
    # not database connectivity.
    with TestClient(app):
        assert app.state.scheduler.running is True

    assert app.state.scheduler.running is False
