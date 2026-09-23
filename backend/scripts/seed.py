"""Deterministic seed script for the AI MCP Data Platform.

Generates synthetic energy data for local development and evaluation testing.

Data characteristics:
  - 20 buildings (B001-B020) with realistic names
  - 2 years of hourly electricity readings (2023-01-01 to 2024-12-31)
    for all 20 buildings (~350,400 electricity rows)
  - Gas readings for buildings B001-B010 (10 buildings)
  - Solar readings for buildings B001-B005 (5 buildings)
  - Building B007 is the highest electricity consumer
  - Building B003 has a planted anomaly in November 2024
  - Building B007 shows the largest July→August 2024 increase (TASK-009)
  - Fixed random seed (42) — results are identical across environments

Usage:
    cd backend
    uv run python scripts/seed.py
    uv run python scripts/seed.py --database-url sqlite+aiosqlite:///./data/db.sqlite
"""

import argparse
import asyncio
import logging
import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent dir to path so imports work when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncEngine

from data.database import get_engine, get_session_factory
from data.models import Base, Building, EnergyReading

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RANDOM_SEED = 42
BATCH_SIZE = 1000

# Building definitions — 20 buildings with realistic names
BUILDINGS = [
    ("B001", "City Hall Annex", "100 Main Street", 5, 45000.0),
    ("B002", "Riverside Office Tower", "200 River Boulevard", 12, 120000.0),
    ("B003", "Greenwood Community Center", "301 Park Avenue", 2, 18000.0),
    ("B004", "Harbor View Logistics Hub", "400 Dock Road", 3, 75000.0),
    ("B005", "Sunridge Research Center", "500 Innovation Drive", 6, 95000.0),
    ("B006", "Lakeside Library", "601 Library Lane", 3, 30000.0),
    ("B007", "Central Data Center", "700 Server Farm Blvd", 4, 110000.0),
    ("B008", "Northgate Shopping Center", "800 Commerce Street", 2, 200000.0),
    ("B009", "Westfield Medical Clinic", "900 Health Avenue", 4, 55000.0),
    ("B010", "Eastside Education Campus", "1001 Scholar Way", 5, 80000.0),
    ("B011", "Millbrook Fitness Center", "1100 Workout Lane", 2, 22000.0),
    ("B012", "Bayside Hotel", "1200 Waterfront Road", 10, 90000.0),
    ("B013", "Uptown Law Offices", "1300 Justice Street", 8, 50000.0),
    ("B014", "Southgate Manufacturing Plant", "1400 Industrial Pkwy", 1, 180000.0),
    ("B015", "Cedar Ridge Apartments", "1500 Residential Blvd", 7, 140000.0),
    ("B016", "Clearwater Aquatic Center", "1600 Pool Drive", 2, 35000.0),
    ("B017", "Pinnacle Financial Center", "1700 Wall Street North", 15, 160000.0),
    ("B018", "Harmony Arts Auditorium", "1800 Stage Road", 3, 42000.0),
    ("B019", "Timberline Convention Center", "1900 Event Blvd", 4, 125000.0),
    ("B020", "Hillcrest Tech Campus", "2000 Silicon Way", 8, 105000.0),
]

# Base electricity load per building (kWh/hour) — B007 is highest consumer
# Multipliers relative to a base of 10 kWh/hour
BASE_ELECTRICITY_KWH = {
    "B001": 8.5,
    "B002": 18.0,
    "B003": 4.0,
    "B004": 14.0,
    "B005": 16.0,
    "B006": 5.5,
    "B007": 32.0,  # Data center — highest consumer
    "B008": 25.0,
    "B009": 12.0,
    "B010": 14.5,
    "B011": 6.0,
    "B012": 20.0,
    "B013": 9.0,
    "B014": 22.0,
    "B015": 19.0,
    "B016": 8.0,
    "B017": 28.0,
    "B018": 7.0,
    "B019": 21.0,
    "B020": 17.5,
}

# Buildings with gas meters
GAS_BUILDINGS = {f"B{i:03d}" for i in range(1, 11)}

# Buildings with solar panels
SOLAR_BUILDINGS = {f"B{i:03d}" for i in range(1, 6)}

