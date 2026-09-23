"""Tests that the agent actually calls MCP tools (not mocked)."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent.analyst_agent import AnalystAgent
from agent.mcp_client import load_mcp_tools
from data.models import Base, Building, EnergyReading
from llm.fake import FakeChatModel, ScriptedResponse
from mcp._server import create_mcp_server


@pytest.fixture
async def populated_mcp_server():
    """FastMCP server with seeded in-memory SQLite."""
    db_url = f"sqlite+aiosqlite:///file:{uuid.uuid4().hex}?mode=memory&cache=shared&uri=true"

    engine = create_async_engine(
        db_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        session.add(
            Building(
                id="B001",
                name="Building 1",
                address="1 Test St",
                floor_count=3,
                area_sqft=10000.0,
                created_at=datetime(2024, 1, 1),
            )
        )
        for day in range(1, 8):
            for hour in range(24):
                session.add(
                    EnergyReading(
                        building_id="B001",
                        timestamp=datetime(2024, 7, day, hour),
                        kwh=25.0,
                        reading_type="electricity",
                        meter_id="M001",
                        created_at=datetime(2024, 1, 1),
                    )
                )
        await session.commit()

    server = create_mcp_server(session_factory=session_factory)
    yield server, session_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_agent_calls_mcp_list_tables(populated_mcp_server):
    """Agent calls list_tables via MCP, not mocked."""
    mcp_server, _session_factory = populated_mcp_server
    tools = await load_mcp_tools(mcp_server)

    fake_llm = FakeChatModel(
        script=[
            ScriptedResponse(tool_calls=[{"name": "list_tables", "args": {}, "id": "c1"}]),
            ScriptedResponse(content="The available tables are buildings and energy_readings."),
        ]
    )

    agent = AnalystAgent(llm=fake_llm, tools=tools)
    result = await agent.invoke("What tables are available?")

    assert "list_tables" in [t.tool for t in result.tools_used]
    assert "buildings" in result.answer.lower() or "energy_readings" in result.answer.lower()
