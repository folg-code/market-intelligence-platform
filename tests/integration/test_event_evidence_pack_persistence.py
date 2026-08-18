"""Integration tests for Event/EvidencePack persistence (S001-T007).

Run with the `db` service up and its port published to the host (the
default in `compose.yaml`):

    docker compose up -d db
    POSTGRES_HOST=localhost POSTGRES_PORT=5433 python -m pytest -m integration

Exercises the actual acceptance criteria: an Event cannot be stored with an
empty `source_ids`, facts and claims stay in separate stored columns, an
EvidencePack rebuild creates a new `evidence_version` row instead of
mutating one, and `independent_source_count <= source_count` is enforced at
the database level too.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from moj_projekt.config.settings import Settings
from moj_projekt.domain.enums import EvidenceRefKind
from moj_projekt.domain.event import Event
from moj_projekt.domain.evidence import EvidenceRef
from moj_projekt.domain.evidence_pack import EvidencePack
from moj_projekt.domain.narrative import Narrative
from moj_projekt.persistence.event_repository import SqlAlchemyEventRepository
from moj_projekt.persistence.evidence_pack_repository import (
    SqlAlchemyEvidencePackRepository,
)
from moj_projekt.persistence.narrative_repository import SqlAlchemyNarrativeRepository

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OCCURRED_AT = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
_GENERATED_AT = datetime(2026, 8, 1, 13, 0, tzinfo=UTC)


@pytest.fixture
def alembic_config(monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    config = Config(str(_REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_REPO_ROOT / "migrations"))
    return config


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    settings = Settings()
    db_engine = create_engine(settings.database_url)
    try:
        yield db_engine
    finally:
        db_engine.dispose()


@pytest.fixture
def migrated_session(alembic_config: Config, engine: Engine) -> Iterator[Session]:
    command.upgrade(alembic_config, "head")
    try:
        with Session(engine) as session:
            yield session
    finally:
        command.downgrade(alembic_config, "base")


def _make_event(**overrides: object) -> Event:
    defaults: dict[str, object] = dict(
        type="rate_decision",
        title="Fed holds rates steady",
        occurred_at=_OCCURRED_AT,
        source_ids=(uuid4(),),
        confidence=0.75,
    )
    defaults.update(overrides)
    return Event(**defaults)  # type: ignore[arg-type]


def _make_pack(**overrides: object) -> EvidencePack:
    defaults: dict[str, object] = dict(
        narrative_id=uuid4(),
        evidence_version=1,
        generated_at=_GENERATED_AT,
        source_count=3,
        independent_source_count=2,
        source_diversity=2,
    )
    defaults.update(overrides)
    return EvidencePack(**defaults)  # type: ignore[arg-type]


def _seed_narrative(session: Session) -> UUID:
    """Create a Narrative and return its id.

    ``evidence_packs.narrative_id`` gained a foreign key to ``narratives.id``
    in the S001-T008 migration, so a real Narrative row must exist before an
    EvidencePack referencing it can be inserted.
    """
    narrative = Narrative(
        canonical_key=f"narrative_{uuid4().hex[:8]}",
        display_title="Fed rate cut expectations",
        economic_mechanism="Lower policy rate reduces the discount rate.",
        market_interpretation="Bullish for risk assets.",
        category="monetary_policy",
        first_seen=_GENERATED_AT,
        last_seen=_GENERATED_AT,
        updated_at=_GENERATED_AT,
    )
    stored = SqlAlchemyNarrativeRepository(session).add(narrative)
    assert stored.id is not None
    return stored.id


def test_event_round_trips_with_facts_and_claims_kept_separate(
    migrated_session: Session,
) -> None:
    repo = SqlAlchemyEventRepository(migrated_session)
    fact = {"text": "Rates held at 5.25-5.50%.", "category": "observed_fact"}
    claim = {"text": "A cut is likely next quarter.", "category": "source_claim"}
    event = _make_event(extracted_facts=(fact,), source_claims=(claim,))

    stored = repo.add(event)
    fetched = repo.get(stored.id)  # type: ignore[arg-type]

    assert fetched is not None
    assert fetched.extracted_facts == (fact,)
    assert fetched.source_claims == (claim,)
    row = migrated_session.execute(
        text(
            "SELECT extracted_facts, source_claims FROM events WHERE id = :id"
        ),
        {"id": stored.id},
    ).one()
    # Stored in genuinely separate columns - not merged into one structure.
    assert row.extracted_facts == [fact]
    assert row.source_claims == [claim]


def test_event_cannot_be_stored_with_empty_source_ids_at_the_database(
    migrated_session: Session,
) -> None:
    with pytest.raises(IntegrityError, match="ck_events_source_ids_not_empty"):
        migrated_session.execute(
            text(
                "INSERT INTO events "
                "(type, title, occurred_at, source_ids, confidence) "
                "VALUES (:type, :title, :occurred_at, '[]'::jsonb, :confidence)"
            ),
            {
                "type": "rate_decision",
                "title": "Fed holds rates steady",
                "occurred_at": _OCCURRED_AT,
                "confidence": 0.5,
            },
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_evidence_pack_rebuild_creates_a_new_version_row(
    migrated_session: Session,
) -> None:
    repo = SqlAlchemyEvidencePackRepository(migrated_session)
    narrative_id = _seed_narrative(migrated_session)
    first = repo.add(_make_pack(narrative_id=narrative_id, evidence_version=1))
    second = repo.add(_make_pack(narrative_id=narrative_id, evidence_version=2))

    assert first.id != second.id
    current = repo.get_current(narrative_id)
    assert current is not None
    assert current.evidence_version == 2

    count = migrated_session.execute(
        text("SELECT count(*) FROM evidence_packs WHERE narrative_id = :nid"),
        {"nid": narrative_id},
    ).scalar_one()
    assert count == 2


def test_evidence_pack_row_is_never_mutated(migrated_session: Session) -> None:
    repo = SqlAlchemyEvidencePackRepository(migrated_session)
    narrative_id = _seed_narrative(migrated_session)
    stored = repo.add(_make_pack(narrative_id=narrative_id))

    with pytest.raises(DBAPIError, match="immutable"):
        migrated_session.execute(
            text(
                "UPDATE evidence_packs SET source_count = 99 WHERE id = :id"
            ),
            {"id": stored.id},
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_independent_source_count_le_source_count_enforced_at_the_database(
    migrated_session: Session,
) -> None:
    narrative_id = _seed_narrative(migrated_session)
    with pytest.raises(
        IntegrityError, match="ck_evidence_packs_independent_le_source_count"
    ):
        migrated_session.execute(
            text(
                "INSERT INTO evidence_packs "
                "(narrative_id, evidence_version, generated_at, source_count, "
                "independent_source_count, source_diversity) "
                "VALUES (:nid, 1, :generated_at, 1, 2, 1)"
            ),
            {"nid": narrative_id, "generated_at": _GENERATED_AT},
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_evidence_pack_traces_evidence_to_documents_and_events(
    migrated_session: Session,
) -> None:
    repo = SqlAlchemyEvidencePackRepository(migrated_session)
    narrative_id = _seed_narrative(migrated_session)
    document_ref = EvidenceRef(kind=EvidenceRefKind.DOCUMENT, target_id=str(uuid4()))
    event_ref = EvidenceRef(kind=EvidenceRefKind.EVENT, target_id=str(uuid4()))
    pack = _make_pack(
        narrative_id=narrative_id,
        supporting_evidence=(document_ref,),
        official_evidence=(event_ref,),
    )

    stored = repo.add(pack)
    fetched = repo.get_version(stored.narrative_id, stored.evidence_version)

    assert fetched is not None
    assert fetched.supporting_evidence == (document_ref,)
    assert fetched.official_evidence == (event_ref,)
