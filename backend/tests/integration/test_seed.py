"""Integration tests for the seed script.

Tests use a smaller dataset (a single month) to verify:
  - Determinism (same seed → same data)
  - Known patterns (B007 is highest consumer, B003 anomaly)
  - B007 July→August 2024 increase (TASK-009)

The full 2-year seed is tested separately by running scripts/seed.py.
"""

import random
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.seed import (
    ANOMALY_BUILDING,
    ANOMALY_TIMESTAMPS,
    B007_AUGUST_MULTIPLIER,
    BASE_ELECTRICITY_KWH,
    BUILDINGS,
    GAS_BUILDINGS,
    RANDOM_SEED,
    SOLAR_BUILDINGS,
    daily_factor,
    generate_kwh,
    seasonal_factor,
)


class TestDeterminism:
    def test_same_seed_produces_same_values(self):
        """Two RNGs with the same seed must produce identical sequences."""
        rng1 = random.Random(RANDOM_SEED)
        rng2 = random.Random(RANDOM_SEED)
        dt = datetime(2024, 7, 1, 12, 0)
        v1 = generate_kwh("B001", dt, "electricity", rng1)
        v2 = generate_kwh("B001", dt, "electricity", rng2)
        assert v1 == pytest.approx(v2)

    def test_different_seeds_produce_different_values(self):
        """Different RNG seeds should generally produce different values."""
        rng1 = random.Random(42)
        rng2 = random.Random(99)
        dt = datetime(2024, 7, 1, 12, 0)
        # Not guaranteed, but extremely likely with good seeds
        values1 = [generate_kwh("B001", dt, "electricity", rng1) for _ in range(10)]
        values2 = [generate_kwh("B001", dt, "electricity", rng2) for _ in range(10)]
        assert values1 != values2


class TestBuildingDefinitions:
    def test_exactly_20_buildings(self):
        assert len(BUILDINGS) == 20

    def test_building_ids_are_b001_to_b020(self):
        ids = [b[0] for b in BUILDINGS]
        expected = [f"B{i:03d}" for i in range(1, 21)]
        assert ids == expected

    def test_b007_is_in_buildings(self):
        ids = [b[0] for b in BUILDINGS]
        assert "B007" in ids

    def test_gas_buildings_are_b001_to_b010(self):
        assert GAS_BUILDINGS == {f"B{i:03d}" for i in range(1, 11)}

    def test_solar_buildings_are_b001_to_b005(self):
        assert SOLAR_BUILDINGS == {f"B{i:03d}" for i in range(1, 6)}


class TestB007HighestConsumer:
    def test_b007_has_highest_base_load(self):
        """B007 must have the highest base electricity load."""
        max_building = max(BASE_ELECTRICITY_KWH, key=lambda k: BASE_ELECTRICITY_KWH[k])
        assert max_building == "B007"

    def test_b007_generates_more_than_other_buildings(self):
        """B007 should consistently generate more kWh than a typical building."""
        rng = random.Random(RANDOM_SEED)
        dt = datetime(2024, 7, 1, 12, 0)
        b007_kwh = generate_kwh("B007", dt, "electricity", rng)
        b001_kwh = generate_kwh("B001", dt, "electricity", random.Random(RANDOM_SEED))
        assert b007_kwh > b001_kwh


class TestB007JulyAugustIncrease:
    def test_august_multiplier_is_applied(self):
        """B007 readings in August 2024 should be boosted by B007_AUGUST_MULTIPLIER."""
        rng_july = random.Random(RANDOM_SEED)
        rng_august = random.Random(RANDOM_SEED)

        july_dt = datetime(2024, 7, 15, 12, 0)
        aug_dt = datetime(2024, 8, 15, 12, 0)

        # Generate many readings to average out noise
        n = 100
        july_values = [generate_kwh("B007", july_dt, "electricity", rng_july) for _ in range(n)]
        aug_values = [generate_kwh("B007", aug_dt, "electricity", rng_august) for _ in range(n)]

        july_avg = sum(july_values) / n
        aug_avg = sum(aug_values) / n

        # August should be higher due to the multiplier
        # Allow some tolerance for seasonal differences
        assert aug_avg > july_avg * 1.3, (
            f"Expected August avg ({aug_avg:.2f}) to be >1.3x July avg ({july_avg:.2f})"
        )

    def test_august_multiplier_constant_is_correct(self):
        assert B007_AUGUST_MULTIPLIER == pytest.approx(1.55, rel=1e-5)


class TestB003Anomaly:
    def test_anomaly_building_is_b003(self):
        assert ANOMALY_BUILDING == "B003"

    def test_anomaly_timestamps_are_in_november_2024(self):
        for ts in ANOMALY_TIMESTAMPS:
            assert ts.year == 2024
            assert ts.month == 11

    def test_anomaly_timestamps_count(self):
        """Should have exactly 3 planted anomaly timestamps."""
        assert len(ANOMALY_TIMESTAMPS) == 3


class TestSeasonalPattern:
    def test_winter_is_higher_than_spring(self):
        """Seasonal factor should be higher in winter than spring."""
        winter = seasonal_factor(datetime(2024, 1, 15))
        spring = seasonal_factor(datetime(2024, 4, 15))
        assert winter > spring

    def test_summer_is_higher_than_spring(self):
        """Seasonal factor should be higher in summer than spring."""
        summer = seasonal_factor(datetime(2024, 7, 15))
        spring = seasonal_factor(datetime(2024, 4, 15))
        assert summer > spring

    def test_seasonal_factor_always_positive(self):
        for month in range(1, 13):
            dt = datetime(2024, month, 15, 12, 0)
            assert seasonal_factor(dt) > 0


class TestDailyPattern:
    def test_business_hours_weekday_is_higher(self):
        """Business hours on weekdays should have higher load."""
        business = daily_factor(datetime(2024, 7, 1, 10, 0))  # Monday 10am
        night = daily_factor(datetime(2024, 7, 1, 2, 0))  # Monday 2am
        assert business > night

    def test_weekend_uses_lower_factor(self):
        """Weekends should use the lower (non-business) factor."""
        weekend = daily_factor(datetime(2024, 7, 7, 10, 0))  # Sunday 10am
        weekday = daily_factor(datetime(2024, 7, 1, 10, 0))  # Monday 10am
        assert weekend < weekday


class TestReadingTypes:
    def test_solar_is_zero_at_night(self):
        rng = random.Random(RANDOM_SEED)
        # Midnight — no solar generation
        night_kwh = generate_kwh("B001", datetime(2024, 7, 1, 0, 0), "solar", rng)
        assert night_kwh == 0.0

    def test_solar_is_positive_at_noon(self):
        rng = random.Random(RANDOM_SEED)
        noon_kwh = generate_kwh("B001", datetime(2024, 7, 1, 12, 0), "solar", rng)
        assert noon_kwh > 0.0

    def test_gas_is_positive(self):
        rng = random.Random(RANDOM_SEED)
        gas_kwh = generate_kwh("B001", datetime(2024, 1, 15, 12, 0), "gas", rng)
        assert gas_kwh > 0.0

    def test_electricity_is_always_positive(self):
        rng = random.Random(RANDOM_SEED)
        for hour in range(24):
            dt = datetime(2024, 7, 1, hour, 0)
            kwh = generate_kwh("B001", dt, "electricity", rng)
            assert kwh > 0.0, f"Expected positive kWh at hour {hour}"
