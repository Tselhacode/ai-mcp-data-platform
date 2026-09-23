"""Tests for FakeChatModel."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from llm.fake import FakeChatModel, ScriptedResponse


def test_fake_model_returns_scripted_content():
    fake = FakeChatModel(
        script=[
            ScriptedResponse(content="Hello world"),
        ]
    )
    result = fake.invoke([HumanMessage(content="Hi")])
    assert isinstance(result, AIMessage)
    assert result.content == "Hello world"


def test_fake_model_returns_tool_calls():
    fake = FakeChatModel(
        script=[
            ScriptedResponse(
                tool_calls=[{"name": "list_tables", "args": {}, "id": "c1"}],
            ),
        ]
    )
    result = fake.invoke([HumanMessage(content="Hi")])
    assert isinstance(result, AIMessage)
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "list_tables"


def test_fake_model_multiple_turns():
    fake = FakeChatModel(
        script=[
            ScriptedResponse(
                tool_calls=[{"name": "list_tables", "args": {}, "id": "c1"}],
            ),
            ScriptedResponse(content="The answer is 42."),
        ]
    )
    r1 = fake.invoke([HumanMessage(content="Step 1")])
    assert r1.tool_calls
    r2 = fake.invoke([HumanMessage(content="Step 2")])
    assert r2.content == "The answer is 42."


def test_fake_model_exhaustion():
    fake = FakeChatModel(
        script=[
            ScriptedResponse(content="Only one response"),
        ]
    )
    fake.invoke([HumanMessage(content="Hi")])
    with pytest.raises(ValueError, match="script exhausted"):
        fake.invoke([HumanMessage(content="Again")])


def test_fake_model_bind_tools_returns_self():
    fake = FakeChatModel(script=[])
    bound = fake.bind_tools([{"name": "test", "description": "test"}])
    assert bound is fake


def test_fake_model_llm_type():
    fake = FakeChatModel(script=[])
    assert fake._llm_type == "fake-chat-model"
