"""FastAPI route handlers -- thin routing only.

No LangChain imports. No business logic. Routes call AgentService only.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Request

from app.dependencies import get_agent_service
from app.models import HealthResponse, QueryRequest, QueryResponse, ToolUsageResponse

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


@router.get("/health", response_model=HealthResponse)
async def health_endpoint() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="ok")
