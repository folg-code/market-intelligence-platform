from decimal import Decimal

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


def test_missing_password_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PASSWORD", "from-env")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.postgres_host == "localhost"
    assert settings.postgres_password == "from-env"


def test_cycle_extract_document_cap_defaults_to_twenty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CYCLE_EXTRACT_DOCUMENT_CAP", raising=False)
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        postgres_password="secret",
    )

    assert settings.cycle_extract_document_cap == 20


def test_cycle_extract_document_cap_rejects_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CYCLE_EXTRACT_DOCUMENT_CAP", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, postgres_password="secret")  # type: ignore[call-arg]


def test_llm_budget_settings_default_to_ten_dollars_and_eighty_percent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LLM_MONTHLY_CEILING_USD", raising=False)
    monkeypatch.delenv("LLM_MONTHLY_SOFT_THRESHOLD_RATIO", raising=False)
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        postgres_password="secret",
    )

    assert settings.llm_monthly_ceiling_usd == Decimal("10")
    assert settings.llm_monthly_soft_threshold_ratio == Decimal("0.80")


def test_llm_budget_settings_read_custom_values_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_MONTHLY_CEILING_USD", "5")
    monkeypatch.setenv("LLM_MONTHLY_SOFT_THRESHOLD_RATIO", "0.5")
    monkeypatch.setenv("CYCLE_EXTRACT_DOCUMENT_CAP", "3")
    settings = Settings(_env_file=None, postgres_password="secret")  # type: ignore[call-arg]

    assert settings.llm_monthly_ceiling_usd == Decimal("5")
    assert settings.llm_monthly_soft_threshold_ratio == Decimal("0.5")
    assert settings.cycle_extract_document_cap == 3


def test_llm_budget_settings_reject_non_positive_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_MONTHLY_CEILING_USD", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, postgres_password="secret")  # type: ignore[call-arg]


def test_llm_budget_settings_reject_soft_threshold_of_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_MONTHLY_SOFT_THRESHOLD_RATIO", "1")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, postgres_password="secret")  # type: ignore[call-arg]
