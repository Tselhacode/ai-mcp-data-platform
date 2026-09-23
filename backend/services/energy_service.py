"""Energy analytics service.

Pure Python service. No LangChain, no FastMCP, no FastAPI imports permitted.
Called by MCP tool handlers and API routes.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from data.models import Building, EnergyReading
from data.repositories.protocols import (
    AnomalyRecord,
    EnergyRepositoryProtocol,
    MonthlySummary,
)

logger = logging.getLogger(__name__)


class EnergyService:
    """Business logic for energy analytics.

    Accepts a repository via constructor injection so it can be tested
    with a fake repository without touching the database.
    """

    def __init__(self, repo: EnergyRepositoryProtocol) -> None:
        self._repo = repo

    async def get_buildings(self) -> list[Building]:
        """Return all buildings in the dataset, ordered by ID.

        Returns:
            List of Building objects.
        """
        logger.debug("get_buildings")
        return await self._repo.get_buildings()

    async def get_building(self, building_id: str) -> Building | None:
        """Return a single building by ID, or None if not found.

        Args:
            building_id: Building ID to look up (e.g. "B007").

        Returns:
            Building if found, else None.
        """
        logger.debug("get_building", extra={"building_id": building_id})
        return await self._repo.get_building(building_id)

    async def get_consumption(
        self,
        building_id: str,
        start: datetime,
        end: datetime,
        reading_type: str = "electricity",
    ) -> list[EnergyReading]:
        """Return energy readings for a building within a time range.

        Args:
            building_id: Building ID to query.
            start: Inclusive start datetime.
            end: Exclusive end datetime.
            reading_type: Reading type filter (default: "electricity").

        Returns:
            List of EnergyReading objects ordered by timestamp.
        """
        logger.debug(
            "get_consumption",
            extra={
                "building_id": building_id,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "reading_type": reading_type,
            },
        )
        return await self._repo.get_consumption(
            building_id=building_id,
            start=start,
            end=end,
            reading_type=reading_type,
        )

    async def get_monthly_summary(
        self,
        building_id: str | None,
        year: int,
        month: int,
    ) -> list[MonthlySummary]:
        """Return monthly energy consumption summary.

        Args:
            building_id: Building to query, or None for all buildings.
            year: Calendar year.
            month: Calendar month (1-12).

        Returns:
            List of MonthlySummary objects.
        """
        logger.debug(
            "get_monthly_summary",
            extra={"building_id": building_id, "year": year, "month": month},
        )
        return await self._repo.get_monthly_summary(
            building_id=building_id,
            year=year,
            month=month,
        )

    async def find_anomalies(
        self,
        building_id: str | None,
        threshold_stddev: float = 2.0,
    ) -> list[AnomalyRecord]:
        """Detect anomalous energy readings.

        Args:
            building_id: Building to check, or None for all buildings.
            threshold_stddev: Anomaly detection sensitivity threshold.

        Returns:
            List of AnomalyRecord objects for detected anomalies.
        """
        logger.debug(
            "find_anomalies",
            extra={"building_id": building_id, "threshold_stddev": threshold_stddev},
        )
        return await self._repo.find_anomalies(
            building_id=building_id,
            threshold_stddev=threshold_stddev,
        )

    async def execute_readonly_query(
        self,
        sql: str,
        params: dict[str, Any],
        fetch_limit: int,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Execute a pre-validated read-only SQL SELECT statement.

        The caller is responsible for validating that `sql` is a single
        SELECT statement before calling this method.

        Args:
            sql: Pre-validated SQL SELECT statement.
            params: Bind parameter values.
            fetch_limit: Maximum rows to fetch.

        Returns:
            Tuple of (column_names, rows).
        """
        return await self._repo.execute_readonly_query(sql, params, fetch_limit)
