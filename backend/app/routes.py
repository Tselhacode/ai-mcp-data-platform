"""FastAPI route handlers -- thin routing only.

No LangChain imports. No business logic. Routes call AgentService only.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.dependencies import get_agent_service
from app.models import HealthResponse, QueryRequest, QueryResponse, ToolUsageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(
    request: QueryRequest,
    service: object = Depends(get_agent_service),
) -> QueryResponse:
    """Submit a natural-language question to the AI analyst.

    The agent selects and calls MCP tools to query the energy database,
    then returns a grounded answer.
    """
    try:
        result = await service.run(  # type: ignore[attr-defined]
            question=request.question,
            session_id=request.session_id,
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
        )
    except Exception:
        logger.exception("query_endpoint error")
        return QueryResponse(
            session_id=request.session_id or "",
            answer="An error occurred processing your question. Please try again.",
            tools_used=[],
            latency_ms=0,
        )


@router.get("/health", response_model=HealthResponse)
async def health_endpoint() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="ok")
