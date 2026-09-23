"""Agent input/output schemas.

Pydantic models for the agent layer's public interface.
No LangChain types in the public interface.
"""

from __future__ import annotations

from pydantic import BaseModel


class ToolUsage(BaseModel):
    """Record of a single tool invocation by the agent."""

    tool: str
    args: dict[str, object]
    result_summary: str


class AgentResult(BaseModel):
    """Result of an agent invocation."""

    answer: str
    session_id: str | None
    tools_used: list[ToolUsage]
    latency_ms: int
