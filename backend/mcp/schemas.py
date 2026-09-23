"""Pydantic request/response models for MCP tools.

No LangChain, FastMCP, or FastAPI imports permitted in this module.
All models must be JSON-serializable via .model_dump().
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── list_tables ───────────────────────────────────────────────────────────────


class TableInfo(BaseModel):
    """Metadata about a single analytical table."""

    name: str
    description: str
    row_count_estimate: int | None = None


class ListTablesResult(BaseModel):
    """Result from list_tables tool."""

    tables: list[TableInfo]


# ── describe_table ────────────────────────────────────────────────────────────


class ColumnInfo(BaseModel):
    """Metadata about a single column in a table."""

    name: str
    data_type: str
    description: str
    nullable: bool = True


class DescribeTableResult(BaseModel):
    """Result from describe_table tool."""

    table_name: str
    description: str
    columns: list[ColumnInfo]


# ── run_readonly_query ────────────────────────────────────────────────────────


class RunReadonlyQueryResult(BaseModel):
    """Result from run_readonly_query tool."""

    columns: list[str]
    rows: list[list[object]]
    row_count: int
    truncated: bool
    execution_time_ms: float


# ── get_building_summary ──────────────────────────────────────────────────────


class BuildingSummaryResult(BaseModel):
    """Summary statistics for a building over a time range."""

    building_id: str
    building_name: str
    start_date: str
    end_date: str
    reading_type: str
    total_kwh: float
    average_daily_kwh: float
    peak_hourly_kwh: float
    measurement_count: int


# ── get_consumption_trend ─────────────────────────────────────────────────────


class TrendDataPoint(BaseModel):
    """A single time-period data point in a consumption trend."""

    period: str = Field(description="Period label (e.g. '2024-07' for month granularity)")
    total_kwh: float
    average_kwh: float
    data_points: int


class ConsumptionTrendResult(BaseModel):
    """Result from get_consumption_trend tool."""

    building_id: str | None
    granularity: str
    reading_type: str
    data_points: list[TrendDataPoint]


# ── Error ─────────────────────────────────────────────────────────────────────


class ToolError(BaseModel):
    """Structured error returned by any tool on failure."""

    error: str
    error_code: str
