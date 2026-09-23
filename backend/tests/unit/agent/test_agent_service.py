"""Tests for AgentService using FakeChatModel and fake tools."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from langchain_core.tools import tool

from agent.agent_service import AgentService
from data.models import Session, SessionTurn
from llm.fake import FakeChatModel, ScriptedResponse
from services.session_service import SessionService

# ---------------------------------------------------------------------------
# Fake session repository for unit tests
# ---------------------------------------------------------------------------


class FakeSessionRepository:
    """In-memory session repository for unit tests."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._turns: list[SessionTurn] = []
        self._turn_id = 0

    async def create_session(self, session_id: str) -> Session:
        now = datetime.now(UTC).replace(tzinfo=None)
        session = Session(id=session_id, created_at=now, last_active=now)
        self._sessions[session_id] = session
        return session

    async def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    async def update_last_active(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].last_active = datetime.now(UTC).replace(tzinfo=None)

    async def get_history(self, session_id: str) -> list[SessionTurn]:
        return [t for t in self._turns if t.session_id == session_id]

    async def save_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
        tools_called: list[object],
        model: str,
        provider: str,
        latency_ms: int,
    ) -> SessionTurn:
        if session_id not in self._sessions:
            await self.create_session(session_id)
        self._turn_id += 1
        now = datetime.now(UTC).replace(tzinfo=None)
        turn = SessionTurn(
            id=self._turn_id,
            session_id=session_id,
            question=question,
            answer=answer,
            tools_called=tools_called,
            model=model,
            provider=provider,
            latency_ms=latency_ms,
            created_at=now,
        )
        self._turns.append(turn)
        return turn


# ---------------------------------------------------------------------------
# Fake LangChain tools for unit tests
# ---------------------------------------------------------------------------


@tool
def list_tables() -> str:
    """List available tables."""
    return '{"tables": [{"name": "buildings"}, {"name": "energy_readings"}]}'


@tool
def get_building_summary(building_id: str, start_date: str, end_date: str) -> str:
    """Get building summary."""
    return '{"building_id": "B007", "total_kwh": 9200.0}'


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_repo():
    return FakeSessionRepository()


@pytest.fixture
def simple_agent_service(fake_repo):
    """Agent service with a simple scripted LLM that just answers."""
    fake_llm = FakeChatModel(
        script=[
            ScriptedResponse(content="There are 20 buildings in the dataset."),
        ]
    )
    return AgentService(
        llm=fake_llm,
        tools=[list_tables, get_building_summary],
        session_service=SessionService(repo=fake_repo),
    )


@pytest.mark.asyncio
async def test_run_returns_agent_result(simple_agent_service):
    result = await simple_agent_service.run(
        question="How many buildings are there?",
    )
    assert result.answer == "There are 20 buildings in the dataset."
    assert result.session_id is not None
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_run_creates_session(simple_agent_service, fake_repo):
    result = await simple_agent_service.run(
        question="Test question",
    )
    # Session should have been created
    session = await fake_repo.get_session(result.session_id)
    assert session is not None


@pytest.mark.asyncio
async def test_run_saves_turn(simple_agent_service, fake_repo):
    result = await simple_agent_service.run(
        question="Test question",
        session_id=None,
    )
    turns = await fake_repo.get_history(result.session_id)
    assert len(turns) == 1
    assert turns[0].question == "Test question"


@pytest.mark.asyncio
async def test_run_with_existing_session(fake_repo):
    # Create a session first
    await fake_repo.create_session("existing-session")

    fake_llm = FakeChatModel(
        script=[
            ScriptedResponse(content="Answer 1"),
        ]
    )
    service = AgentService(
        llm=fake_llm,
        tools=[list_tables],
        session_service=SessionService(repo=fake_repo),
    )

    result = await service.run(
        question="Question",
        session_id="existing-session",
    )
    assert result.session_id == "existing-session"


@pytest.mark.asyncio
async def test_run_with_tool_calling(fake_repo):
    """Test agent service with a tool-calling scripted response."""
    fake_llm = FakeChatModel(
        script=[
            ScriptedResponse(
                tool_calls=[{"name": "list_tables", "args": {}, "id": "c1"}],
            ),
            ScriptedResponse(content="There are 2 tables: buildings and energy_readings."),
        ]
    )
    service = AgentService(
        llm=fake_llm,
        tools=[list_tables, get_building_summary],
        session_service=SessionService(repo=fake_repo),
    )

    result = await service.run(question="What tables are available?")
    assert "tables" in result.answer.lower() or "buildings" in result.answer.lower()
    assert len(result.tools_used) >= 1
