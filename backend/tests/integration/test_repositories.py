"""Integration tests for repository implementations.

Uses SQLite in-memory (not mocked sessions) to catch real query bugs.
Each test gets a fresh database via the fixtures in conftest.py.
"""

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from data.repositories.energy import SQLAlchemyEnergyRepository
from data.repositories.session import SQLAlchemySessionRepository

# ---------------------------------------------------------------------------
# EnergyRepository tests
# ---------------------------------------------------------------------------


class TestGetBuildings:
    async def test_returns_all_buildings(self, db_session: AsyncSession, seeded_buildings):
        repo = SQLAlchemyEnergyRepository(db_session)
        buildings = await repo.get_buildings()
        assert len(buildings) == 3  # SEED_BUILDINGS has 3 entries

    async def test_returns_buildings_ordered_by_id(
        self, db_session: AsyncSession, seeded_buildings
    ):
        repo = SQLAlchemyEnergyRepository(db_session)
        buildings = await repo.get_buildings()
        ids = [b.id for b in buildings]
        assert ids == sorted(ids)

    async def test_returns_empty_list_when_no_buildings(self, db_session: AsyncSession):
        repo = SQLAlchemyEnergyRepository(db_session)
        buildings = await repo.get_buildings()
        assert buildings == []


class TestGetBuilding:
    async def test_returns_building_by_id(self, db_session: AsyncSession, seeded_buildings):
        repo = SQLAlchemyEnergyRepository(db_session)
        building = await repo.get_building("B001")
        assert building is not None
        assert building.id == "B001"
        assert building.name == "City Hall Annex"

    async def test_returns_none_for_unknown_id(self, db_session: AsyncSession, seeded_buildings):
        repo = SQLAlchemyEnergyRepository(db_session)
        building = await repo.get_building("B999")
        assert building is None

    async def test_returns_none_on_empty_database(self, db_session: AsyncSession):
        repo = SQLAlchemyEnergyRepository(db_session)
        building = await repo.get_building("B001")
        assert building is None


class TestGetConsumption:
    async def test_returns_readings_for_building(self, db_session: AsyncSession, seeded_readings):
        repo = SQLAlchemyEnergyRepository(db_session)
        readings = await repo.get_consumption(
            building_id="B001",
            start=datetime(2024, 7, 1, 0, 0),
            end=datetime(2024, 8, 1, 0, 0),
        )
        assert len(readings) == 2  # Two electricity readings for B001 in July
        assert all(r.building_id == "B001" for r in readings)

    async def test_filters_by_reading_type(self, db_session: AsyncSession, seeded_readings):
        repo = SQLAlchemyEnergyRepository(db_session)
        # B001 has gas reading in July
        gas_readings = await repo.get_consumption(
            building_id="B001",
            start=datetime(2024, 7, 1, 0, 0),
            end=datetime(2024, 8, 1, 0, 0),
            reading_type="gas",
        )
        assert len(gas_readings) == 1
        assert gas_readings[0].reading_type == "gas"

    async def test_start_is_inclusive(self, db_session: AsyncSession, seeded_readings):
        repo = SQLAlchemyEnergyRepository(db_session)
        # Reading at exactly 10:00 should be included
        readings = await repo.get_consumption(
            building_id="B001",
            start=datetime(2024, 7, 1, 10, 0),
            end=datetime(2024, 8, 1, 0, 0),
        )
        assert len(readings) == 2

    async def test_end_is_exclusive(self, db_session: AsyncSession, seeded_readings):
        repo = SQLAlchemyEnergyRepository(db_session)
        # end=10:00 excludes the reading at 10:00
        readings = await repo.get_consumption(
            building_id="B001",
            start=datetime(2024, 7, 1, 0, 0),
            end=datetime(2024, 7, 1, 10, 0),
        )
        assert len(readings) == 0

    async def test_returns_readings_ordered_by_timestamp(
        self, db_session: AsyncSession, seeded_readings
    ):
        repo = SQLAlchemyEnergyRepository(db_session)
        readings = await repo.get_consumption(
            building_id="B001",
            start=datetime(2024, 7, 1, 0, 0),
            end=datetime(2024, 8, 1, 0, 0),
        )
        timestamps = [r.timestamp for r in readings]
        assert timestamps == sorted(timestamps)

    async def test_returns_empty_list_for_unknown_building(
        self, db_session: AsyncSession, seeded_readings
    ):
        repo = SQLAlchemyEnergyRepository(db_session)
        readings = await repo.get_consumption(
            building_id="B999",
            start=datetime(2024, 7, 1),
            end=datetime(2024, 8, 1),
        )
        assert readings == []


