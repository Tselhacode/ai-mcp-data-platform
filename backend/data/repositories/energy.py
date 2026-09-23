"""SQLAlchemy implementation of EnergyRepositoryProtocol.

Implements all energy data access methods using async SQLAlchemy.
All queries are parameterized — no raw user input is ever passed to text().

No LangChain, FastMCP, or FastAPI imports are permitted in this module.
"""

import logging
import math
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import Building, EnergyReading
from data.repositories.protocols import AnomalyRecord, MonthlySummary

logger = logging.getLogger(__name__)


class SQLAlchemyEnergyRepository:
    """Async SQLAlchemy implementation of the energy data repository.

    All methods accept and return domain objects (Building, EnergyReading,
    MonthlySummary, AnomalyRecord). No SQLAlchemy types leak into callers.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_buildings(self) -> list[Building]:
        """Return all buildings ordered by ID."""
        result = await self._session.execute(select(Building).order_by(Building.id))
        return list(result.scalars().all())

    async def get_building(self, building_id: str) -> Building | None:
        """Return a single building by ID, or None."""
        result = await self._session.execute(select(Building).where(Building.id == building_id))
        return result.scalar_one_or_none()

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
            start: Inclusive start datetime (UTC).
            end: Exclusive end datetime (UTC).
            reading_type: Filter by reading type (default: "electricity").

        Returns:
            Readings ordered by timestamp ascending.
        """
        result = await self._session.execute(
            select(EnergyReading)
            .where(
                EnergyReading.building_id == building_id,
                EnergyReading.timestamp >= start,
                EnergyReading.timestamp < end,
                EnergyReading.reading_type == reading_type,
            )
            .order_by(EnergyReading.timestamp)
        )
        return list(result.scalars().all())

    async def get_monthly_summary(
        self,
        building_id: str | None,
        year: int,
        month: int,
    ) -> list[MonthlySummary]:
        """Return aggregated consumption per building for a calendar month.

        Args:
            building_id: If None, return summaries for all buildings.
            year: Calendar year.
            month: Calendar month (1-12).

        Returns:
            MonthlySummary objects sorted by building_id.
        """
        # Build the date range for the month
        start = datetime(year, month, 1, tzinfo=None)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=None)
        else:
            end = datetime(year, month + 1, 1, tzinfo=None)

        stmt = (
            select(
                EnergyReading.building_id,
                EnergyReading.reading_type,
                func.sum(EnergyReading.kwh).label("total_kwh"),
                func.count(EnergyReading.id).label("reading_count"),
            )
            .where(
                EnergyReading.timestamp >= start,
                EnergyReading.timestamp < end,
            )
            .group_by(EnergyReading.building_id, EnergyReading.reading_type)
            .order_by(EnergyReading.building_id, EnergyReading.reading_type)
        )

        if building_id is not None:
            stmt = stmt.where(EnergyReading.building_id == building_id)

        result = await self._session.execute(stmt)
        rows = result.all()

        return [
            MonthlySummary(
                building_id=row.building_id,
                year=year,
                month=month,
                total_kwh=float(row.total_kwh),
                reading_count=int(row.reading_count),
                reading_type=row.reading_type,
            )
            for row in rows
        ]

    async def find_anomalies(
        self,
        building_id: str | None,
        threshold_stddev: float = 2.0,
    ) -> list[AnomalyRecord]:
        """Detect anomalous energy readings by statistical deviation.

        Computes per-building mean and standard deviation for electricity
        readings, then returns readings that deviate more than threshold_stddev
        standard deviations from the mean.

        Args:
            building_id: If None, check all buildings.
            threshold_stddev: Number of stddevs to define anomaly threshold.

        Returns:
            AnomalyRecord objects for anomalous readings.
        """
        # Fetch all electricity readings (or just for one building)
        stmt = select(EnergyReading).where(EnergyReading.reading_type == "electricity")
        if building_id is not None:
            stmt = stmt.where(EnergyReading.building_id == building_id)

        result = await self._session.execute(stmt.order_by(EnergyReading.building_id))
        readings = list(result.scalars().all())

        if not readings:
            return []

        # Group readings by building_id for statistical analysis
        by_building: dict[str, list[EnergyReading]] = {}
        for r in readings:
            by_building.setdefault(r.building_id, []).append(r)

        anomalies: list[AnomalyRecord] = []

        for bid, breadings in by_building.items():
            kwh_values = [r.kwh for r in breadings]
            n = len(kwh_values)
            if n < 2:
                continue

            mean = sum(kwh_values) / n
            variance = sum((x - mean) ** 2 for x in kwh_values) / (n - 1)
            stddev = math.sqrt(variance)

            if stddev == 0.0:
                continue

            for reading in breadings:
                deviation = abs(reading.kwh - mean) / stddev
                if deviation >= threshold_stddev:
                    anomalies.append(
                        AnomalyRecord(
                            building_id=bid,
                            timestamp=reading.timestamp,
                            kwh=reading.kwh,
                            mean_kwh=mean,
                            stddev_kwh=stddev,
                            deviation=deviation,
                            reading_type=reading.reading_type,
                            meter_id=reading.meter_id,
                        )
                    )

        # Sort by deviation descending (most anomalous first)
        anomalies.sort(key=lambda a: a.deviation, reverse=True)
        return anomalies

    async def execute_readonly_query(
        self,
        sql: str,
        params: dict[str, Any],
        fetch_limit: int,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Execute a pre-validated read-only SQL SELECT statement.

        Args:
            sql: Pre-validated SQL SELECT statement.
            params: Bind parameter values.
            fetch_limit: Maximum rows to fetch.

        Returns:
            Tuple of (column_names, rows) where each row is a plain Python tuple.
        """
        result = await self._session.execute(text(sql), params)
        columns = list(result.keys())
        rows = result.fetchmany(fetch_limit)
        return columns, [tuple(row) for row in rows]
