"""MCP integration tests for schema tools: list_tables and describe_table."""

from __future__ import annotations


class TestListTables:
    async def test_returns_tables_key(self, mcp_client):
        result = await mcp_client.call_tool("list_tables")
        data = result.data
        assert "tables" in data, f"Expected 'tables' key, got: {data.keys()}"

    async def test_returns_at_least_two_tables(self, mcp_client):
        result = await mcp_client.call_tool("list_tables")
        tables = result.data["tables"]
        assert len(tables) >= 2

    async def test_buildings_table_is_present(self, mcp_client):
        result = await mcp_client.call_tool("list_tables")
        names = {t["name"] for t in result.data["tables"]}
        assert "buildings" in names

    async def test_energy_readings_table_is_present(self, mcp_client):
        result = await mcp_client.call_tool("list_tables")
        names = {t["name"] for t in result.data["tables"]}
        assert "energy_readings" in names

    async def test_each_table_has_description(self, mcp_client):
        result = await mcp_client.call_tool("list_tables")
        for table in result.data["tables"]:
            assert table.get("description"), f"Table {table['name']} has no description"

    async def test_is_not_error(self, mcp_client):
        result = await mcp_client.call_tool("list_tables")
        assert not result.is_error
        assert "error" not in result.data


class TestDescribeTable:
    async def test_buildings_returns_columns(self, mcp_client):
        result = await mcp_client.call_tool("describe_table", {"table_name": "buildings"})
        data = result.data
        assert not result.is_error
        assert "columns" in data
        assert len(data["columns"]) > 0

    async def test_buildings_has_id_column(self, mcp_client):
        result = await mcp_client.call_tool("describe_table", {"table_name": "buildings"})
        col_names = {c["name"] for c in result.data["columns"]}
        assert "id" in col_names

    async def test_energy_readings_returns_columns(self, mcp_client):
        result = await mcp_client.call_tool("describe_table", {"table_name": "energy_readings"})
        data = result.data
        assert not result.is_error
        assert "columns" in data
        assert len(data["columns"]) > 0

    async def test_energy_readings_has_kwh_column(self, mcp_client):
        result = await mcp_client.call_tool("describe_table", {"table_name": "energy_readings"})
        col_names = {c["name"] for c in result.data["columns"]}
        assert "kwh" in col_names

    async def test_each_column_has_data_type(self, mcp_client):
        result = await mcp_client.call_tool("describe_table", {"table_name": "buildings"})
        for col in result.data["columns"]:
            assert col.get("data_type"), f"Column {col['name']} has no data_type"

    async def test_unknown_table_returns_error(self, mcp_client):
        result = await mcp_client.call_tool("describe_table", {"table_name": "nonexistent_table"})
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "TABLE_NOT_FOUND"

    async def test_sql_injection_attempt_returns_error(self, mcp_client):
        result = await mcp_client.call_tool(
            "describe_table", {"table_name": "buildings; DROP TABLE buildings"}
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "TABLE_NOT_FOUND"

    async def test_system_table_attempt_returns_error(self, mcp_client):
        result = await mcp_client.call_tool("describe_table", {"table_name": "sqlite_master"})
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "TABLE_NOT_FOUND"

    async def test_sessions_table_not_exposed(self, mcp_client):
        """Internal sessions table must not be accessible."""
        result = await mcp_client.call_tool("describe_table", {"table_name": "sessions"})
        data = result.data
        assert "error" in data

    async def test_evaluation_tables_not_exposed(self, mcp_client):
        """Internal evaluation tables must not be accessible."""
        for table in ("evaluation_runs", "evaluation_records"):
            result = await mcp_client.call_tool("describe_table", {"table_name": table})
            assert "error" in result.data, f"Table '{table}' should not be exposed"
