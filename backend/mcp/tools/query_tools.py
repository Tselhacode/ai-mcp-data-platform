"""MCP query tool: run_readonly_query.

Executes a user/LLM-provided SQL SELECT query against the database.
Uses sqlglot for statement-type validation before execution.

Security approach:
- sqlglot parses SQL and confirms the statement type is SELECT
- Multiple statements (semicolons) are rejected
- Results are truncated to a configurable limit (default 1000, max 5000)
- Queries are logged at DEBUG level only, never at INFO
- No raw user input is passed to SQLAlchemy text() without parameterization

Limitations:
- sqlglot validates statement type but does not prevent all information
  disclosure attacks (e.g. timing side-channels via complex subqueries)
- The READ ONLY constraint is enforced by statement type, not DB-level

No LangChain imports permitted.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import sqlglot
import sqlglot.expressions as exp
from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mcp.dependencies import get_energy_service
from mcp.schemas import RunReadonlyQueryResult, ToolError

logger = logging.getLogger(__name__)

_DEFAULT_LIMIT = 1000
_MAX_LIMIT = 5000


def _validate_sql(query: str) -> tuple[bool, str]:
    """Validate a SQL query is a single SELECT statement.

    Uses sqlglot to parse the query and check:
    - Exactly one statement
    - Statement type is SELECT
    - No DDL or DML operations

    Args:
        query: SQL query string from the user/LLM.

    Returns:
        (is_valid, error_message) — error_message is empty string when valid.
    """
    stripped = query.strip()
    if not stripped:
        return False, "Query must not be empty"

    try:
        statements = sqlglot.parse(stripped, dialect="sqlite")
    except Exception as e:
        return False, f"SQL parse error: {e}"

    if not statements:
        return False, "Query produced no parseable statements"

    if len(statements) > 1:
        return False, (
            "Multiple SQL statements are not allowed. Submit one SELECT statement at a time."
        )

    stmt = statements[0]
    if stmt is None:
        return False, "Empty statement"

    if not isinstance(stmt, exp.Select):
        stmt_type = type(stmt).__name__
        return False, (
            f"Only SELECT statements are allowed. "
            f"Received: {stmt_type}. "
            "INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, "
            "GRANT, REVOKE, EXECUTE and similar statements are rejected."
        )

    return True, ""


def register_query_tools(
    mcp: FastMCP,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Register query tools on the given FastMCP server instance.

    Args:
        mcp: The FastMCP server to register tools on.
        session_factory: Async session factory for database access.
    """

    @mcp.tool()
    async def run_readonly_query(
        query: str,
        params: dict[str, Any] | None = None,
        limit: int = _DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Execute a read-only SQL SELECT query against the energy database.

        Use this tool for custom analytics that the other tools do not cover.
        Only SELECT statements are accepted — any mutation attempt is rejected.

        Available tables: buildings, energy_readings (use list_tables and
        describe_table to understand the schema first).

        Args:
            query: A SQL SELECT statement. Use :param_name for bind parameters.
            params: Optional dict of bind parameter values, e.g. {"building_id": "B007"}.
            limit: Maximum rows to return (default 1000, maximum 5000).

        Returns a dict with:
            - columns: list of column names
            - rows: list of row arrays
            - row_count: number of rows returned
            - truncated: true if results were limited
            - execution_time_ms: query execution time in milliseconds

        Returns an error dict if the query is invalid or fails.

        Example:
            query = "SELECT building_id, SUM(kwh) FROM energy_readings
                     WHERE reading_type = :rtype GROUP BY building_id"
            params = {"rtype": "electricity"}
        """
        start_time = time.monotonic()
        effective_limit = min(max(1, limit), _MAX_LIMIT)

        # Log query at DEBUG only — it may contain sensitive filter values
        logger.debug(
            "run_readonly_query received",
            extra={"query_preview": query[:200], "limit": effective_limit},
        )

        # ── SQL validation ────────────────────────────────────────────────────
        is_valid, error_msg = _validate_sql(query)
        if not is_valid:
            logger.warning(
                "run_readonly_query rejected invalid SQL",
                extra={"reason": error_msg, "query_preview": query[:200]},
            )
            return ToolError(
                error=error_msg,
                error_code="INVALID_SQL",
            ).model_dump()

        # ── Execute query via service → repository → SQLAlchemy ──────────────
        safe_params = params or {}
        try:
            async with get_energy_service(session_factory) as svc:
                # Fetch one extra row to detect truncation without a second query
                columns, raw_rows = await svc.execute_readonly_query(
                    query, safe_params, effective_limit + 1
                )

                truncated = len(raw_rows) > effective_limit
                rows_to_return = raw_rows[:effective_limit]

                # Convert row tuples to plain lists for JSON serialization
                serializable_rows: list[list[object]] = [
                    [_serialize_value(v) for v in row] for row in rows_to_return
                ]

        except Exception as exc:
            logger.error(
                "run_readonly_query database error",
                extra={"error": str(exc)},
                exc_info=True,
            )
            return ToolError(
                error="Query execution failed. Check query syntax and table/column names.",
                error_code="QUERY_EXECUTION_ERROR",
            ).model_dump()

        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "mcp_tool_call",
            extra={
                "tool": "run_readonly_query",
                "row_count": len(serializable_rows),
                "truncated": truncated,
                "duration_ms": round(elapsed_ms, 1),
                "success": True,
            },
        )

        return RunReadonlyQueryResult(
            columns=columns,
            rows=serializable_rows,
            row_count=len(serializable_rows),
            truncated=truncated,
            execution_time_ms=round(elapsed_ms, 1),
        ).model_dump()


def _serialize_value(value: Any) -> Any:
    """Convert a database value to a JSON-serializable type.

    Args:
        value: Raw value from database row.

    Returns:
        JSON-serializable equivalent.
    """
    if value is None:
        return None
    if isinstance(value, (int, float, str, bool)):
        return value
    # datetime, date, time → ISO string
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
