"""Integration test for GET /health against the compose database.

Run with the `db` service up and its port published to the host (the
default in `compose.yaml`):

    docker compose up -d db
    POSTGRES_HOST=localhost POSTGRES_PORT=5433 python -m pytest -m integration

`Settings` still reads POSTGRES_DB/USER/PASSWORD from `.env`; host and port
differ from the in-container "db"/5432 because this test runs on the host,
not inside the `app` container (the default host port is 5433, not 5432, to
avoid colliding with a locally installed PostgreSQL - see `compose.yaml`).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    from moj_projekt.api.app import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_database_and_pgvector(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["pgvector"] == "available"
