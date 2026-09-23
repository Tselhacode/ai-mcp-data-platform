"""LLM factory — creates BaseChatModel instances from configuration.

This is the ONLY file that imports langchain_aws / ChatBedrock.
All other code uses langchain_core types only.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import get_settings


def create_llm() -> BaseChatModel:
    """Create a BaseChatModel instance based on application settings.

    Returns:
        A configured chat model (ChatBedrock for production, FakeChatModel for tests).

    Raises:
        ValueError: If LLM_PROVIDER is not a recognized value.
    """
    settings = get_settings()

    if settings.llm_provider == "fake":
        from llm.fake import FakeChatModel

        return FakeChatModel(script=[])

    elif settings.llm_provider == "bedrock":
        from langchain_aws import ChatBedrock

        return ChatBedrock(  # type: ignore[call-arg]  # langchain-aws Pydantic fields not in __init__ stub
            model_id=settings.llm_model,
            region_name=settings.aws_region,
            model_kwargs={
                "max_tokens": settings.llm_max_tokens,
                "temperature": 0,
            },
        )

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")
