"""SQLAlchemy async engine and session factory.

Provides the engine and session factory used throughout the application.
The DATABASE_URL environment variable selects the backend (SQLite or PostgreSQL).

Usage:
    from data.database import get_engine, get_session_factory

    engine = get_engine(database_url)
    async_session = get_session_factory(engine)

    async with async_session() as session:
        result = await session.execute(select(Building))
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def get_engine(database_url: str) -> AsyncEngine:
    """Create and return an async SQLAlchemy engine for the given URL.

    For SQLite: echo=False, use connect_args={"check_same_thread": False}
    For PostgreSQL: pool_pre_ping=True for connection health checking.

    Args:
        database_url: SQLAlchemy async database URL.

    Returns:
        Configured async engine.
    """
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_async_engine(
        database_url,
        echo=False,
        connect_args=connect_args,
        pool_pre_ping=True,
    )


def get_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create and return an async session factory bound to the given engine.

    Args:
        engine: The async engine to bind sessions to.

    Returns:
        Async session factory (callable that produces AsyncSession instances).
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Async generator that yields a session and handles commit/rollback.

    Intended for use as a FastAPI dependency via Depends().

    Args:
        session_factory: The session factory to create sessions from.

    Yields:
        An open AsyncSession.
    """
    async with session_factory() as session:
        yield session
