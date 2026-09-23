"""MCP analytics tools: get_building_summary and get_consumption_trend.

These tools provide high-level energy analytics by delegating to EnergyService.
They do NOT contain business logic — all computation is in the service layer.

No LangChain imports permitted.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mcp.dependencies import get_energy_service
from mcp.schemas import (
    BuildingSummaryResult,
    ConsumptionTrendResult,
    ToolError,
    TrendDataPoint,
)

logger = logging.getLogger(__name__)

_VALID_GRANULARITIES = frozenset({"day", "week", "month"})
_VALID_READING_TYPES = frozenset({"electricity", "gas", "solar"})


def _parse_date(date_str: str, field_name: str) -> datetime | None:
    """Parse a YYYY-MM-DD date string.

    Args:
        date_str: Date string in YYYY-MM-DD format.
        field_name: Field name for error messages.

    Returns:
        datetime at midnight UTC, or None on parse failure.
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


def _period_key(ts: datetime, granularity: str) -> str:
    """Compute the period label for a timestamp.

    Args:
        ts: The timestamp.
        granularity: One of "day", "week", "month".

    Returns:
        Period label string (e.g. "2024-07" for month, "2024-07-01" for day).
    """
    if granularity == "month":
        return ts.strftime("%Y-%m")
    elif granularity == "week":
        # ISO week start (Monday)
        week_start = ts - timedelta(days=ts.weekday())
        return week_start.strftime("%Y-%m-%d")
    else:  # day
        return ts.strftime("%Y-%m-%d")


