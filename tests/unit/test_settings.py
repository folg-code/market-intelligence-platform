import pytest
from pydantic import ValidationError

from moj_projekt.config.settings import Settings


def test_database_url_is_built_from_components(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        postgres_password="secret",
        postgres_host="db",
        postgres_port=5432,
        postgres_user="moj_projekt",
        postgres_db="moj_projekt",
    )

    assert settings.database_url == "postgresql+psycopg://moj_projekt:secret@db:5432/moj_projekt"


def test_missing_password_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PASSWORD", "from-env")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.postgres_host == "localhost"
    assert settings.postgres_password == "from-env"
