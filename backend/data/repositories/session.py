"""SQLAlchemy implementation of SessionRepositoryProtocol.

Handles conversation session and turn persistence.

No LangChain, FastMCP, or FastAPI imports are permitted in this module.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import Session, SessionTurn

logger = logging.getLogger(__name__)


class SQLAlchemySessionRepository:
    """Async SQLAlchemy implementation of the session repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_session(self, session_id: str) -> Session:
        """Create and persist a new conversation session.

        Args:
            session_id: UUID string to use as the session ID.

        Returns:
            The newly created Session.
        """
        now = datetime.now(UTC).replace(tzinfo=None)
        db_session = Session(
            id=session_id,
            created_at=now,
            last_active=now,
        )
        self._session.add(db_session)
        await self._session.commit()
        await self._session.refresh(db_session)
        logger.debug("Created session", extra={"session_id": session_id})
        return db_session

    async def get_session(self, session_id: str) -> Session | None:
        """Return an existing session by ID, or None.

        Args:
            session_id: The session UUID to look up.

        Returns:
            Session if found, else None.
        """
        result = await self._session.execute(select(Session).where(Session.id == session_id))
        return result.scalar_one_or_none()

    async def update_last_active(self, session_id: str) -> None:
        """Update last_active timestamp for a session.

        Args:
            session_id: The session UUID to update.
        """
        db_session = await self.get_session(session_id)
        if db_session is None:
            return
        db_session.last_active = datetime.now(UTC).replace(tzinfo=None)
        await self._session.commit()

    async def list_sessions(self, limit: int = 20) -> list[Session]:
        """Return recent sessions ordered by last_active descending.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of Session objects.
        """
        result = await self._session.execute(
            select(Session).order_by(Session.last_active.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_history(self, session_id: str) -> list[SessionTurn]:
        """Return all turns for a session in chronological order.

        Args:
            session_id: The session UUID.

        Returns:
            SessionTurn objects ordered by created_at ascending.
        """
        result = await self._session.execute(
            select(SessionTurn)
            .where(SessionTurn.session_id == session_id)
            .order_by(SessionTurn.created_at)
        )
        return list(result.scalars().all())

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
        """Persist a conversation turn, creating the session if needed.

        Args:
            session_id: Session UUID (created if not found).
            question: User question text.
            answer: LLM final answer text.
            tools_called: List of tool call records.
            model: LLM model ID.
            provider: LLM provider name.
            latency_ms: Response latency in milliseconds.

        Returns:
            The persisted SessionTurn.
        """
        # Ensure the session exists
        existing = await self.get_session(session_id)
        if existing is None:
            await self.create_session(session_id)
        else:
            await self.update_last_active(session_id)

        now = datetime.now(UTC).replace(tzinfo=None)
        turn = SessionTurn(
            session_id=session_id,
            question=question,
            answer=answer,
            tools_called=tools_called,
            model=model,
            provider=provider,
            latency_ms=latency_ms,
            created_at=now,
        )
        self._session.add(turn)
        await self._session.commit()
        await self._session.refresh(turn)
        logger.debug(
            "Saved session turn",
            extra={"session_id": session_id, "latency_ms": latency_ms},
        )
        return turn