# B003 anomaly: planted spike in November 2024
ANOMALY_BUILDING = "B003"
ANOMALY_TIMESTAMPS = [
    datetime(2024, 11, 14, 14, 0),  # 3x normal
    datetime(2024, 11, 14, 15, 0),  # 3x normal
    datetime(2024, 11, 14, 16, 0),  # 2.5x normal
]
ANOMALY_MULTIPLIER = 3.0

# B007 July→August 2024 boost (TASK-009): large increase in August
B007_AUGUST_MULTIPLIER = 1.55  # ~55% increase over July


def seasonal_factor(dt: datetime) -> float:
    """Return a seasonal load multiplier (higher in summer/winter for HVAC).

    Uses a double-peak sinusoidal pattern: peaks in January and July.
    """
    # Day of year normalized to [0, 2π]
    day_of_year = dt.timetuple().tm_yday
    angle = 2 * math.pi * day_of_year / 365.0
    # cos peaks at day 0 (Jan 1) and troughs at day 182 (July 1)
    # We want peaks in winter AND summer, so use |cos|
    return 1.0 + 0.3 * abs(math.cos(angle))


def daily_factor(dt: datetime) -> float:
    """Return a daily load multiplier (higher during business hours).

    Business hours (8-18) use 1.4x, nights/weekends use 0.7x.
    """
    hour = dt.hour
    weekday = dt.weekday()  # 0=Monday, 6=Sunday
    is_business = weekday < 5 and 8 <= hour < 18
    return 1.4 if is_business else 0.7


def generate_kwh(
    building_id: str,
    dt: datetime,
    reading_type: str,
    rng: random.Random,
) -> float:
    """Generate a realistic kWh value for a reading.

    Combines base load, seasonal pattern, daily pattern, and noise.

    Args:
        building_id: Building identifier.
        dt: Timestamp of the reading.
        reading_type: "electricity", "gas", or "solar".
        rng: Seeded random number generator.

    Returns:
        kWh value (always positive).
    """
    if reading_type == "electricity":
        base = BASE_ELECTRICITY_KWH.get(building_id, 10.0)

        # Special boost for B007 in August 2024 (TASK-009)
        if building_id == "B007" and dt.year == 2024 and dt.month == 8:
            base *= B007_AUGUST_MULTIPLIER

        s_factor = seasonal_factor(dt)
        d_factor = daily_factor(dt)
        noise = rng.gauss(1.0, 0.08)  # 8% noise
        return max(0.1, base * s_factor * d_factor * noise)

    elif reading_type == "gas":
        # Gas is higher in winter (heating), minimal in summer
        day_of_year = dt.timetuple().tm_yday
        angle = 2 * math.pi * day_of_year / 365.0
        # Peak in winter (day 0/365), trough in summer
        winter_factor = 1.0 + 0.8 * math.cos(angle)
        base = BASE_ELECTRICITY_KWH.get(building_id, 10.0) * 0.3
        noise = rng.gauss(1.0, 0.1)
        return max(0.01, base * max(0.1, winter_factor) * noise)

    elif reading_type == "solar":
        # Solar only generates during daylight; summer produces more
        hour = dt.hour
        if hour < 6 or hour >= 20:
            return 0.0
        day_of_year = dt.timetuple().tm_yday
        # Summer peak (day 182 ≈ July 1)
        summer_factor = 1.0 + 0.5 * math.sin(2 * math.pi * (day_of_year - 80) / 365.0)
        daylight_factor = math.sin(math.pi * (hour - 6) / 14.0)  # peak at noon
        base = BASE_ELECTRICITY_KWH.get(building_id, 10.0) * 0.4
        noise = rng.gauss(1.0, 0.15)
        return max(0.0, base * max(0.0, summer_factor) * max(0.0, daylight_factor) * noise)

    return 0.0


