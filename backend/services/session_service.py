"""Session management service.

Pure Python service. No LangChain, no FastMCP, no FastAPI imports permitted.
Wraps SessionRepositoryProtocol for conversation history management.
"""

from __future__ import annotations

import logging
import uuid

from data.models import SessionTurn
from data.repositories.protocols import SessionRepositoryProtocol

logger = logging.getLogger(__name__)


class SessionService:
    """Manages conversation sessions and turns.

    Accepts a session repository via constructor injection.
    """

    def __init__(self, repo: SessionRepositoryProtocol) -> None:
        self._repo = repo

    async def create_or_get_session(self, session_id: str | None) -> str:
        """Return an existing session ID or create a new one.

        Args:
            session_id: Existing session ID, or None to create a new one.

        Returns:
            The session ID (existing or newly created).
        """
        if session_id is not None:
            existing = await self._repo.get_session(session_id)
            if existing is not None:
                return session_id
            # Session ID provided but not found -- create it
            await self._repo.create_session(session_id)
            return session_id

        new_id = str(uuid.uuid4())
        await self._repo.create_session(new_id)
        logger.debug("Created new session", extra={"session_id": new_id})
        return new_id

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
        return await self._repo.save_turn(
            session_id=session_id,
            question=question,
            answer=answer,
            tools_called=tools_called,
            model=model,
            provider=provider,
            latency_ms=latency_ms,
        )

    async def get_history(self, session_id: str) -> list[SessionTurn]:
        """Return all turns for a session in chronological order.

        Args:
            session_id: Session UUID.

        Returns:
            List of SessionTurn objects ordered by created_at ascending.
        """
        return await self._repo.get_history(session_id)
