"""Tests for POST /api/v1/query endpoint."""

import pytest
from langchain_core.tools import tool

from app.config import Settings
from app.dependencies import set_agent_service
from app.main import create_app
from llm.fake import FakeChatModel, ScriptedResponse


@tool
def list_tables() -> str:
    """List available tables."""
    return '{"tables": [{"name": "buildings"}, {"name": "energy_readings"}]}'


@pytest.fixture
def test_settings():
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        llm_provider="fake",
        langsmith_tracing=False,
    )


@pytest.mark.asyncio
async def test_query_endpoint_returns_answer(test_settings):
    from datetime import UTC, datetime

    from agent.agent_service import AgentService
    from data.models import Session, SessionTurn
    from services.session_service import SessionService

    # Use in-memory fake session repo to avoid DB setup
    class FakeSessionRepo:
        def __init__(self):
            self._sessions = {}
            self._turns = []
            self._tid = 0

        async def create_session(self, session_id):
            now = datetime.now(UTC).replace(tzinfo=None)
            s = Session(id=session_id, created_at=now, last_active=now)
            self._sessions[session_id] = s
            return s

        async def get_session(self, session_id):
            return self._sessions.get(session_id)

        async def update_last_active(self, session_id):
            pass

        async def get_history(self, session_id):
            return [t for t in self._turns if t.session_id == session_id]

        async def save_turn(
            self, session_id, question, answer, tools_called, model, provider, latency_ms
        ):
            if session_id not in self._sessions:
                await self.create_session(session_id)
            self._tid += 1
            now = datetime.now(UTC).replace(tzinfo=None)
            t = SessionTurn(
                id=self._tid,
                session_id=session_id,
                question=question,
                answer=answer,
                tools_called=tools_called,
                model=model,
                provider=provider,
                latency_ms=latency_ms,
                created_at=now,
            )
            self._turns.append(t)
            return t

    fake_llm = FakeChatModel(
        script=[
            ScriptedResponse(content="There are 20 buildings in the dataset."),
        ]
    )
    session_svc = SessionService(repo=FakeSessionRepo())
    agent_svc = AgentService(
        llm=fake_llm,
        tools=[list_tables],
        session_service=session_svc,
    )

    # Set the agent service directly (bypassing lifespan)
    set_agent_service(agent_svc)

    app = create_app(settings=test_settings, llm=fake_llm, tools=[list_tables])
    # Override the dependency
    from app.dependencies import get_agent_service as _get

    app.dependency_overrides[_get] = lambda: agent_svc

    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/query",
            json={"question": "How many buildings are there?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "session_id" in data
    assert isinstance(data["tools_used"], list)
    assert data["answer"] == "There are 20 buildings in the dataset."


@pytest.mark.asyncio
async def test_query_with_session_id(test_settings):
    from datetime import UTC, datetime

    from agent.agent_service import AgentService
    from data.models import Session, SessionTurn
    from services.session_service import SessionService

    class FakeSessionRepo:
        def __init__(self):
            self._sessions = {}
            self._turns = []
            self._tid = 0

        async def create_session(self, session_id):
            now = datetime.now(UTC).replace(tzinfo=None)
            s = Session(id=session_id, created_at=now, last_active=now)
            self._sessions[session_id] = s
            return s

        async def get_session(self, session_id):
            return self._sessions.get(session_id)

        async def update_last_active(self, session_id):
            pass

        async def get_history(self, session_id):
            return [t for t in self._turns if t.session_id == session_id]

        async def save_turn(
            self, session_id, question, answer, tools_called, model, provider, latency_ms
        ):
            if session_id not in self._sessions:
                await self.create_session(session_id)
            self._tid += 1
            now = datetime.now(UTC).replace(tzinfo=None)
            t = SessionTurn(
                id=self._tid,
                session_id=session_id,
                question=question,
                answer=answer,
                tools_called=tools_called,
                model=model,
                provider=provider,
                latency_ms=latency_ms,
                created_at=now,
            )
            self._turns.append(t)
            return t

    fake_llm = FakeChatModel(
        script=[
            ScriptedResponse(content="Answer one."),
        ]
    )
    session_svc = SessionService(repo=FakeSessionRepo())
    agent_svc = AgentService(
        llm=fake_llm,
        tools=[list_tables],
        session_service=session_svc,
    )

    app = create_app(settings=test_settings, llm=fake_llm, tools=[list_tables])
    from app.dependencies import get_agent_service as _get

    app.dependency_overrides[_get] = lambda: agent_svc

    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/query",
            json={"question": "Test", "session_id": "test-session-123"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "test-session-123"
