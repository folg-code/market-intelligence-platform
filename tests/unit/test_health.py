from sqlalchemy import create_engine

from moj_projekt.persistence.health import check_database_health


def test_unreachable_database_reports_error() -> None:
    # Port 1 is a reserved, never-listening port: the connection is refused
    # immediately, no live database required for this test.
    engine = create_engine(
        "postgresql+psycopg://user:pass@localhost:1/db",
        connect_args={"connect_timeout": 1},
    )

    result = check_database_health(engine)

    assert result.database == "error"
    assert result.pgvector == "unknown"
    assert result.healthy is False
    assert result.detail is not None
