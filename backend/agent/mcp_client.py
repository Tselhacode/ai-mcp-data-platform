"""MCP tool loader -- converts FastMCP tools to LangChain BaseTool instances.

Uses fastmcp.Client to connect to the FastMCP server in-process and
wraps each MCP tool as a LangChain StructuredTool.

LangChain imports are permitted in this module (agent layer).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastmcp import Client as FastMCPClient
from fastmcp import FastMCP
from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)


async def load_mcp_tools(mcp_server: FastMCP) -> list[StructuredTool]:
    """Load tools from a FastMCP server as LangChain StructuredTool instances.

    Connects to the FastMCP server in-process (no network), lists all tools,
    and creates a LangChain StructuredTool wrapper for each.

    Args:
        mcp_server: A FastMCP server instance.

    Returns:
        List of LangChain StructuredTool instances.
    """
    tools: list[StructuredTool] = []

    async with FastMCPClient(mcp_server) as client:
        mcp_tools = await client.list_tools()

        for mcp_tool in mcp_tools:
            tool_name = mcp_tool.name
            tool_description = mcp_tool.description or ""

            # Build the input schema from the MCP tool's input_schema (MCP SDK v2)
            input_schema = mcp_tool.input_schema if mcp_tool.input_schema else {}

            # Create a closure that captures the tool name for calling
            def _make_tool_fn(name: str) -> Any:
                async def _call_tool(**kwargs: Any) -> str:
                    async with FastMCPClient(mcp_server) as inner_client:
                        result = await inner_client.call_tool(name, kwargs)
                        # Extract text content from the result
                        if hasattr(result, "content") and result.content:
                            texts = []
                            for content_block in result.content:
                                if hasattr(content_block, "text"):
                                    texts.append(content_block.text)
                            return "\n".join(texts) if texts else json.dumps({"result": "ok"})
                        return json.dumps({"result": "ok"})

                return _call_tool

            lc_tool = StructuredTool.from_function(
                coroutine=_make_tool_fn(tool_name),
                name=tool_name,
                description=tool_description,
                args_schema=None,
            )
            # For parameterised tools, set args_schema to None post-construction to
            # prevent LangChain from applying the inferred **kwargs schema, which
            # would drop keyword arguments before they reach the underlying coroutine.
            if input_schema and "properties" in input_schema:
                lc_tool.args_schema = None  # type: ignore[assignment]  # StructuredTool accepts None at runtime

            tools.append(lc_tool)
            logger.debug("Loaded MCP tool as LangChain tool", extra={"tool_name": tool_name})

    logger.info(
        "Loaded MCP tools",
        extra={"tool_count": len(tools)},
    )
    return tools