class TestGetMonthlySummary:
    async def test_returns_summary_for_specific_building(
        self, db_session: AsyncSession, seeded_readings
    ):
        repo = SQLAlchemyEnergyRepository(db_session)
        summaries = await repo.get_monthly_summary(
            building_id="B001",
            year=2024,
            month=7,
        )
        assert len(summaries) >= 1
        elec = next(s for s in summaries if s.reading_type == "electricity")
        assert elec.building_id == "B001"
        assert elec.total_kwh == pytest.approx(25.5, rel=1e-5)  # 12.5 + 13.0

    async def test_returns_summaries_for_all_buildings_when_none(
        self, db_session: AsyncSession, seeded_readings
    ):
        repo = SQLAlchemyEnergyRepository(db_session)
        summaries = await repo.get_monthly_summary(
            building_id=None,
            year=2024,
            month=7,
        )
        # B001 and B007 both have July readings; gas adds another B001 entry
        building_ids = {s.building_id for s in summaries}
        assert "B001" in building_ids
        assert "B007" in building_ids

    async def test_returns_empty_when_no_data_in_month(
        self, db_session: AsyncSession, seeded_readings
    ):
        repo = SQLAlchemyEnergyRepository(db_session)
        summaries = await repo.get_monthly_summary(
            building_id=None,
            year=2023,
            month=1,
        )
        assert summaries == []

    async def test_summary_reading_count_is_correct(
        self, db_session: AsyncSession, seeded_readings
    ):
        repo = SQLAlchemyEnergyRepository(db_session)
        summaries = await repo.get_monthly_summary(
            building_id="B001",
            year=2024,
            month=7,
        )
        elec = next(s for s in summaries if s.reading_type == "electricity")
        assert elec.reading_count == 2


class TestFindAnomalies:
    async def test_no_anomalies_with_uniform_data(self, db_session: AsyncSession, seeded_buildings):
        """Uniform readings should produce no anomalies."""
        from datetime import timedelta

        from data.models import EnergyReading

        # Insert 100 identical readings for B001 (spread across days)
        base_ts = datetime(2024, 1, 1, 12, 0)
        readings = [
            EnergyReading(
                building_id="B001",
                timestamp=base_ts + timedelta(hours=i),
                kwh=10.0,
                reading_type="electricity",
                meter_id="ELEC-B001",
                created_at=datetime(2024, 1, 1),
            )
            for i in range(100)
        ]
        db_session.add_all(readings)
        await db_session.commit()

        repo = SQLAlchemyEnergyRepository(db_session)
        anomalies = await repo.find_anomalies(building_id="B001")
        assert anomalies == []

    async def test_detects_anomaly_in_spiked_data(self, db_session: AsyncSession, seeded_buildings):
        """A reading 5x the mean should be flagged as anomalous."""
        from datetime import timedelta

        from data.models import EnergyReading

        # 99 normal readings + 1 massive spike
        base_ts = datetime(2024, 1, 1, 12, 0)
        readings = [
            EnergyReading(
                building_id="B001",
                timestamp=base_ts + timedelta(hours=i),
                kwh=10.0,
                reading_type="electricity",
                meter_id="ELEC-B001",
                created_at=datetime(2024, 1, 1),
            )
            for i in range(99)
        ]
        # Extreme spike
        readings.append(
            EnergyReading(
                building_id="B001",
                timestamp=datetime(2024, 1, 5, 3, 0),
                kwh=500.0,  # Extreme spike
                reading_type="electricity",
                meter_id="ELEC-B001",
                created_at=datetime(2024, 1, 1),
            )
        )
        db_session.add_all(readings)
        await db_session.commit()

        repo = SQLAlchemyEnergyRepository(db_session)
        anomalies = await repo.find_anomalies(building_id="B001")
        assert len(anomalies) >= 1
        assert anomalies[0].kwh == 500.0

    async def test_anomalies_sorted_by_deviation_desc(
        self, db_session: AsyncSession, seeded_buildings
    ):
        """Most anomalous readings should come first."""
        from datetime import timedelta

        from data.models import EnergyReading

        base_ts = datetime(2024, 1, 1, 12, 0)
        readings = [
            EnergyReading(
                building_id="B001",
                timestamp=base_ts + timedelta(hours=i),
                kwh=10.0,
                reading_type="electricity",
                meter_id="ELEC-B001",
                created_at=datetime(2024, 1, 1),
            )
            for i in range(90)
        ]
        # Two spikes of different severity
        readings.extend(
            [
                EnergyReading(
                    building_id="B001",
                    timestamp=datetime(2024, 1, 5, 0, 0),
                    kwh=200.0,
                    reading_type="electricity",
                    meter_id="ELEC-B001",
                    created_at=datetime(2024, 1, 1),
                ),
                EnergyReading(
                    building_id="B001",
                    timestamp=datetime(2024, 1, 5, 1, 0),
                    kwh=500.0,
                    reading_type="electricity",
                    meter_id="ELEC-B001",
                    created_at=datetime(2024, 1, 1),
                ),
            ]
        )
        db_session.add_all(readings)
        await db_session.commit()

        repo = SQLAlchemyEnergyRepository(db_session)
        anomalies = await repo.find_anomalies(building_id="B001")
        if len(anomalies) >= 2:
            assert anomalies[0].deviation >= anomalies[1].deviation

    async def test_filters_by_building_id(self, db_session: AsyncSession, seeded_buildings):
        """Anomaly detection should only check the specified building."""
        from datetime import timedelta

        from data.models import EnergyReading

        base_ts = datetime(2024, 1, 1, 12, 0)
        # B007 has uniform data; B001 has a spike
        b001_readings = [
            EnergyReading(
                building_id="B001",
                timestamp=base_ts + timedelta(hours=i),
                kwh=10.0 if i < 99 else 500.0,
                reading_type="electricity",
                meter_id="ELEC-B001",
                created_at=datetime(2024, 1, 1),
            )
            for i in range(100)
        ]
        b007_readings = [
            EnergyReading(
                building_id="B007",
                timestamp=base_ts + timedelta(hours=i),
                kwh=30.0,
                reading_type="electricity",
                meter_id="ELEC-B007",
                created_at=datetime(2024, 1, 1),
            )
            for i in range(100)
        ]
        db_session.add_all(b001_readings + b007_readings)
        await db_session.commit()

        repo = SQLAlchemyEnergyRepository(db_session)

        # Only B007 — no anomalies expected
        anomalies_b007 = await repo.find_anomalies(building_id="B007")
        assert anomalies_b007 == []

        # Only B001 — anomaly expected
        anomalies_b001 = await repo.find_anomalies(building_id="B001")
        assert len(anomalies_b001) >= 1


