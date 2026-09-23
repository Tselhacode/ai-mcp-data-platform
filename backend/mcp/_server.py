"""FastMCP server factory and entry point.

Creates and configures the FastMCP server with all registered tools.
This module is the public API for the MCP server package.

Transport is configured via the MCP_TRANSPORT environment variable:
    stdio  — for local development and Docker Compose (default)
    sse    — for AWS ECS (network deployment)

No LangChain imports permitted.
"""

from __future__ import annotations

import logging

from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mcp.dependencies import get_session_factory, make_session_factory
from mcp.tools.analytics_tools import register_analytics_tools
from mcp.tools.query_tools import register_query_tools
from mcp.tools.schema_tools import register_schema_tools

logger = logging.getLogger(__name__)


def create_mcp_server(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> FastMCP:
    """Create and configure the FastMCP server with all tools registered.

    Args:
        session_factory: Optional session factory override (used in tests).
                         Defaults to the production factory from settings.

    Returns:
        Fully configured FastMCP server instance.
    """
    factory = session_factory or get_session_factory()

    mcp = FastMCP(
        name="ai-mcp-data-platform",
        instructions=(
            "You are an energy analytics assistant. "
            "Use the available tools to query building energy consumption data. "
            "Always use list_tables and describe_table before writing SQL queries. "
            "All tools are read-only — you cannot modify data."
        ),
    )

    # Register all tool groups
    register_schema_tools(mcp)
    register_query_tools(mcp, factory)
    register_analytics_tools(mcp, factory)

    logger.info(
        "MCP server created",
        extra={"server_name": "ai-mcp-data-platform", "tool_count": 5},
    )
    return mcp


def run_server() -> None:
    """Run the MCP server using stdio transport (for local/Docker use).

    Called when this module is executed directly:
        uv run python -m mcp._server
    """
    from app.config import get_settings
    from logging_config import configure_logging

    settings = get_settings()
    configure_logging(level=settings.log_level)

    mcp = create_mcp_server()

    transport = settings.mcp_transport
    logger.info("Starting MCP server", extra={"transport": transport})

    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse")


# Allow running directly: uv run python -m mcp._server
if __name__ == "__main__":
    run_server()


def create_mcp_server_for_test(database_url: str) -> FastMCP:
    """Create a FastMCP server configured for testing with a specific DB URL.

    Args:
        database_url: SQLAlchemy async URL for the test database.

    Returns:
        Fully configured FastMCP server using the test database.
    """
    factory = make_session_factory(database_url)
    return create_mcp_server(session_factory=factory)
