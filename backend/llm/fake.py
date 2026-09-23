"""FakeChatModel for deterministic testing of the LangChain agent layer.

Replays a scripted list of responses in order. Makes no network calls.
Supports tool-use sequences via AIMessage with tool_calls.

No provider-specific imports (langchain_aws, boto3, etc.) permitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ConfigDict, Field


@dataclass
class ScriptedResponse:
    """One scripted LLM response in a multi-turn conversation.

    Attributes:
        content: Text content of the response (mutually exclusive with tool_calls
                 in practice, but both can be set).
        tool_calls: List of tool calls the LLM should make. Each is a dict with
                    keys 'name', 'args', 'id'.
    """

    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class FakeChatModel(BaseChatModel):
    """Deterministic fake LangChain chat model for testing.

    Replays a scripted list of responses in order. Raises ValueError
    when the script is exhausted.

    Usage:
        fake = FakeChatModel(script=[
            ScriptedResponse(tool_calls=[{"name": "list_tables", "args": {}, "id": "c1"}]),
            ScriptedResponse(content="The answer is 42."),
        ])
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    script: list[ScriptedResponse] = Field(default_factory=list)
    _call_index: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake-chat-model"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self._call_index >= len(self.script):
            raise ValueError("FakeChatModel script exhausted")

        response = self.script[self._call_index]
        self._call_index += 1

        message = AIMessage(
            content=response.content,
            tool_calls=response.tool_calls if response.tool_calls else [],
        )

        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(self, tools: Any, **kwargs: Any) -> FakeChatModel:
        """Return self — tools are ignored since responses are scripted."""
        return self
