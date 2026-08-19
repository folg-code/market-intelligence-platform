"""Integration tests for Narrative aggregate persistence (S001-T008).

Run with the `db` service up and its port published to the host (the
default in `compose.yaml`):

    docker compose up -d db
    POSTGRES_HOST=localhost POSTGRES_PORT=5433 python -m pytest -m integration

Exercises the actual acceptance criteria: `canonical_key` is unique,
`evidence_packs.narrative_id` has a foreign key to `narratives.id`, a
Narrative with a NULL `identity_embedding` is fully valid, a
nearest-neighbour query over the vector column executes successfully
against seeded test vectors, self-relations are rejected, and episodes of
one narrative cannot overlap.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from moj_projekt.config.settings import Settings
from moj_projekt.domain.embedding import IdentityEmbedding
from moj_projekt.domain.enums import RelationType
from moj_projekt.domain.evidence_pack import EvidencePack
from moj_projekt.domain.narrative import Narrative
from moj_projekt.domain.narrative_episode import NarrativeEpisode
from moj_projekt.domain.narrative_relation import NarrativeRelation
from moj_projekt.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIRST_SEEN = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
_LAST_SEEN = _FIRST_SEEN + timedelta(hours=1)
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


def _make_narrative(**overrides: object) -> Narrative:
    defaults: dict[str, object] = dict(
        canonical_key=f"narrative_{uuid4().hex[:8]}",
        display_title="Fed rate cut expectations",
        economic_mechanism="Lower policy rate reduces the discount rate.",
        market_interpretation="Bullish for risk assets.",
        category="monetary_policy",
        first_seen=_FIRST_SEEN,
        last_seen=_LAST_SEEN,
        updated_at=_LAST_SEEN,
    )
    defaults.update(overrides)
    return Narrative(**defaults)  # type: ignore[arg-type]


def test_upgrade_to_head_and_back_round_trips_narrative_tables(
    alembic_config: Config, engine: Engine
) -> None:
    command.upgrade(alembic_config, "head")
    with engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
        }
    assert {
        "narratives",
        "narrative_episodes",
        "narrative_events",
        "narrative_relations",
    } <= tables

    command.downgrade(alembic_config, "base")
    with engine.connect() as connection:
        tables_after_downgrade = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
        }
    assert "narratives" not in tables_after_downgrade


def test_canonical_key_is_unique(migrated_session: Session, engine: Engine) -> None:
    narrative = _make_narrative(canonical_key="fed_rate_cut_expectations")
    with SqlAlchemyUnitOfWork(engine) as uow:
        uow.narratives.add(narrative)

    with (
        pytest.raises(IntegrityError, match="uq_narratives_canonical_key"),
        SqlAlchemyUnitOfWork(engine) as uow,
    ):
        uow.narratives.add(_make_narrative(canonical_key="fed_rate_cut_expectations"))


def test_narrative_with_null_identity_embedding_is_fully_valid(
    migrated_session: Session,
    engine: Engine,
) -> None:
    narrative = _make_narrative(identity_embedding=None)

    with SqlAlchemyUnitOfWork(engine) as uow:
        stored = uow.narratives.add(narrative)
        fetched = uow.narratives.get(stored.id)  # type: ignore[arg-type]

    assert fetched is not None
    assert fetched.identity_embedding is None


def test_evidence_packs_narrative_id_has_a_foreign_key_to_narratives(
    migrated_session: Session,
    engine: Engine,
) -> None:
    with (
        pytest.raises(IntegrityError, match="fk_evidence_packs_narrative_id_narratives"),
        SqlAlchemyUnitOfWork(engine) as uow,
    ):
        uow.evidence_packs.add(
            EvidencePack(
                narrative_id=uuid4(),
                evidence_version=1,
                generated_at=_GENERATED_AT,
                source_count=1,
                independent_source_count=1,
                source_diversity=1,
            )
        )


def test_evidence_pack_stores_against_an_existing_narrative(
    migrated_session: Session,
    engine: Engine,
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        narrative = uow.narratives.add(_make_narrative())
        stored = uow.evidence_packs.add(
            EvidencePack(
                narrative_id=narrative.id,  # type: ignore[arg-type]
                evidence_version=1,
                generated_at=_GENERATED_AT,
                source_count=1,
                independent_source_count=1,
                source_diversity=1,
            )
        )

    assert stored.narrative_id == narrative.id


def test_nearest_neighbour_query_over_identity_embedding(
    migrated_session: Session,
    engine: Engine,
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        close = uow.narratives.add(
            _make_narrative(
                canonical_key="fed_rate_cut_expectations",
                identity_embedding=IdentityEmbedding(
                    embedding_model="local-minilm",
                    embedding_version="v1",
                    vector=tuple([1.0, 0.0] + [0.0] * 382),
                ),
            )
        )
        far = uow.narratives.add(
            _make_narrative(
                canonical_key="btc_regulatory_pressure",
                identity_embedding=IdentityEmbedding(
                    embedding_model="local-minilm",
                    embedding_version="v1",
                    vector=tuple([0.0, 1.0] + [0.0] * 382),
                ),
            )
        )

    query_vector = "[" + ",".join(["1.0", "0.0"] + ["0.0"] * 382) + "]"
    rows = migrated_session.execute(
        text(
            "SELECT id FROM narratives "
            "ORDER BY identity_embedding <=> CAST(:query_vector AS vector) "
            "LIMIT 2"
        ),
        {"query_vector": query_vector},
    ).all()

    assert [row[0] for row in rows] == [close.id, far.id]


def test_self_relation_is_rejected_at_the_domain_layer() -> None:
    narrative_id = uuid4()

    with pytest.raises(ValueError, match="itself"):
        NarrativeRelation(
            source_narrative_id=narrative_id,
            target_narrative_id=narrative_id,
            relation_type=RelationType.RELATED_TO,
        )


def test_self_relation_is_rejected_at_the_database(
    migrated_session: Session, engine: Engine
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        narrative = uow.narratives.add(_make_narrative())

    # The domain constructor already rejects a self-relation
    # (NarrativeRelation.__post_init__), so exercising the database-level
    # CHECK constraint requires bypassing it with a raw INSERT.
    with pytest.raises(IntegrityError, match="ck_narrative_relations_no_self_relation"):
        migrated_session.execute(
            text(
                "INSERT INTO narrative_relations "
                "(source_narrative_id, target_narrative_id, relation_type) "
                "VALUES (:nid, :nid, :relation_type)"
            ),
            {"nid": narrative.id, "relation_type": RelationType.RELATED_TO.value},
        )
        migrated_session.commit()
    migrated_session.rollback()


def test_episodes_of_one_narrative_cannot_overlap(
    migrated_session: Session, engine: Engine
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        narrative = uow.narratives.add(_make_narrative())
        uow.narrative_episodes.add(
            NarrativeEpisode(
                narrative_id=narrative.id,  # type: ignore[arg-type]
                started_at=_FIRST_SEEN,
                ended_at=_FIRST_SEEN + timedelta(days=2),
            )
        )

    with (
        pytest.raises(IntegrityError, match="ex_narrative_episodes_no_overlap"),
        SqlAlchemyUnitOfWork(engine) as uow,
    ):
        uow.narrative_episodes.add(
            NarrativeEpisode(
                narrative_id=narrative.id,  # type: ignore[arg-type]
                started_at=_FIRST_SEEN + timedelta(days=1),
                ended_at=_FIRST_SEEN + timedelta(days=3),
            )
        )


def test_episodes_of_one_narrative_may_be_sequential(
    migrated_session: Session, engine: Engine
) -> None:
    with SqlAlchemyUnitOfWork(engine) as uow:
        narrative = uow.narratives.add(_make_narrative())
        uow.narrative_episodes.add(
            NarrativeEpisode(
                narrative_id=narrative.id,  # type: ignore[arg-type]
                started_at=_FIRST_SEEN,
                ended_at=_FIRST_SEEN + timedelta(days=1),
            )
        )
        second = uow.narrative_episodes.add(
            NarrativeEpisode(
                narrative_id=narrative.id,  # type: ignore[arg-type]
                started_at=_FIRST_SEEN + timedelta(days=2),
                ended_at=None,
            )
        )

    assert second.ended_at is None
