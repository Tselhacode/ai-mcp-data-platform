"""FastAPI application factory.

Creates and configures the FastAPI application. No LangChain imports.
The agent service is initialized during the lifespan and injected
via the dependency system.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.dependencies import set_agent_service
from app.routes import router
from logging_config import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialize services on startup, cleanup on shutdown."""
    settings: Settings = app.state.settings

    # Configure LangSmith environment variables
    if settings.langsmith_tracing:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        if settings.langsmith_api_key:
            os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    else:
        os.environ["LANGSMITH_TRACING"] = "false"

    # Import agent layer components here (lazy to avoid importing LangChain at module level)
    from agent.agent_service import AgentService
    from agent.mcp_client import load_mcp_tools
    from data.models import Base
    from data.repositories.session import SQLAlchemySessionRepository
    from llm.factory import create_llm
    from mcp._server import create_mcp_server
    from mcp.dependencies import make_session_factory
    from services.session_service import SessionService

    # Create LLM
    llm = app.state.llm if hasattr(app.state, "llm") and app.state.llm is not None else create_llm()

    # For in-memory test DBs, use a shared-cache URL so all connections share state
    db_url = settings.database_url
    if db_url == "sqlite+aiosqlite:///:memory:":
        import uuid as _uuid

        db_url = (
            f"sqlite+aiosqlite:///file:test_{_uuid.uuid4().hex}?mode=memory&cache=shared&uri=true"
        )

    session_factory = (
        app.state.session_factory
        if hasattr(app.state, "session_factory") and app.state.session_factory is not None
        else make_session_factory(db_url)
    )

    # Ensure tables exist (needed for test databases)
    from sqlalchemy.ext.asyncio import create_async_engine

    _engine = create_async_engine(
        db_url,
        echo=False,
        connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
    )
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _engine.dispose()

    # Rebuild session factory to use the same shared-cache URL
    if app.state.session_factory is None:
        session_factory = make_session_factory(db_url)

    # Create MCP server and load tools
    mcp_server = create_mcp_server(session_factory=session_factory)

    # Use pre-loaded tools if provided (for testing), otherwise load from MCP
    if hasattr(app.state, "tools") and app.state.tools is not None:
        tools = app.state.tools
    else:
        tools = await load_mcp_tools(mcp_server)

    # Create a persistent session for the session service
    # The session stays open for the application lifetime
    db_session = session_factory()
    session_repo = SQLAlchemySessionRepository(db_session)
    session_svc = SessionService(repo=session_repo)

    # Create agent service
    agent_service = AgentService(
        llm=llm,
        tools=tools,
        session_service=session_svc,
        max_iterations=settings.llm_max_iterations,
    )
    set_agent_service(agent_service)

    logger.info("Application started", extra={"llm_provider": settings.llm_provider})

    yield

    await db_session.close()
    logger.info("Application shutdown")


def create_app(
    settings: Settings | None = None,
    llm: Any | None = None,
    tools: list[Any] | None = None,
    session_factory: Any | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        settings: Optional settings override (defaults to env-based settings).
        llm: Optional LLM override (for testing with FakeChatModel).
        tools: Optional pre-loaded tools (for testing).
        session_factory: Optional session factory override (for testing).

    Returns:
        Configured FastAPI application.
    """
    if settings is None:
        settings = get_settings()

    configure_logging(level=settings.log_level)

    app = FastAPI(
        title="AI MCP Data Platform",
        description="AI Data Analyst API with MCP tool integration",
        version="0.1.0",
        lifespan=_lifespan,
    )

    # Store configuration on app state for lifespan access
    app.state.settings = settings
    app.state.llm = llm
    app.state.tools = tools
    app.state.session_factory = session_factory

    # CORS
    origins = [o.strip() for o in settings.cors_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    return app
