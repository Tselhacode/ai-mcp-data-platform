"""Database session and service construction helpers for MCP tools.

MCP tools call these helpers to get fully-constructed service objects.
All SQL lives in the repository layer — this module only wires dependencies.

No LangChain imports permitted.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from data.models import Base
from data.repositories.energy import SQLAlchemyEnergyRepository
from services.energy_service import EnergyService


def _get_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory for the given database URL.

    Args:
        database_url: SQLAlchemy async database URL.

    Returns:
        Async session factory.
    """
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_async_engine(
        database_url,
        echo=False,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Module-level session factory — created once from settings.
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the module-level session factory, creating it on first call."""
    global _session_factory
    if _session_factory is None:
        settings = get_settings()
        _session_factory = _get_session_factory(settings.database_url)
    return _session_factory


@asynccontextmanager
async def get_energy_service(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> AsyncGenerator[EnergyService, None]:
    """Async context manager that yields a fully-constructed EnergyService.

    Creates a database session, constructs the repository and service, and
    cleans up the session on exit.

    Args:
        session_factory: Optional session factory override (for testing).

    Yields:
        Constructed EnergyService bound to an open session.
    """
    factory = session_factory or get_session_factory()
    async with factory() as session:
        repo = SQLAlchemyEnergyRepository(session)
        yield EnergyService(repo=repo)


async def create_tables_if_needed(database_url: str) -> None:
    """Create all tables if they do not exist (for in-memory test databases).

    In production, Alembic manages schema. This is only for test fixtures.

    Args:
        database_url: SQLAlchemy async database URL.
    """
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_async_engine(
        database_url,
        echo=False,
        connect_args=connect_args,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


def make_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Create a new session factory for the given URL (used in tests).

    Args:
        database_url: SQLAlchemy async database URL.

    Returns:
        New async session factory.
    """
    return _get_session_factory(database_url)
