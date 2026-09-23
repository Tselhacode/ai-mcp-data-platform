"""End-to-end tests for the full pipeline.

Tests:
  HTTP request -> FastAPI -> AgentService -> LangGraph -> MCP tools -> Services -> DB -> Response

Uses FakeChatModel. Does NOT require AWS/Bedrock/LangSmith.
"""

import uuid
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent.agent_service import AgentService
from agent.mcp_client import load_mcp_tools
from app.config import Settings
from app.dependencies import get_agent_service, set_agent_service
from app.main import create_app
from data.models import Base, Building, EnergyReading
from llm.fake import FakeChatModel, ScriptedResponse
from mcp._server import create_mcp_server
from services.session_service import SessionService


@pytest.fixture
async def e2e_env():
    """Create a full E2E environment with seeded DB, MCP tools, and agent service."""
    db_url = f"sqlite+aiosqlite:///file:{uuid.uuid4().hex}?mode=memory&cache=shared&uri=true"

    engine = create_async_engine(db_url, echo=False, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sf: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Seed data
    async with sf() as session:
        session.add(
            Building(
                id="B007",
                name="Building 7",
                address="7 Test St",
                floor_count=5,
                area_sqft=25000.0,
                created_at=datetime(2024, 1, 1),
            )
        )
        for day in range(1, 32):
            for hour in range(24):
                session.add(
                    EnergyReading(
                        building_id="B007",
                        timestamp=datetime(2024, 7, day, hour),
                        kwh=32.0,
                        reading_type="electricity",
                        meter_id="M007",
                        created_at=datetime(2024, 1, 1),
                    )
                )
        await session.commit()

    # Build MCP tools
    mcp_server = create_mcp_server(session_factory=sf)
    tools = await load_mcp_tools(mcp_server)

    # Build the FakeChatModel
    fake_llm = FakeChatModel(
        script=[
            ScriptedResponse(
                tool_calls=[
                    {
                        "name": "get_building_summary",
                        "args": {
                            "building_id": "B007",
                            "start_date": "2024-07-01",
                            "end_date": "2024-07-31",
                        },
                        "id": "call_1",
                    }
                ]
            ),
            ScriptedResponse(
                content="Building B007 used electricity in July 2024 totaling approximately 23,808 kWh."
            ),
        ]
    )

    # Build services
    session_svc = SessionService(session_factory=sf)
    agent_svc = AgentService(llm=fake_llm, tools=tools, session_service=session_svc)

    # Build app with dependency override (bypass lifespan)
    settings = Settings(
        database_url=db_url,
        llm_provider="fake",
        langsmith_tracing=False,
    )
    app = create_app(settings=settings, llm=fake_llm, tools=tools, session_factory=sf)
    set_agent_service(agent_svc)
    app.dependency_overrides[get_agent_service] = lambda: agent_svc

    yield app

    await engine.dispose()


@pytest.mark.asyncio
async def test_full_pipeline_query(e2e_env):
    """End-to-end: HTTP -> FastAPI -> Agent -> MCP -> DB -> answer."""
    async with AsyncClient(transport=ASGITransport(app=e2e_env), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/query",
            json={
                "question": "What was B007's electricity consumption in July 2024?",
                "session_id": None,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "B007" in data["answer"]
    assert "session_id" in data
    assert isinstance(data["tools_used"], list)
    assert len(data["tools_used"]) >= 1
    tool_names = [t["tool"] for t in data["tools_used"]]
    assert "get_building_summary" in tool_names
    assert "request_id" in data
    assert data["request_id"] != ""


@pytest.mark.asyncio
async def test_health_check(e2e_env):
    """Health endpoint returns 200."""
    async with AsyncClient(transport=ASGITransport(app=e2e_env), base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