def register_analytics_tools(
    mcp: FastMCP,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Register analytics tools on the given FastMCP server instance.

    Args:
        mcp: The FastMCP server to register tools on.
        session_factory: Async session factory for database access.
    """

    @mcp.tool()
    async def get_building_summary(
        building_id: str,
        start_date: str,
        end_date: str,
        reading_type: str = "electricity",
    ) -> dict[str, Any]:
        """Get an energy consumption summary for a specific building over a date range.

        Computes total kWh, average daily kWh, peak hourly kWh, and reading count
        for the requested period. Use this for a quick snapshot of a building's
        energy usage.

        Args:
            building_id: The building ID (e.g. 'B007'). Use list_tables or
                         run_readonly_query to discover valid building IDs.
            start_date: Start date in YYYY-MM-DD format (inclusive).
            end_date: End date in YYYY-MM-DD format (inclusive).
            reading_type: Energy type to query — 'electricity', 'gas', or 'solar'.
                          Defaults to 'electricity'.

        Returns a dict with:
            - building_id, building_name
            - start_date, end_date, reading_type
            - total_kwh, average_daily_kwh, peak_hourly_kwh, measurement_count

        Returns an error dict if building is not found or dates are invalid.
        """
        start_time = time.monotonic()
        logger.debug(
            "get_building_summary called",
            extra={
                "building_id": building_id,
                "start_date": start_date,
                "end_date": end_date,
                "reading_type": reading_type,
            },
        )

        # ── Input validation ──────────────────────────────────────────────────
        if reading_type not in _VALID_READING_TYPES:
            return ToolError(
                error=f"Invalid reading_type '{reading_type}'. "
                f"Must be one of: {sorted(_VALID_READING_TYPES)}",
                error_code="INVALID_READING_TYPE",
            ).model_dump()

        start_dt = _parse_date(start_date, "start_date")
        if start_dt is None:
            return ToolError(
                error=f"Invalid start_date '{start_date}'. Use YYYY-MM-DD format.",
                error_code="INVALID_DATE",
            ).model_dump()

        end_dt = _parse_date(end_date, "end_date")
        if end_dt is None:
            return ToolError(
                error=f"Invalid end_date '{end_date}'. Use YYYY-MM-DD format.",
                error_code="INVALID_DATE",
            ).model_dump()

        # Make end_dt exclusive (include the whole last day)
        end_dt_exclusive = end_dt + timedelta(days=1)

        if start_dt >= end_dt_exclusive:
            return ToolError(
                error="start_date must be before end_date.",
                error_code="INVALID_DATE_RANGE",
            ).model_dump()

        # ── Service call ──────────────────────────────────────────────────────
        try:
            async with get_energy_service(session_factory) as svc:
                building = await svc.get_building(building_id)
                if building is None:
                    return ToolError(
                        error=f"Building '{building_id}' not found.",
                        error_code="BUILDING_NOT_FOUND",
                    ).model_dump()

                readings = await svc.get_consumption(
                    building_id=building_id,
                    start=start_dt,
                    end=end_dt_exclusive,
                    reading_type=reading_type,
                )
        except Exception as exc:
            logger.error(
                "get_building_summary error",
                extra={"building_id": building_id, "error": str(exc)},
                exc_info=True,
            )
            return ToolError(
                error="An error occurred retrieving building data.",
                error_code="SERVICE_ERROR",
            ).model_dump()

        # ── Compute summary stats ─────────────────────────────────────────────
        measurement_count = len(readings)
        total_kwh = sum(r.kwh for r in readings) if readings else 0.0
        peak_hourly_kwh = max((r.kwh for r in readings), default=0.0)

        # Average daily kWh: total / number of calendar days in range
        days_in_range = (end_dt_exclusive - start_dt).days
        average_daily_kwh = total_kwh / days_in_range if days_in_range > 0 else 0.0

        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "mcp_tool_call",
            extra={
                "tool": "get_building_summary",
                "building_id": building_id,
                "measurement_count": measurement_count,
                "duration_ms": round(elapsed_ms, 1),
                "success": True,
            },
        )

        return BuildingSummaryResult(
            building_id=building_id,
            building_name=building.name,
            start_date=start_date,
            end_date=end_date,
            reading_type=reading_type,
            total_kwh=round(total_kwh, 3),
            average_daily_kwh=round(average_daily_kwh, 3),
            peak_hourly_kwh=round(peak_hourly_kwh, 3),
            measurement_count=measurement_count,
        ).model_dump()

    @mcp.tool()
    async def get_consumption_trend(
        start_date: str,
        end_date: str,
        granularity: str = "month",
        building_id: str | None = None,
        reading_type: str = "electricity",
    ) -> dict[str, Any]:
        """Get energy consumption trend aggregated by time period.

        Returns consumption data grouped by day, week, or month.
        Use this to identify seasonal patterns, compare periods, or
        visualise how energy use changes over time.

        Args:
            start_date: Start date in YYYY-MM-DD format (inclusive).
            end_date: End date in YYYY-MM-DD format (inclusive).
            granularity: Aggregation period — 'day', 'week', or 'month'.
                         Defaults to 'month'.
            building_id: Optional building ID filter. Omit for all buildings.
            reading_type: Energy type — 'electricity', 'gas', or 'solar'.
                          Defaults to 'electricity'.

        Returns a dict with:
            - building_id (null if all buildings)
            - granularity, reading_type
            - data_points: list of {period, total_kwh, average_kwh, data_points}

        Returns an error dict if dates are invalid or granularity is unknown.
        """
        start_time = time.monotonic()
        logger.debug(
            "get_consumption_trend called",
            extra={
                "building_id": building_id,
                "start_date": start_date,
                "end_date": end_date,
                "granularity": granularity,
                "reading_type": reading_type,
            },
        )

        # ── Input validation ──────────────────────────────────────────────────
        if granularity not in _VALID_GRANULARITIES:
            return ToolError(
                error=f"Invalid granularity '{granularity}'. "
                f"Must be one of: {sorted(_VALID_GRANULARITIES)}",
                error_code="INVALID_GRANULARITY",
            ).model_dump()

        if reading_type not in _VALID_READING_TYPES:
            return ToolError(
                error=f"Invalid reading_type '{reading_type}'. "
                f"Must be one of: {sorted(_VALID_READING_TYPES)}",
                error_code="INVALID_READING_TYPE",
            ).model_dump()

        start_dt = _parse_date(start_date, "start_date")
        if start_dt is None:
            return ToolError(
                error=f"Invalid start_date '{start_date}'. Use YYYY-MM-DD format.",
                error_code="INVALID_DATE",
            ).model_dump()

        end_dt = _parse_date(end_date, "end_date")
        if end_dt is None:
            return ToolError(
                error=f"Invalid end_date '{end_date}'. Use YYYY-MM-DD format.",
                error_code="INVALID_DATE",
            ).model_dump()

        end_dt_exclusive = end_dt + timedelta(days=1)

        if start_dt >= end_dt_exclusive:
            return ToolError(
                error="start_date must be before end_date.",
                error_code="INVALID_DATE_RANGE",
            ).model_dump()

        # ── Service call ──────────────────────────────────────────────────────
        try:
            async with get_energy_service(session_factory) as svc:
                if building_id is not None:
                    # Validate building exists
                    building = await svc.get_building(building_id)
                    if building is None:
                        return ToolError(
                            error=f"Building '{building_id}' not found.",
                            error_code="BUILDING_NOT_FOUND",
                        ).model_dump()

                    readings = await svc.get_consumption(
                        building_id=building_id,
                        start=start_dt,
                        end=end_dt_exclusive,
                        reading_type=reading_type,
                    )
                else:
                    # Fetch all buildings, then all readings
                    buildings = await svc.get_buildings()
                    readings = []
                    for bldg in buildings:
                        bldg_readings = await svc.get_consumption(
                            building_id=bldg.id,
                            start=start_dt,
                            end=end_dt_exclusive,
                            reading_type=reading_type,
                        )
                        readings.extend(bldg_readings)

        except Exception as exc:
            logger.error(
                "get_consumption_trend error",
                extra={"building_id": building_id, "error": str(exc)},
                exc_info=True,
            )
            return ToolError(
                error="An error occurred retrieving consumption data.",
                error_code="SERVICE_ERROR",
            ).model_dump()

        # ── Aggregate by period ───────────────────────────────────────────────
        period_kwh: dict[str, list[float]] = defaultdict(list)
        for reading in readings:
            key = _period_key(reading.timestamp, granularity)
            period_kwh[key].append(reading.kwh)

        data_points: list[TrendDataPoint] = []
        for period in sorted(period_kwh.keys()):
            kwh_values = period_kwh[period]
            total = sum(kwh_values)
            avg = total / len(kwh_values) if kwh_values else 0.0
            data_points.append(
                TrendDataPoint(
                    period=period,
                    total_kwh=round(total, 3),
                    average_kwh=round(avg, 3),
                    data_points=len(kwh_values),
                )
            )

        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "mcp_tool_call",
            extra={
                "tool": "get_consumption_trend",
                "building_id": building_id,
                "periods": len(data_points),
                "duration_ms": round(elapsed_ms, 1),
                "success": True,
            },
        )

        return ConsumptionTrendResult(
            building_id=building_id,
            granularity=granularity,
            reading_type=reading_type,
            data_points=data_points,
        ).model_dump()
