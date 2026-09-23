"""Tests for LLM factory."""

from llm.factory import create_llm
from llm.fake import FakeChatModel


def test_factory_creates_fake_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    llm = create_llm()
    assert isinstance(llm, FakeChatModel)


def test_factory_raises_for_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unknown_provider")
    import pytest

    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        create_llm()
