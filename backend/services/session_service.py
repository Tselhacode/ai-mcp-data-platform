"""Session management service.

Pure Python service. No LangChain, no FastMCP, no FastAPI imports permitted.
Wraps SessionRepositoryProtocol for conversation history management.

Supports two modes:
  1. Injected repository (legacy, used in some tests)
  2. Session factory (production) - creates a fresh session per operation
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from data.models import Session, SessionTurn
from data.repositories.protocols import SessionRepositoryProtocol

logger = logging.getLogger(__name__)


class SessionService:
    """Manages conversation sessions and turns.

    Accepts either a repository directly or a session_factory.
    When session_factory is provided, a fresh DB session is created
    per operation to avoid holding a long-lived connection.
    """

    def __init__(
        self,
        repo: SessionRepositoryProtocol | None = None,
        session_factory: Any | None = None,
    ) -> None:
        self._repo = repo
        self._session_factory = session_factory
        if repo is None and session_factory is None:
            raise ValueError("Either repo or session_factory must be provided")

    def _get_repo(self) -> tuple[SessionRepositoryProtocol, Any]:
        """Return a repository and optionally a session to close.

        Returns:
            (repo, session_or_none) - if session_or_none is not None,
            caller must close it after use.
        """
        if self._repo is not None:
            return self._repo, None
        # Import here to avoid circular imports
        from data.repositories.session import SQLAlchemySessionRepository

        assert self._session_factory is not None  # guaranteed by __init__
        session = self._session_factory()
        return SQLAlchemySessionRepository(session), session

    async def create_or_get_session(self, session_id: str | None) -> str:
        """Return an existing session ID or create a new one.

        Args:
            session_id: Existing session ID, or None to create a new one.

        Returns:
            The session ID (existing or newly created).
        """
        repo, db_session = self._get_repo()
        try:
            if session_id is not None:
                existing = await repo.get_session(session_id)
                if existing is not None:
                    return session_id
                # Session ID provided but not found -- create it
                await repo.create_session(session_id)
                return session_id

            new_id = str(uuid.uuid4())
            await repo.create_session(new_id)
            logger.debug("Created new session", extra={"session_id": new_id})
            return new_id
        finally:
            if db_session is not None:
                await db_session.close()

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
        """Persist a conversation turn.

        Args:
            session_id: Session UUID.
            question: User question text.
            answer: LLM final answer text.
            tools_called: List of tool call records (serializable).
            model: LLM model ID.
            provider: LLM provider name.
            latency_ms: Response latency in milliseconds.

        Returns:
            The persisted SessionTurn.
        """
        repo, db_session = self._get_repo()
        try:
            return await repo.save_turn(
                session_id=session_id,
                question=question,
                answer=answer,
                tools_called=tools_called,
                model=model,
                provider=provider,
                latency_ms=latency_ms,
            )
        finally:
            if db_session is not None:
                await db_session.close()

    async def get_session(self, session_id: str) -> Session | None:
        """Return a session by ID, or None if not found.

        Args:
            session_id: Session UUID.

        Returns:
            Session if found, else None.
        """
        repo, db_session = self._get_repo()
        try:
            return await repo.get_session(session_id)
        finally:
            if db_session is not None:
                await db_session.close()

    async def list_sessions(self, limit: int = 20) -> list[Session]:
        """Return recent sessions ordered by last_active descending.

        Args:
            limit: Maximum number of sessions to return (default 20).

        Returns:
            List of Session objects.
        """
        repo, db_session = self._get_repo()
        try:
            return await repo.list_sessions(limit=limit)
        finally:
            if db_session is not None:
                await db_session.close()

    async def get_history(self, session_id: str) -> list[SessionTurn]:
        """Return all turns for a session in chronological order.

        Args:
            session_id: Session UUID.

        Returns:
            List of SessionTurn objects ordered by created_at ascending.
        """
        repo, db_session = self._get_repo()
        try:
            return await repo.get_history(session_id)
        finally:
            if db_session is not None:
                await db_session.close()
