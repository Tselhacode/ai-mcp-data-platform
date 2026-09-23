"""MCP integration test fixtures.

Provides a FastMCP server backed by an in-memory SQLite database with
seeded test data. Uses fastmcp.client.Client for in-memory transport.

No real network connections. No LangChain. SQLite in-memory only.
"""

from __future__ import annotations

from datetime import datetime
from typing import cast

import pytest_asyncio
from fastmcp.client import Client
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data.models import Base, Building, EnergyReading
from mcp._server import create_mcp_server

# ── In-memory database fixtures ───────────────────────────────────────────────

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_engine():
    """Create a shared-cache in-memory SQLite engine for MCP tests."""
    engine = create_async_engine(
        _TEST_DB_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(test_engine) -> async_sessionmaker[AsyncSession]:
    """Return a session factory bound to the in-memory test engine."""
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def seeded_session_factory(test_session_factory) -> async_sessionmaker[AsyncSession]:
    """Session factory pre-loaded with test buildings and readings."""
    async with test_session_factory() as session:
        buildings = [
            Building(
                id="B001",
                name="City Hall Annex",
                address="100 Main Street",
                floor_count=5,
                area_sqft=45000.0,
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
        session.add_all(buildings)
        await session.commit()

        # Two months of hourly electricity readings for B001 and B007
        readings = []
        for building_id, base_kwh in [("B001", 12.0), ("B007", 45.0)]:
            for month in [7, 8]:
                for day in range(1, 32):
                    for hour in range(24):
                        readings.append(
                            EnergyReading(
                                building_id=building_id,
                                timestamp=datetime(2024, month, day, hour, 0),
                                kwh=base_kwh + (day % 5),
                                reading_type="electricity",
                                meter_id=f"ELEC-{building_id}",
                                created_at=datetime(2024, 1, 1),
                            )
                        )
        session.add_all(readings)
        await session.commit()

    return cast(async_sessionmaker[AsyncSession], test_session_factory)


# ── MCP server fixtures ───────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def mcp_server(seeded_session_factory):
    """FastMCP server backed by seeded in-memory database."""
    return create_mcp_server(session_factory=seeded_session_factory)


@pytest_asyncio.fixture
async def mcp_client(mcp_server):
    """Connected FastMCP client for testing tools."""
    async with Client(mcp_server) as client:
        yield client


@pytest_asyncio.fixture
async def empty_mcp_server(test_session_factory):
    """FastMCP server backed by empty in-memory database."""
    return create_mcp_server(session_factory=test_session_factory)


@pytest_asyncio.fixture
async def empty_mcp_client(empty_mcp_server):
    """Connected FastMCP client for empty database tests."""
    async with Client(empty_mcp_server) as client:
        yield client
