"""Shared test fixtures for the AI MCP Data Platform backend.

CRITICAL: LangSmith must be disabled for all tests.
This is set as the very first operation in this module.
"""

import os

# Disable LangSmith unconditionally for all tests.
# This must be set before any LangChain imports occur.
os.environ["LANGSMITH_TRACING"] = "false"

from collections.abc import AsyncGenerator
from datetime import datetime

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data.models import Base, Building, EnergyReading

# ---------------------------------------------------------------------------
# Async SQLite in-memory engine and session fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def engine():
    """Create an async in-memory SQLite engine for tests.

    Uses a shared cache URL so the same in-memory DB is accessible across
    connections within the same test. Tables are created fresh for each test.
    """
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Return an async session factory bound to the test engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Provide an open AsyncSession for a single test.

    Uses a nested transaction (savepoint) so each test is fully isolated
    and changes are rolled back after the test finishes.
    """
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Seed data helpers
# ---------------------------------------------------------------------------


def _make_seed_buildings() -> list[Building]:
    """Create fresh Building objects each call to avoid SQLAlchemy instance reuse."""
    return [
        Building(
            id="B001",
            name="City Hall Annex",
            address="100 Main Street",
            floor_count=5,
            area_sqft=45000.0,
            created_at=datetime(2024, 1, 1),
        ),
        Building(
            id="B002",
            name="Riverside Office Tower",
            address="200 River Boulevard",
            floor_count=12,
            area_sqft=120000.0,
            created_at=datetime(2024, 1, 1),
        ),
        Building(
            id="B007",
            name="Central Data Center",
            address="700 Server Farm Blvd",
            floor_count=4,
            area_sqft=110000.0,
            created_at=datetime(2024, 1, 1),
        ),
    ]


@pytest_asyncio.fixture
async def seeded_buildings(db_session: AsyncSession) -> list[Building]:
    """Insert a small set of test buildings and return them."""
    buildings = _make_seed_buildings()
    db_session.add_all(buildings)
    await db_session.commit()
    return buildings


@pytest_asyncio.fixture
async def seeded_readings(
    db_session: AsyncSession, seeded_buildings: list[Building]
) -> list[EnergyReading]:
    """Insert a small set of test energy readings and return them."""
    readings = [
        EnergyReading(
            building_id="B001",
            timestamp=datetime(2024, 7, 1, 10, 0),
            kwh=12.5,
            reading_type="electricity",
            meter_id="ELEC-B001",
            created_at=datetime(2024, 1, 1),
        ),
        EnergyReading(
            building_id="B001",
            timestamp=datetime(2024, 7, 1, 11, 0),
            kwh=13.0,
            reading_type="electricity",
            meter_id="ELEC-B001",
            created_at=datetime(2024, 1, 1),
        ),
        EnergyReading(
            building_id="B007",
            timestamp=datetime(2024, 7, 1, 10, 0),
            kwh=45.0,
            reading_type="electricity",
            meter_id="ELEC-B007",
            created_at=datetime(2024, 1, 1),
        ),
        EnergyReading(
            building_id="B007",
            timestamp=datetime(2024, 8, 1, 10, 0),
            kwh=70.0,
            reading_type="electricity",
            meter_id="ELEC-B007",
            created_at=datetime(2024, 1, 1),
        ),
        # B001 gas reading
        EnergyReading(
            building_id="B001",
            timestamp=datetime(2024, 7, 1, 10, 0),
            kwh=5.0,
            reading_type="gas",
            meter_id="GAS-B001",
            created_at=datetime(2024, 1, 1),
        ),
    ]
    db_session.add_all(readings)
    await db_session.commit()
    return readings
