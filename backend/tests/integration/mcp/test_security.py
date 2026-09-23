"""Security-focused MCP integration tests.

Tests SQL injection attempts, mutation via comments, case variations,
and other bypass attempts on the run_readonly_query tool.
"""

from __future__ import annotations


class TestSQLInjectionPrevention:
    async def test_line_comment_before_drop(self, mcp_client):
        """-- comment cannot disguise a DROP statement."""
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "-- safe\nDROP TABLE buildings"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_block_comment_before_delete(self, mcp_client):
        """Block comment cannot disguise a DELETE statement."""
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "/* safe query */ DELETE FROM buildings"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_uppercase_insert_rejected(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {
                "query": "INSERT INTO buildings VALUES ('X', 'evil', 'addr', 1, 1000.0, '2024-01-01')"
            },
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_lowercase_insert_rejected(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {
                "query": "insert into buildings values ('X', 'evil', 'addr', 1, 1000.0, '2024-01-01')"
            },
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_mixed_case_delete_rejected(self, mcp_client):
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "DeLeTe FrOm buildings"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_embedded_newline_mutation_rejected(self, mcp_client):
        """Newlines in query cannot be used to hide a second statement."""
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "SELECT 1\n;\nDELETE FROM buildings"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_union_statement_type_rejected(self, mcp_client):
        """sqlglot classifies UNION as a Union node, not a Select.
        The validator rejects it as it is not a pure SELECT statement.
        """
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {
                "query": (
                    "SELECT id FROM buildings UNION SELECT id FROM buildings WHERE id = :bid"
                ),
                "params": {"bid": "B001"},
            },
        )
        data = result.data
        # sqlglot parses UNION as Union (not Select), so it is rejected
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_semicolon_after_select_rejected(self, mcp_client):
        """SELECT followed by semicolon and another statement is rejected."""
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "SELECT * FROM buildings; DELETE FROM buildings"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"

    async def test_drop_with_comment_suffix_rejected(self, mcp_client):
        """DROP TABLE with trailing comment is still a DROP, not a SELECT."""
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {"query": "DROP TABLE buildings -- not a delete"},
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_SQL"


class TestParameterization:
    async def test_string_param_does_not_inject(self, mcp_client):
        """A building_id param containing SQL injection is treated as a literal value."""
        result = await mcp_client.call_tool(
            "run_readonly_query",
            {
                "query": "SELECT * FROM buildings WHERE id = :bid",
                "params": {"bid": "'; DROP TABLE buildings; --"},
            },
        )
        # Should execute the SELECT, find no rows matching that injection string
        data = result.data
        if "error" not in data:
            assert data["row_count"] == 0  # no building with that ID exists
