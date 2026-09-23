"""Tests for GET /api/v1/health endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def test_settings():
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        llm_provider="fake",
        langsmith_tracing=False,
    )


@pytest.mark.asyncio
async def test_health_returns_ok(test_settings):
    from langchain_core.tools import tool

    from llm.fake import FakeChatModel

    @tool
    def dummy_tool() -> str:
        """Dummy tool."""
        return "ok"

    app = create_app(
        settings=test_settings,
        llm=FakeChatModel(script=[]),
        tools=[dummy_tool],
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
