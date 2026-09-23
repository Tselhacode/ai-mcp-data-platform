"""FastAPI route handlers -- thin routing only.

No LangChain imports. No business logic. Routes call AgentService or SessionService only.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies import get_agent_service, get_session_service
from app.models import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    SessionDetailResponse,
    SessionListResponse,
    SessionSummary,
    SessionTurnResponse,
    ToolUsageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(
    request_body: QueryRequest,
    request: Request,
    service: object = Depends(get_agent_service),
) -> QueryResponse:
    """Submit a natural-language question to the AI analyst.

    The agent selects and calls MCP tools to query the energy database,
    then returns a grounded answer.
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    logger.info(
        "query_received",
        extra={
            "request_id": request_id,
            "question": request_body.question[:100],
        },
    )

    try:
        result = await service.run(  # type: ignore[attr-defined]
            question=request_body.question,
            session_id=request_body.session_id,
        )
        return QueryResponse(
            session_id=result.session_id or "",
            answer=result.answer,
            tools_used=[
                ToolUsageResponse(
                    tool=tu.tool,
                    args=tu.args,
                    result_summary=tu.result_summary,
                )
                for tu in result.tools_used
            ],
            latency_ms=result.latency_ms,
            request_id=request_id,
        )
    except Exception:
        logger.exception("query_endpoint error", extra={"request_id": request_id})
        return QueryResponse(
            session_id=request_body.session_id or "",
            answer="An error occurred processing your question. Please try again.",
            tools_used=[],
            latency_ms=0,
            request_id=request_id,
        )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions_endpoint(
    limit: int = 20,
    service: object = Depends(get_session_service),
) -> SessionListResponse:
    """List recent conversation sessions ordered by last activity."""
    sessions = await service.list_sessions(limit=limit)  # type: ignore[attr-defined]
    summaries = []
    for s in sessions:
        history = await service.get_history(s.id)  # type: ignore[attr-defined]
        summaries.append(
            SessionSummary(
                session_id=s.id,
                created_at=s.created_at.isoformat(),
                last_active=s.last_active.isoformat(),
                turn_count=len(history),
            )
        )
    return SessionListResponse(sessions=summaries, total=len(summaries))


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_endpoint(
    session_id: str,
    service: object = Depends(get_session_service),
) -> SessionDetailResponse:
    """Return a session and its full conversation history."""
    db_session_record = await service.get_session(session_id)  # type: ignore[attr-defined]
    if db_session_record is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    history = await service.get_history(session_id)  # type: ignore[attr-defined]

    turns = [
        SessionTurnResponse(
            question=t.question,
            answer=t.answer,
            tools_used=[
                ToolUsageResponse(
                    tool=tc.get("tool", ""),
                    args=tc.get("args", {}),
                    result_summary=tc.get("result_summary", ""),
                )
                for tc in (t.tools_called or [])
            ],
            latency_ms=t.latency_ms,
            created_at=t.created_at.isoformat(),
        )
        for t in history
    ]
    return SessionDetailResponse(
        session_id=session_id,
        created_at=db_session_record.created_at.isoformat(),
        last_active=db_session_record.last_active.isoformat(),
        turns=turns,
    )


@router.get("/health", response_model=HealthResponse)
async def health_endpoint() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="ok")