async def drop_and_recreate_tables(engine: AsyncEngine) -> None:
    """Drop all tables and recreate them from the ORM metadata.

    Used only by the seed script to ensure a clean slate.
    In production, use Alembic migrations instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables dropped and recreated")


async def seed_database(database_url: str) -> dict[str, int]:
    """Seed the database with deterministic synthetic energy data.

    Args:
        database_url: SQLAlchemy async database URL.

    Returns:
        Dict with counts of records created per type.
    """
    engine = get_engine(database_url)
    session_factory = get_session_factory(engine)

    rng = random.Random(RANDOM_SEED)
    created_at = datetime(2024, 1, 1, 0, 0, 0)

    # Ensure tables exist
    await drop_and_recreate_tables(engine)

    async with session_factory() as session:
        # ── Seed buildings ──────────────────────────────────────────────────
        logger.info("Seeding buildings...")
        buildings = [
            Building(
                id=bid,
                name=name,
                address=address,
                floor_count=floors,
                area_sqft=area,
                created_at=created_at,
            )
            for bid, name, address, floors, area in BUILDINGS
        ]
        session.add_all(buildings)
        await session.commit()
        logger.info(f"Seeded {len(buildings)} buildings")

        # ── Seed energy readings ────────────────────────────────────────────
        start_date = datetime(2023, 1, 1, 0, 0, 0)
        end_date = datetime(2025, 1, 1, 0, 0, 0)  # exclusive

        total_hours = int((end_date - start_date).total_seconds() / 3600)
        building_ids = [b[0] for b in BUILDINGS]

        electricity_count = 0
        gas_count = 0
        solar_count = 0

        batch: list[EnergyReading] = []

        logger.info(
            f"Generating readings for {len(building_ids)} buildings x "
            f"{total_hours} hours x 2 years..."
        )

        anomaly_set = set(ANOMALY_TIMESTAMPS)

        for hour_offset in range(total_hours):
            dt = start_date + timedelta(hours=hour_offset)

            for bid in building_ids:
                meter_id = f"ELEC-{bid}"
                kwh = generate_kwh(bid, dt, "electricity", rng)

                # Plant anomaly for B003 in November 2024
                if bid == ANOMALY_BUILDING and dt in anomaly_set:
                    base_kwh = generate_kwh(bid, dt, "electricity", rng)
                    kwh = base_kwh * ANOMALY_MULTIPLIER

                batch.append(
                    EnergyReading(
                        building_id=bid,
                        timestamp=dt,
                        kwh=kwh,
                        reading_type="electricity",
                        meter_id=meter_id,
                        created_at=created_at,
                    )
                )
                electricity_count += 1

                # Gas readings for subset of buildings
                if bid in GAS_BUILDINGS:
                    gas_kwh = generate_kwh(bid, dt, "gas", rng)
                    batch.append(
                        EnergyReading(
                            building_id=bid,
                            timestamp=dt,
                            kwh=gas_kwh,
                            reading_type="gas",
                            meter_id=f"GAS-{bid}",
                            created_at=created_at,
                        )
                    )
                    gas_count += 1

                # Solar readings for subset of buildings
                if bid in SOLAR_BUILDINGS:
                    solar_kwh = generate_kwh(bid, dt, "solar", rng)
                    batch.append(
                        EnergyReading(
                            building_id=bid,
                            timestamp=dt,
                            kwh=solar_kwh,
                            reading_type="solar",
                            meter_id=f"SOLAR-{bid}",
                            created_at=created_at,
                        )
                    )
                    solar_count += 1

                # Flush batch to keep memory bounded
                if len(batch) >= BATCH_SIZE:
                    session.add_all(batch)
                    await session.commit()
                    batch = []

            # Progress logging every 30 days
            if hour_offset % (24 * 30) == 0:
                days_done = hour_offset // 24
                logger.info(f"  Progress: {days_done} days processed...")

        # Flush remaining rows
        if batch:
            session.add_all(batch)
            await session.commit()

    await engine.dispose()

    total_readings = electricity_count + gas_count + solar_count
    logger.info(
        f"Seed complete: {electricity_count} electricity + {gas_count} gas + "
        f"{solar_count} solar = {total_readings} total readings"
    )

    return {
        "buildings": len(buildings),
        "electricity": electricity_count,
        "gas": gas_count,
        "solar": solar_count,
        "total_readings": total_readings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the AI MCP Data Platform database")
    parser.add_argument(
        "--database-url",
        default="sqlite+aiosqlite:///./data/db.sqlite",
        help="SQLAlchemy async database URL",
    )
    args = parser.parse_args()

    counts = asyncio.run(seed_database(args.database_url))
    logger.info(f"Final counts: {counts}")


if __name__ == "__main__":
    main()
