"""FastAPI request/response Pydantic models.

No LangChain imports permitted.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request body for POST /api/v1/query."""

    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None


class ToolUsageResponse(BaseModel):
    """Tool usage record in query response."""

    tool: str
    args: dict[str, object]
    result_summary: str


class QueryResponse(BaseModel):
    """Response body for POST /api/v1/query."""

    session_id: str
    answer: str
    tools_used: list[ToolUsageResponse]
    latency_ms: int
    request_id: str = ""


class HealthResponse(BaseModel):
    """Response body for GET /api/v1/health."""

    status: str


class SessionTurnResponse(BaseModel):
    """A single conversation turn within a session."""

    question: str
    answer: str
    tools_used: list[ToolUsageResponse]
    latency_ms: int
    created_at: str


class SessionDetailResponse(BaseModel):
    """Full session with all conversation turns."""

    session_id: str
    created_at: str
    last_active: str
    turns: list[SessionTurnResponse]


class SessionSummary(BaseModel):
    """Lightweight session entry for the sessions list."""

    session_id: str
    created_at: str
    last_active: str
    turn_count: int


class SessionListResponse(BaseModel):
    """Response body for GET /api/v1/sessions."""

    sessions: list[SessionSummary]
    total: int
