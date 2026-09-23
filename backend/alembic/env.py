"""Alembic migration environment configuration.

This file is invoked by Alembic when running migrations. It:
  1. Loads the database URL from the environment (via app/config.py)
  2. Imports all ORM models so Alembic can detect schema changes
  3. Runs migrations synchronously (Alembic does not support async natively)
"""

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import the declarative base and all models so Alembic can see the full schema.
# Adding a new model? Import it here or it will not appear in autogenerate.
from data.models import (  # noqa: F401
    Base,
    Building,
    EnergyReading,
    EvaluationRecord,
    EvaluationRun,
    Session,
    SessionTurn,
)

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Configure Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the metadata for autogenerate support
target_metadata = Base.metadata


def get_url() -> str:
    """Return the database URL from the environment.

    Prefers DATABASE_URL env var. Falls back to the default SQLite path.
    Never reads the URL from alembic.ini — it must come from the environment.
    """
    return os.environ.get(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./data/db.sqlite",
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a live connection).

    Used when generating SQL scripts for review, not for direct execution.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations using an established connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async engine (required for aiosqlite/asyncpg)."""
    # Convert the async URL for Alembic's synchronous migration runner
    url = get_url()

    connectable = async_engine_from_config(
        {"sqlalchemy.url": url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (direct connection to the database)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
