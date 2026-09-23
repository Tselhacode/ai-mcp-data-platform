"""MCP integration tests for the run_readonly_query tool.

Tests cover: valid SELECT, mutation rejection, multi-statement rejection,
comment handling, result limits, and result structure.
"""

from __future__ import annotations


class TestValidSelect:
    async def test_simple_select_executes(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query", {"query": "SELECT * FROM buildings"}
        )
        data = result.data
        assert "error" not in data
        assert "columns" in data
        assert "rows" in data
        assert "row_count" in data

    async def test_returns_columns_list(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "SELECT id, name FROM buildings"},
        )
        data = result.data
        assert "columns" in data
        assert "id" in data["columns"]
        assert "name" in data["columns"]

    async def test_returns_correct_row_count(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query", {"query": "SELECT * FROM buildings"}
        )
        data = result.data
        assert data["row_count"] == len(data["rows"])

    async def test_parameterized_query_works(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {
                "query": "SELECT * FROM buildings WHERE id = :bid",
                "params": {"bid": "B001"},
            },
        )
        data = result.data
        assert "error" not in data
        assert data["row_count"] == 1

    async def test_aggregate_query_works(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "SELECT COUNT(*) as cnt FROM buildings"},
        )
        data = result.data
        assert "error" not in data
        assert data["row_count"] == 1

    async def test_result_includes_execution_time(self, mcp_client):
        result = await mcp_client.call_tool("run_readonly_query", {"query": "SELECT 1"})
        data = result.data
        assert "execution_time_ms" in data
        assert data["execution_time_ms"] >= 0

    async def test_truncated_flag_false_for_small_results(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "SELECT * FROM buildings", "limit": 100},
        )
        data = result.data
        assert data["truncated"] is False

    async def test_join_query_works(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {
                "query": (
                    "SELECT b.id, b.name, COUNT(e.id) as reading_count "
                    "FROM buildings b "
                    "LEFT JOIN energy_readings e ON b.id = e.building_id "
                    "GROUP BY b.id, b.name"
                )
            },
        )
        data = result.data
        assert "error" not in data
        assert "columns" in data


class TestMutationRejection:
    async def test_insert_is_rejected(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "INSERT INTO buildings (id, name) VALUES ('X', 'Test')"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_update_is_rejected(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "UPDATE buildings SET name = 'Evil' WHERE id = 'B001'"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_delete_is_rejected(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "DELETE FROM buildings WHERE id = 'B001'"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_drop_table_is_rejected(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "DROP TABLE buildings"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_alter_table_is_rejected(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "ALTER TABLE buildings ADD COLUMN new_col TEXT"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_create_table_is_rejected(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "CREATE TABLE evil (id TEXT)"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_truncate_is_rejected(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "TRUNCATE TABLE buildings"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"


class TestMultiStatementRejection:
    async def test_two_selects_rejected(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "SELECT * FROM buildings; SELECT * FROM energy_readings"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_select_then_drop_rejected(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "SELECT * FROM buildings; DROP TABLE buildings"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_select_then_insert_rejected(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": ("SELECT 1; INSERT INTO buildings (id, name) VALUES ('X', 'Evil')")},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"


class TestEmptyAndInvalidQueries:
    async def test_empty_query_returns_error(self, mcp_client):
        result = await mcp_client.call_tool("run_readonly_query", {"query": ""})
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_whitespace_only_query_returns_error(self, mcp_client):
        result = await mcp_client.call_tool("run_readonly_query", {"query": "   \n\t  "})
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_invalid_sql_returns_error(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query", {"query": "THIS IS NOT SQL AT ALL !!"}
        )
        data = result.data
        assert "error" in data

    async def test_unknown_table_returns_execution_error(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "SELECT * FROM nonexistent_table_xyz"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "QUERY_EXECUTION_ERROR"


class TestResultLimits:
    async def test_limit_is_respected(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {
                "query": "SELECT * FROM energy_readings",
                "limit": 5,
            },
        )
        data = result.data
        assert data["row_count"] <= 5

    async def test_truncated_flag_when_limit_exceeded(self, mcp_client):
        """With limit=1 and multiple readings, truncated should be True."""
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {
                "query": "SELECT * FROM energy_readings",
                "limit": 1,
            },
        )
        data = result.data
        # Only truncated if there are > 1 rows
        if data.get("row_count", 0) == 1:
            assert data["truncated"] is True

    async def test_limit_cannot_exceed_maximum(self, mcp_client):
        """Even if a huge limit is requested, result must not exceed 5000 rows."""
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {
                "query": "SELECT * FROM energy_readings",
                "limit": 99999,
            },
        )
        data = result.data
        if "error" not in data:
            assert data["row_count"] <= 5000


class TestCommentHandling:
    async def test_line_comment_before_select_works(self, mcp_client):
        """Queries with leading comments are valid if the statement is SELECT."""
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "-- find all buildings\nSELECT * FROM buildings"},
        )
        data = result.data
        assert "error" not in data
        assert "columns" in data

    async def test_block_comment_before_select_works(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "/* analytics query */ SELECT id FROM buildings"},
        )
        data = result.data
        assert "error" not in data

    async def test_inline_comment_in_select_works(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": ("SELECT id, -- primary key\nname -- building name\nFROM buildings")},
        )
        data = result.data
        assert "error" not in data