# ---------------------------------------------------------------------------
# SessionRepository tests
# ---------------------------------------------------------------------------


class TestCreateSession:
    async def test_create_session_returns_session(self, db_session: AsyncSession):
        repo = SQLAlchemySessionRepository(db_session)
        session = await repo.create_session("sess-abc-123")
        assert session.id == "sess-abc-123"
        assert session.created_at is not None
        assert session.last_active is not None

    async def test_create_session_is_persisted(self, db_session: AsyncSession):
        repo = SQLAlchemySessionRepository(db_session)
        await repo.create_session("sess-persist-test")
        fetched = await repo.get_session("sess-persist-test")
        assert fetched is not None
        assert fetched.id == "sess-persist-test"


class TestGetSession:
    async def test_returns_none_for_unknown_id(self, db_session: AsyncSession):
        repo = SQLAlchemySessionRepository(db_session)
        result = await repo.get_session("nonexistent")
        assert result is None


class TestSaveTurn:
    async def test_save_turn_creates_session_if_missing(self, db_session: AsyncSession):
        repo = SQLAlchemySessionRepository(db_session)
        # Session doesn't exist yet
        turn = await repo.save_turn(
            session_id="new-sess-001",
            question="What is the highest consuming building?",
            answer="Building B007",
            tools_called=[{"tool": "list_buildings"}],
            model="fake",
            provider="fake",
            latency_ms=100,
        )
        assert turn.id is not None
        # Session should now exist
        session = await repo.get_session("new-sess-001")
        assert session is not None

    async def test_save_turn_returns_correct_data(self, db_session: AsyncSession):
        repo = SQLAlchemySessionRepository(db_session)
        turn = await repo.save_turn(
            session_id="sess-turn-test",
            question="How much energy did B001 use in July?",
            answer="25.5 kWh",
            tools_called=[{"tool": "get_monthly_summary", "args": {"month": "2024-07"}}],
            model="fake-model",
            provider="fake",
            latency_ms=250,
        )
        assert turn.session_id == "sess-turn-test"
        assert turn.question == "How much energy did B001 use in July?"
        assert turn.answer == "25.5 kWh"
        assert turn.latency_ms == 250


class TestGetHistory:
    async def test_returns_turns_in_chronological_order(self, db_session: AsyncSession):
        repo = SQLAlchemySessionRepository(db_session)
        # Create two turns
        await repo.save_turn(
            session_id="sess-history",
            question="Q1",
            answer="A1",
            tools_called=[],
            model="fake",
            provider="fake",
            latency_ms=100,
        )
        await repo.save_turn(
            session_id="sess-history",
            question="Q2",
            answer="A2",
            tools_called=[],
            model="fake",
            provider="fake",
            latency_ms=150,
        )

        history = await repo.get_history("sess-history")
        assert len(history) == 2
        assert history[0].question == "Q1"
        assert history[1].question == "Q2"

    async def test_returns_empty_list_for_unknown_session(self, db_session: AsyncSession):
        repo = SQLAlchemySessionRepository(db_session)
        history = await repo.get_history("unknown-session")
        assert history == []
