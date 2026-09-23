"""Energy analytics service — Phase 1A scaffold.

Pure Python service. No LangChain, no FastMCP, no FastAPI imports permitted.
Called by MCP tool handlers and API routes.

This module is a scaffold. Methods will be fully implemented in later phases
when MCP tools and the API layer are built.
"""

import logging

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
