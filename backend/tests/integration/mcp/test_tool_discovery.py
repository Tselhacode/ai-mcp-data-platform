"""MCP contract tests: tool discovery and schema validation.

Verifies that all 5 expected tools are registered, have correct names,
non-empty descriptions, and valid parameter schemas.
"""

from __future__ import annotations

EXPECTED_TOOLS = {
    "list_tables",
    "describe_table",
    "run_readonly_query",
    "get_building_summary",
    "get_consumption_trend",
}


class TestToolDiscovery:
    async def test_all_expected_tools_are_registered(self, mcp_client):
        tools = await mcp_client.list_tools()
        tool_names = {t.name for t in tools}
        assert EXPECTED_TOOLS == tool_names, (
            f"Tool mismatch. Expected: {EXPECTED_TOOLS}. Got: {tool_names}"
        )

    async def test_tool_count_is_five(self, mcp_client):
        tools = await mcp_client.list_tools()
        assert len(tools) == 5

    async def test_list_tables_has_description(self, mcp_client):
        tools = await mcp_client.list_tools()
        tool = next(t for t in tools if t.name == "list_tables")
        assert tool.description, "list_tables must have a non-empty description"
        assert len(tool.description) > 20, "Description is too short to be useful"

    async def test_describe_table_has_description(self, mcp_client):
        tools = await mcp_client.list_tools()
        tool = next(t for t in tools if t.name == "describe_table")
        assert tool.description, "describe_table must have a non-empty description"

    async def test_run_readonly_query_has_description(self, mcp_client):
        tools = await mcp_client.list_tools()
        tool = next(t for t in tools if t.name == "run_readonly_query")
        assert tool.description, "run_readonly_query must have a non-empty description"

    async def test_get_building_summary_has_description(self, mcp_client):
        tools = await mcp_client.list_tools()
        tool = next(t for t in tools if t.name == "get_building_summary")
        assert tool.description, "get_building_summary must have a non-empty description"

    async def test_get_consumption_trend_has_description(self, mcp_client):
        tools = await mcp_client.list_tools()
        tool = next(t for t in tools if t.name == "get_consumption_trend")
        assert tool.description, "get_consumption_trend must have a non-empty description"

    async def test_describe_table_has_table_name_parameter(self, mcp_client):
        tools = await mcp_client.list_tools()
        tool = next(t for t in tools if t.name == "describe_table")
        # FastMCP SDK v2 uses input_schema
        schema = tool.input_schema
        assert "table_name" in schema.get("properties", {}), (
            "describe_table must have a 'table_name' parameter"
        )

    async def test_run_readonly_query_has_query_parameter(self, mcp_client):
        tools = await mcp_client.list_tools()
        tool = next(t for t in tools if t.name == "run_readonly_query")
        schema = tool.input_schema
        assert "query" in schema.get("properties", {}), (
            "run_readonly_query must have a 'query' parameter"
        )

    async def test_get_building_summary_has_required_parameters(self, mcp_client):
        tools = await mcp_client.list_tools()
        tool = next(t for t in tools if t.name == "get_building_summary")
        schema = tool.input_schema
        props = schema.get("properties", {})
        required = schema.get("required", [])
        assert "building_id" in props
        assert "start_date" in props
        assert "end_date" in props
        assert "building_id" in required
        assert "start_date" in required
        assert "end_date" in required

    async def test_get_consumption_trend_has_required_parameters(self, mcp_client):
        tools = await mcp_client.list_tools()
        tool = next(t for t in tools if t.name == "get_consumption_trend")
        schema = tool.input_schema
        props = schema.get("properties", {})
        assert "start_date" in props
        assert "end_date" in props
        assert "granularity" in props
