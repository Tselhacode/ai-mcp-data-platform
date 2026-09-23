"""AnalystAgent -- LangChain agent wrapper using LangGraph create_react_agent.

LangChain lives in this module. The agent is a LangGraph ReAct agent
that uses tool-calling to answer questions about energy data.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from agent.schemas import AgentResult, ToolUsage

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an energy analytics assistant. "
    "Use the available tools to query building energy consumption data. "
    "Always ground your answers in the data returned by tools. "
    "If a tool returns an error, explain it to the user clearly. "
    "All tools are read-only -- you cannot modify data."
)


class AnalystAgent:
    """Wraps a LangGraph ReAct agent for energy analytics.

    Constructed with a BaseChatModel and a list of LangChain tools.
    The agent manages the tool-calling loop internally.
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool],
        max_iterations: int = 10,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._max_iterations = max_iterations
        self._agent = create_react_agent(
            llm,
            tools,
            prompt=_SYSTEM_PROMPT,
        )

    async def invoke(
        self, question: str, history: list[dict[str, str]] | None = None
    ) -> AgentResult:
        """Run the agent with a question and optional conversation history.

        Args:
            question: The user's natural-language question.
            history: Optional prior conversation turns as list of
                     {"role": "user"|"assistant", "content": "..."} dicts.

        Returns:
            AgentResult with the answer, tools used, and metadata.
        """
        messages: list[tuple[str, str] | dict[str, Any]] = []

        # Add history if provided
        if history:
            for turn in history:
                messages.append((turn["role"], turn["content"]))

        messages.append(("human", question))

        result = await self._agent.ainvoke(
            {"messages": messages},
            config={"recursion_limit": self._max_iterations * 2 + 1},
        )

        # Extract final answer and tool usage from the message history
        result_messages: list[BaseMessage] = result.get("messages", [])
        tools_used = _extract_tool_usage(result_messages)
        answer = _extract_final_answer(result_messages)

        return AgentResult(
            answer=answer,
            session_id=None,  # Set by AgentService
            tools_used=tools_used,
            latency_ms=0,  # Set by AgentService
        )


def _extract_final_answer(messages: list[BaseMessage]) -> str:
    """Extract the final text answer from the agent message list."""
    # Walk backwards to find the last AI message with content
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            return str(msg.content)
    # Fallback: return the last message content
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return str(msg.content)
    return ""


def _extract_tool_usage(messages: list[BaseMessage]) -> list[ToolUsage]:
    """Extract tool usage records from the agent message list."""
    tool_calls_by_id: dict[str, dict[str, Any]] = {}

    # Collect tool calls from AIMessages
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                call_id: str = tc.get("id") or ""
                tool_calls_by_id[call_id] = {
                    "name": tc.get("name", ""),
                    "args": tc.get("args", {}),
                }

    # Match tool results from ToolMessages
    for msg in messages:
        if isinstance(msg, ToolMessage):
            call_id = msg.tool_call_id
            if call_id in tool_calls_by_id:
                content = str(msg.content) if msg.content else ""
                tool_calls_by_id[call_id]["result"] = content[:200]

    return [
        ToolUsage(
            tool=info["name"],
            args=info["args"],
            result_summary=info.get("result", "")[:200],
        )
        for info in tool_calls_by_id.values()
    ]
