"""Unit tests for SQLAlchemy ORM models.

Tests model construction, repr, and basic attribute constraints.
No database I/O — these verify model definitions, not persistence.
"""

from datetime import datetime

from data.models import (
    Building,
    EnergyReading,
    EvaluationRecord,
    EvaluationRun,
    Session,
    SessionTurn,
)


class TestBuilding:
    def test_building_construction(self):
        b = Building(
            id="B001",
            name="City Hall",
            address="100 Main St",
            floor_count=5,
            area_sqft=45000.0,
            created_at=datetime(2024, 1, 1),
        )
        assert b.id == "B001"
        assert b.name == "City Hall"
        assert b.floor_count == 5
        assert b.area_sqft == 45000.0

    def test_building_repr(self):
        b = Building(
            id="B007",
            name="Data Center",
            address="700 Server Blvd",
            floor_count=4,
            area_sqft=110000.0,
            created_at=datetime(2024, 1, 1),
        )
        assert "B007" in repr(b)
        assert "Data Center" in repr(b)

    def test_building_id_formats(self):
        for i in range(1, 21):
            bid = f"B{i:03d}"
            b = Building(
                id=bid,
                name=f"Building {i}",
                address=f"{i * 100} Street",
                floor_count=i,
                area_sqft=float(i * 5000),
                created_at=datetime(2024, 1, 1),
            )
            assert b.id == bid


class TestEnergyReading:
    def test_energy_reading_construction(self):
        r = EnergyReading(
            building_id="B001",
            timestamp=datetime(2024, 7, 1, 10, 0),
            kwh=12.5,
            reading_type="electricity",
            meter_id="ELEC-B001",
            created_at=datetime(2024, 1, 1),
        )
        assert r.building_id == "B001"
        assert r.kwh == 12.5
        assert r.reading_type == "electricity"

    def test_energy_reading_types(self):
        for rtype in ("electricity", "gas", "solar"):
            r = EnergyReading(
                building_id="B001",
                timestamp=datetime(2024, 7, 1),
                kwh=10.0,
                reading_type=rtype,
                meter_id=f"{rtype.upper()}-B001",
                created_at=datetime(2024, 1, 1),
            )
            assert r.reading_type == rtype

    def test_energy_reading_repr(self):
        r = EnergyReading(
            building_id="B007",
            timestamp=datetime(2024, 7, 1, 12, 0),
            kwh=45.0,
            reading_type="electricity",
            meter_id="ELEC-B007",
            created_at=datetime(2024, 1, 1),
        )
        assert "B007" in repr(r)
        assert "45.0" in repr(r)


class TestSession:
    def test_session_construction(self):
        s = Session(
            id="test-uuid-1234",
            created_at=datetime(2024, 1, 1),
            last_active=datetime(2024, 1, 1),
        )
        assert s.id == "test-uuid-1234"

    def test_session_repr(self):
        s = Session(
            id="abc-123",
            created_at=datetime(2024, 1, 1),
            last_active=datetime(2024, 1, 1),
        )
        assert "abc-123" in repr(s)


class TestSessionTurn:
    def test_session_turn_construction(self):
        turn = SessionTurn(
            session_id="sess-1",
            question="What is the highest consuming building?",
            answer="Building B007",
            tools_called=[{"tool": "get_monthly_summary"}],
            model="fake",
            provider="fake",
            latency_ms=150,
            created_at=datetime(2024, 1, 1),
        )
        assert turn.session_id == "sess-1"
        assert turn.latency_ms == 150
        assert isinstance(turn.tools_called, list)


class TestEvaluationRun:
    def test_eval_run_construction(self):
        run = EvaluationRun(
            id="run-uuid-001",
            model="fake",
            provider="fake",
            started_at=datetime(2024, 1, 1),
            completed_at=None,
            task_count=9,
            pass_count=0,
        )
        assert run.id == "run-uuid-001"
        assert run.completed_at is None

    def test_eval_run_repr(self):
        run = EvaluationRun(
            id="run-001",
            model="anthropic.claude-3-5-sonnet-20241022-v2:0",
            provider="bedrock",
            started_at=datetime(2024, 1, 1),
            completed_at=None,
            task_count=5,
            pass_count=3,
        )
        assert "run-001" in repr(run)


class TestEvaluationRecord:
    def test_eval_record_construction(self):
        rec = EvaluationRecord(
            run_id="run-001",
            task_id="TASK-009",
            question="Which building had the largest July-to-August increase?",
            tools_called=[],
            final_answer="Building B007",
            expected_answer="B007",
            passed=True,
            score=1.0,
            judge_rationale=None,
            latency_ms=500,
            created_at=datetime(2024, 1, 1),
        )
        assert rec.task_id == "TASK-009"
        assert rec.passed is True
        assert rec.score == 1.0

    def test_eval_record_repr(self):
        rec = EvaluationRecord(
            run_id="run-001",
            task_id="TASK-001",
            question="Q",
            tools_called=[],
            final_answer="A",
            expected_answer=None,
            passed=False,
            score=0.0,
            judge_rationale="The answer was incorrect.",
            latency_ms=200,
            created_at=datetime(2024, 1, 1),
        )
        assert "TASK-001" in repr(rec)
        assert "False" in repr(rec)
