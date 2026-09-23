"""Tests for GET /api/v1/sessions and GET /api/v1/sessions/{session_id}."""

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.dependencies import get_session_service, set_session_service
from app.main import create_app
from data.models import Session, SessionTurn
from services.session_service import SessionService

# ---------------------------------------------------------------------------
# Shared fake repository and helpers
# ---------------------------------------------------------------------------


class FakeSessionRepo:
    """In-memory session repository for tests."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._turns: list[SessionTurn] = []
        self._tid = 0

    async def create_session(self, session_id: str) -> Session:
        now = datetime.now(UTC).replace(tzinfo=None)
        s = Session(id=session_id, created_at=now, last_active=now)
        self._sessions[session_id] = s
        return s

    async def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    async def update_last_active(self, session_id: str) -> None:
        pass

    async def list_sessions(self, limit: int = 20) -> list[Session]:
        sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.last_active,
            reverse=True,
        )
        return sessions[:limit]

    async def get_history(self, session_id: str) -> list[SessionTurn]:
        return [t for t in self._turns if t.session_id == session_id]

    async def save_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
        tools_called: object,
        model: str,
        provider: str,
        latency_ms: int,
    ) -> SessionTurn:
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


def _make_app_with_session_svc(session_svc: SessionService):
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        llm_provider="fake",
        langsmith_tracing=False,
    )
    app = create_app(settings=settings)
    set_session_service(session_svc)
    app.dependency_overrides[get_session_service] = lambda: session_svc
    return app


# ---------------------------------------------------------------------------
# GET /api/v1/sessions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sessions_empty():
    """Empty database returns empty sessions list."""
    repo = FakeSessionRepo()
    svc = SessionService(repo=repo)
    app = _make_app_with_session_svc(svc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sessions")

    assert response.status_code == 200
    data = response.json()
    assert data["sessions"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_sessions_returns_created_sessions():
    """Sessions created via save_turn appear in the list."""
    repo = FakeSessionRepo()
    svc = SessionService(repo=repo)
    app = _make_app_with_session_svc(svc)

    await svc.save_turn(
        session_id="session-aaa",
        question="What is B007?",
        answer="Building 7.",
        tools_called=[],
        model="fake",
        provider="fake",
        latency_ms=100,
    )
    await svc.save_turn(
        session_id="session-bbb",
        question="How many buildings?",
        answer="20.",
        tools_called=[],
        model="fake",
        provider="fake",
        latency_ms=50,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sessions")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    session_ids = {s["session_id"] for s in data["sessions"]}
    assert "session-aaa" in session_ids
    assert "session-bbb" in session_ids


@pytest.mark.asyncio
async def test_list_sessions_turn_count():
    """turn_count reflects the number of turns in each session."""
    repo = FakeSessionRepo()
    svc = SessionService(repo=repo)
    app = _make_app_with_session_svc(svc)

    for i in range(3):
        await svc.save_turn(
            session_id="session-multi",
            question=f"Q{i}",
            answer=f"A{i}",
            tools_called=[],
            model="fake",
            provider="fake",
            latency_ms=10,
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sessions")

    data = response.json()
    assert data["total"] == 1
    assert data["sessions"][0]["turn_count"] == 3


# ---------------------------------------------------------------------------
# GET /api/v1/sessions/{session_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_session_not_found():
    """Non-existent session returns 404."""
    repo = FakeSessionRepo()
    svc = SessionService(repo=repo)
    app = _make_app_with_session_svc(svc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sessions/does-not-exist")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_session_returns_turns():
    """Session detail includes all conversation turns in order."""
    repo = FakeSessionRepo()
    svc = SessionService(repo=repo)
    app = _make_app_with_session_svc(svc)

    await svc.save_turn(
        session_id="sess-detail",
        question="First question",
        answer="First answer",
        tools_called=[{"tool": "list_tables", "args": {}, "result_summary": ""}],
        model="fake",
        provider="fake",
        latency_ms=120,
    )
    await svc.save_turn(
        session_id="sess-detail",
        question="Second question",
        answer="Second answer",
        tools_called=[],
        model="fake",
        provider="fake",
        latency_ms=80,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sessions/sess-detail")

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "sess-detail"
    assert len(data["turns"]) == 2
    assert data["turns"][0]["question"] == "First question"
    assert data["turns"][0]["answer"] == "First answer"
    assert data["turns"][0]["latency_ms"] == 120
    assert len(data["turns"][0]["tools_used"]) == 1
    assert data["turns"][0]["tools_used"][0]["tool"] == "list_tables"
    assert data["turns"][1]["question"] == "Second question"


@pytest.mark.asyncio
async def test_get_session_has_timestamps():
    """Session detail response includes created_at and last_active."""
    repo = FakeSessionRepo()
    svc = SessionService(repo=repo)
    app = _make_app_with_session_svc(svc)

    await svc.save_turn(
        session_id="sess-ts",
        question="Q",
        answer="A",
        tools_called=[],
        model="fake",
        provider="fake",
        latency_ms=10,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sessions/sess-ts")

    data = response.json()
    assert "created_at" in data
    assert "last_active" in data
    # ISO 8601 format check
    assert "T" in data["created_at"]
