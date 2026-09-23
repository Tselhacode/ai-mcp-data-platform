"""AgentService -- application-level entry point for AI-driven queries.

This is what FastAPI routes call. Coordinates session management
and agent invocation. LangChain imports are permitted here (agent layer).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from agent.analyst_agent import AnalystAgent
from agent.schemas import AgentResult
from services.session_service import SessionService

logger = logging.getLogger(__name__)


class AgentService:
    """Application-level entry point for AI queries.

    Manages session lifecycle and delegates to AnalystAgent for
    the actual LLM tool-calling loop.
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: Sequence[BaseTool],
        session_service: SessionService,
        max_iterations: int = 10,
    ) -> None:
        self._llm = llm
        self._session_service = session_service
        self._analyst = AnalystAgent(
            llm=llm,
            tools=tools,
            max_iterations=max_iterations,
        )

    async def run(
        self,
        question: str,
        session_id: str | None = None,
    ) -> AgentResult:
        """Run an AI query with optional session context.

        Args:
            question: The user's natural-language question.
            session_id: Optional existing session ID. Creates new if None.

        Returns:
            AgentResult with the answer, tools used, session ID, and latency.
        """
        start = time.monotonic()

        # Create or retrieve session
        sid = await self._session_service.create_or_get_session(session_id)

        # Get conversation history for context
        history_turns = await self._session_service.get_history(sid)
        history = [{"role": "user", "content": t.question} for t in history_turns] + [
            {"role": "assistant", "content": t.answer} for t in history_turns
        ]
        # Interleave properly: user, assistant, user, assistant...
        history = []
        for t in history_turns:
            history.append({"role": "user", "content": t.question})
            history.append({"role": "assistant", "content": t.answer})

        # Run the agent
        result = await self._analyst.invoke(question, history=history if history else None)

        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Save the turn
        tools_called: list[object] = [
            {"tool": tu.tool, "args": tu.args, "result_summary": tu.result_summary}
            for tu in result.tools_used
        ]
        await self._session_service.save_turn(
            session_id=sid,
            question=question,
            answer=result.answer,
            tools_called=tools_called,
            model=getattr(self._llm, "model_id", "fake"),
            provider="bedrock" if hasattr(self._llm, "model_id") else "fake",
            latency_ms=elapsed_ms,
        )

        logger.info(
            "query_completed",
            extra={
                "session_id": sid,
                "question": question[:100],
                "answer": result.answer[:100],
                "tools_used": [tu.tool for tu in result.tools_used],
                "latency_ms": elapsed_ms,
            },
        )

        return AgentResult(
            answer=result.answer,
            session_id=sid,
            tools_used=result.tools_used,
            latency_ms=elapsed_ms,
        )
