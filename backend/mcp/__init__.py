"""MCP server package for the AI MCP Data Platform.

No LangChain imports are permitted in this package.

COMPATIBILITY NOTE
------------------
The name ``mcp`` is shared with the MCP SDK (a dependency of fastmcp).
This ``__init__.py`` performs two operations to resolve the conflict:

1. Extends ``__path__`` to include the MCP SDK's package directory so
   that submodule imports like ``from mcp.server.lowlevel...`` (used
   internally by fastmcp) resolve to the SDK, not this package.

2. Re-exports all public symbols from the MCP SDK's ``__init__.py``
   so that ``from mcp import MCPError`` (also used by fastmcp) works.

These operations are silent and have no effect when the SDK is not
installed (e.g. in minimal environments).
"""

from __future__ import annotations

import os as _os
import sys as _sys

# ── Step 1: extend __path__ to include the SDK's mcp directory ───────────────
# This allows Python to find SDK subpackages (mcp.server, mcp.client, etc.)
# through our package namespace.

_sdk_mcp_dir: str | None = None
for _sys_path_entry in _sys.path:
    if "site-packages" in _sys_path_entry:
        _candidate = _os.path.join(_sys_path_entry, "mcp")
        if _os.path.isdir(_candidate) and _candidate not in __path__:
            _sdk_mcp_dir = _candidate
            __path__.append(_candidate)
            break

# ── Step 2: re-export SDK top-level symbols ───────────────────────────────────
# fastmcp does ``from mcp import MCPError``, ``from mcp import GetPromptResult``,
# etc. These need to be available from our package.

if _sdk_mcp_dir is not None:
    try:
        from mcp_types import (
            CallToolRequest,
            ClientCapabilities,
            ClientNotification,
            ClientRequest,
            ClientResult,
            CompleteRequest,
            CreateMessageRequest,
            CreateMessageResult,
            CreateMessageResultWithTools,
            ErrorData,
            GetPromptRequest,
            GetPromptResult,
            Implementation,
            IncludeContext,
            InitializedNotification,
            InitializeRequest,
            InitializeResult,
            JSONRPCError,
            JSONRPCRequest,
            JSONRPCResponse,
            ListPromptsRequest,
            ListPromptsResult,
            ListResourcesRequest,
            ListResourcesResult,
            ListToolsResult,
            LoggingLevel,
            LoggingMessageNotification,
            Notification,
            PingRequest,
            ProgressNotification,
            PromptsCapability,
            ReadResourceRequest,
            ReadResourceResult,
            Resource,
            ResourcesCapability,
            ResourceUpdatedNotification,
            RootsCapability,
            SamplingCapability,
            SamplingContent,
            SamplingContextCapability,
            SamplingMessage,
            SamplingMessageContentBlock,
            SamplingToolsCapability,
            ServerCapabilities,
            ServerNotification,
            ServerRequest,
            ServerResult,
            SetLevelRequest,
            StopReason,
            SubscribeRequest,
            Tool,
            ToolChoice,
            ToolResultContent,
            ToolsCapability,
            ToolUseContent,
            UnsubscribeRequest,
        )
        from mcp_types import Role as SamplingRole

        # Subpackage imports (use the extended __path__ so they resolve to SDK)
        from .client._input_required import InputRequiredRoundsExceededError
        from .client.client import Client
        from .client.session import ClientSession
        from .client.session_group import ClientSessionGroup
        from .client.stdio import StdioServerParameters, stdio_client
        from .server.session import ServerSession
        from .server.stdio import stdio_server
        from .shared.exceptions import (
            MCPDeprecationWarning,
            MCPError,
            UrlElicitationRequiredError,
        )
        from .shared.uri_template import InvalidUriTemplate, UriTemplate

        __all__ = [
            "CallToolRequest",
            "Client",
            "ClientCapabilities",
            "ClientNotification",
            "ClientRequest",
            "ClientResult",
            "ClientSession",
            "ClientSessionGroup",
            "CompleteRequest",
            "CreateMessageRequest",
            "CreateMessageResult",
            "CreateMessageResultWithTools",
            "ErrorData",
            "GetPromptRequest",
            "GetPromptResult",
            "Implementation",
            "IncludeContext",
            "InitializeRequest",
            "InitializeResult",
            "InitializedNotification",
            "InputRequiredRoundsExceededError",
            "InvalidUriTemplate",
            "JSONRPCError",
            "JSONRPCRequest",
            "JSONRPCResponse",
            "ListPromptsRequest",
            "ListPromptsResult",
            "ListResourcesRequest",
            "ListResourcesResult",
            "ListToolsResult",
            "LoggingLevel",
            "LoggingMessageNotification",
            "MCPDeprecationWarning",
            "MCPError",
            "Notification",
            "PingRequest",
            "ProgressNotification",
            "PromptsCapability",
            "ReadResourceRequest",
            "ReadResourceResult",
            "Resource",
            "ResourceUpdatedNotification",
            "ResourcesCapability",
            "RootsCapability",
            "SamplingCapability",
            "SamplingContent",
            "SamplingContextCapability",
            "SamplingMessage",
            "SamplingMessageContentBlock",
            "SamplingRole",
            "SamplingToolsCapability",
            "ServerCapabilities",
            "ServerNotification",
            "ServerRequest",
            "ServerResult",
            "ServerSession",
            "SetLevelRequest",
            "StdioServerParameters",
            "StopReason",
            "SubscribeRequest",
            "Tool",
            "ToolChoice",
            "ToolResultContent",
            "ToolUseContent",
            "ToolsCapability",
            "UnsubscribeRequest",
            "UriTemplate",
            "UrlElicitationRequiredError",
            "stdio_client",
            "stdio_server",
        ]

    except ImportError:
        # SDK not available — skip re-exports. FastMCP will raise its own
        # ImportError with a helpful message.
        pass
