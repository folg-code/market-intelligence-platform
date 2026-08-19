"""Alembic environment: builds the database URL from the typed settings
object rather than a hardcoded or `.ini`-embedded one, so migrations use the
exact same connection configuration as the application (ADR-0013).

There is deliberately no call to this module, or to `alembic upgrade`, from
application startup code - migrations are an explicit, separate command
(root `CLAUDE.md`, ADR-0013).
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from moj_projekt.config.settings import Settings
from moj_projekt.persistence.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ORM metadata for autogenerate support (S001-T006 onward). Migrations are
# still written and reviewed explicitly - autogenerate is a drafting aid,
# not a substitute for reading the generated script.
target_metadata = Base.metadata


def _database_url() -> str:
    return Settings().database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live database connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection built from `Settings`."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
