"""MCP schema tools: list_tables and describe_table.

These tools expose analytical table metadata to the LLM agent.
They are read-only and return hardcoded metadata — no database queries.

No LangChain imports permitted.
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP

from mcp.schemas import ColumnInfo, DescribeTableResult, ListTablesResult, TableInfo, ToolError

logger = logging.getLogger(__name__)

# ── Allowed table names (allowlist) ──────────────────────────────────────────
# Only analytically relevant tables are exposed. Internal tables (sessions,
# evaluation runs, etc.) are not exposed to the LLM.

_ALLOWED_TABLES = frozenset({"buildings", "energy_readings"})

# ── Static table metadata ─────────────────────────────────────────────────────

_TABLE_METADATA: dict[str, DescribeTableResult] = {
    "buildings": DescribeTableResult(
        table_name="buildings",
        description=(
            "Metadata about monitored buildings. "
            "Each row represents one building with its physical attributes."
        ),
        columns=[
            ColumnInfo(
                name="id",
                data_type="TEXT",
                description="Building identifier (e.g. 'B001'). Primary key.",
                nullable=False,
            ),
            ColumnInfo(
                name="name",
                data_type="TEXT",
                description="Human-readable building name.",
                nullable=False,
            ),
            ColumnInfo(
                name="address",
                data_type="TEXT",
                description="Physical street address of the building.",
                nullable=False,
            ),
            ColumnInfo(
                name="floor_count",
                data_type="INTEGER",
                description="Number of floors in the building.",
                nullable=False,
            ),
            ColumnInfo(
                name="area_sqft",
                data_type="REAL",
                description="Total floor area in square feet.",
                nullable=False,
            ),
            ColumnInfo(
                name="created_at",
                data_type="DATETIME",
                description="Record creation timestamp (UTC).",
                nullable=False,
            ),
        ],
    ),
    "energy_readings": DescribeTableResult(
        table_name="energy_readings",
        description=(
            "Time-series energy consumption readings. "
            "Each row is one hourly reading for a building. "
            "Primary access pattern: filter by building_id + timestamp range."
        ),
        columns=[
            ColumnInfo(
                name="id",
                data_type="INTEGER",
                description="Auto-increment primary key.",
                nullable=False,
            ),
            ColumnInfo(
                name="building_id",
                data_type="TEXT",
                description="Foreign key to buildings.id.",
                nullable=False,
            ),
            ColumnInfo(
                name="timestamp",
                data_type="DATETIME",
                description="Reading timestamp (UTC). Readings are hourly.",
                nullable=False,
            ),
            ColumnInfo(
                name="kwh",
                data_type="REAL",
                description="Kilowatt-hours consumed in this period.",
                nullable=False,
            ),
            ColumnInfo(
                name="reading_type",
                data_type="TEXT",
                description="Energy type: 'electricity', 'gas', or 'solar'.",
                nullable=False,
            ),
            ColumnInfo(
                name="meter_id",
                data_type="TEXT",
                description="Source meter identifier.",
                nullable=False,
            ),
            ColumnInfo(
                name="created_at",
                data_type="DATETIME",
                description="Record creation timestamp (UTC).",
                nullable=False,
            ),
        ],
    ),
}


def register_schema_tools(mcp: FastMCP) -> None:
    """Register schema tools on the given FastMCP server instance.

    Args:
        mcp: The FastMCP server to register tools on.
    """

    @mcp.tool()
    def list_tables() -> dict[str, Any]:
        """List the analytical tables available for querying.

        Use this tool to discover what data is available before constructing
        SQL queries or calling analytics tools. Returns table names and
        descriptions. Only analytically relevant tables are exposed.

        Returns a dict with key 'tables' containing a list of table objects,
        each with 'name', 'description', and 'row_count_estimate'.
        """
        logger.info("mcp_tool_call", extra={"tool": "list_tables"})
        result = ListTablesResult(
            tables=[
                TableInfo(
                    name="buildings",
                    description="Metadata about monitored buildings (id, name, address, floor_count, area_sqft).",
                    row_count_estimate=None,
                ),
                TableInfo(
                    name="energy_readings",
                    description=(
                        "Hourly energy consumption readings "
                        "(building_id, timestamp, kwh, reading_type, meter_id). "
                        "Primary data for analytics."
                    ),
                    row_count_estimate=None,
                ),
            ]
        )
        return result.model_dump()

    @mcp.tool()
    def describe_table(table_name: str) -> dict[str, Any]:
        """Describe the columns, data types, and purpose of a table.

        Use this before writing SQL queries to understand what columns are
        available. Only the analytically relevant tables (buildings,
        energy_readings) can be described.

        Args:
            table_name: Name of the table to describe. Must be one of:
                        'buildings', 'energy_readings'.

        Returns a dict with 'table_name', 'description', and 'columns'
        (each with 'name', 'data_type', 'description', 'nullable').
        Returns an error dict if the table name is not in the allowed list.
        """
        logger.info("mcp_tool_call", extra={"tool": "describe_table", "table_name": table_name})

        # Allowlist validation — reject anything not explicitly permitted.
        if table_name not in _ALLOWED_TABLES:
            logger.warning(
                "describe_table rejected unknown table",
                extra={"table_name": table_name},
            )
            return ToolError(
                error=f"Table '{table_name}' is not available. "
                f"Allowed tables: {sorted(_ALLOWED_TABLES)}",
                error_code="TABLE_NOT_FOUND",
            ).model_dump()

        metadata = _TABLE_METADATA[table_name]
        return metadata.model_dump()
