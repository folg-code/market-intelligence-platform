"""Idempotent seed command for the MVP Source registry (S001-T010).

Usage::

    python -m moj_projekt.persistence.seed_sources

Reads connection settings the same way the app does (environment / ``.env``
via :class:`~moj_projekt.config.settings.Settings`); see
`docs/reference/WORKFLOWS.md` for local setup.

Data-driven, not hard-coded branching: :func:`seed_sources` iterates the
declarative sources in
:mod:`moj_projekt.persistence.seed_data.sources`, calling
``SourceRepository.add()`` for each. That method already performs
``INSERT ... ON CONFLICT DO NOTHING`` keyed on ``Source.key``
(:class:`~moj_projekt.persistence.source_repository.SqlAlchemySourceRepository`).

On a fresh database, running this command twice is stable, including
``active``: the first insert writes the seed flag and the second is a
no-op that leaves the stored row unchanged.

A re-seed onto an existing registry does **not** flip ``active`` (or any
other column) of an already-present key. If a row was previously seeded
``active=True``, deactivate it with a manual flag change. This command
does not widen ``add()``'s conflict clause.

The CLI opens one unit of work around the whole seed so the registry
write is a single commit.
"""

from __future__ import annotations

from sqlalchemy import create_engine

from moj_projekt.config.settings import Settings
from moj_projekt.domain.repositories import SourceRepository
from moj_projekt.domain.source import Source
from moj_projekt.persistence.seed_data.sources import SEED_SOURCES
from moj_projekt.persistence.unit_of_work import SqlAlchemyUnitOfWork

__all__ = ["seed_sources"]


def seed_sources(repository: SourceRepository) -> list[Source]:
    """Persist every declarative seed Source, idempotently.

    Returns the stored (post-upsert) rows in ``SEED_SOURCES`` order.
    The caller owns the transaction (flush here, commit in the unit of
    work).
    """
    return [repository.add(source) for source in SEED_SOURCES]


def main() -> int:
    """Seed the MVP Source registry against the configured database."""
    settings = Settings()
    engine = create_engine(settings.database_url)
    try:
        with SqlAlchemyUnitOfWork(engine) as uow:
            seeded = seed_sources(uow.sources)
    finally:
        engine.dispose()

    for source in seeded:
        print(
            f"seeded: {source.key} (tier={source.tier.name}, "
            f"publisher={source.publisher}, active={source.active})"
        )
    print(f"{len(seeded)} source(s) in registry after seed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
