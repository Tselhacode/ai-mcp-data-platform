"""Repository Protocol interfaces for the AI MCP Data Platform.

These Protocol classes define the contract that any repository implementation
must satisfy. Using Protocol (structural subtyping) rather than ABC allows:
  - SQLAlchemy implementations for production/integration tests
  - In-memory fake implementations for unit tests
  - No inheritance required — any class with the right methods qualifies

No LangChain, FastMCP, or FastAPI imports are permitted in this module.
"""

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from data.models import (
    Building,
    EnergyReading,
    EvaluationRecord,
    EvaluationRun,
    Session,
    SessionTurn,
)

# ---------------------------------------------------------------------------
# Return types for computed/aggregated results
# ---------------------------------------------------------------------------


class MonthlySummary:
    """Aggregated energy consumption for a building in a calendar month."""

    def __init__(
        self,
        building_id: str,
        year: int,
        month: int,
        total_kwh: float,
        reading_count: int,
        reading_type: str,
    ) -> None:
        self.building_id = building_id
        self.year = year
        self.month = month
        self.total_kwh = total_kwh
        self.reading_count = reading_count
        self.reading_type = reading_type

    def __repr__(self) -> str:
        return (
            f"MonthlySummary(building_id={self.building_id!r}, "
            f"year={self.year!r}, month={self.month!r}, "
            f"total_kwh={self.total_kwh!r})"
        )


class AnomalyRecord:
    """A detected anomalous energy reading."""

    def __init__(
        self,
        building_id: str,
        timestamp: datetime,
        kwh: float,
        mean_kwh: float,
        stddev_kwh: float,
        deviation: float,
        reading_type: str,
        meter_id: str,
    ) -> None:
        self.building_id = building_id
        self.timestamp = timestamp
        self.kwh = kwh
        self.mean_kwh = mean_kwh
        self.stddev_kwh = stddev_kwh
        self.deviation = deviation  # number of standard deviations from mean
        self.reading_type = reading_type
        self.meter_id = meter_id

    def __repr__(self) -> str:
        return (
            f"AnomalyRecord(building_id={self.building_id!r}, "
            f"timestamp={self.timestamp!r}, kwh={self.kwh!r}, "
            f"deviation={self.deviation!r})"
        )


# ---------------------------------------------------------------------------
# Energy repository protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class EnergyRepositoryProtocol(Protocol):
    """Contract for all energy data access implementations.

    Implementations must be async. No LangChain dependencies permitted.
    """

    async def get_buildings(self) -> list[Building]:
        """Return all buildings in the dataset."""
        ...

    async def get_building(self, building_id: str) -> Building | None:
        """Return a single building by ID, or None if not found."""
        ...

    async def get_consumption(
        self,
        building_id: str,
        start: datetime,
        end: datetime,
        reading_type: str = "electricity",
    ) -> list[EnergyReading]:
        """Return energy readings for a building within a time range.

        Args:
            building_id: The building ID (e.g. "B007").
            start: Inclusive start of the time range (UTC).
            end: Exclusive end of the time range (UTC).
            reading_type: One of "electricity", "gas", "solar".

        Returns:
            List of EnergyReading objects ordered by timestamp ascending.
        """
        ...

    async def get_monthly_summary(
        self,
        building_id: str | None,
        year: int,
        month: int,
    ) -> list[MonthlySummary]:
        """Return aggregated consumption by building for a calendar month.

        Args:
            building_id: If provided, return only this building's summary.
                         If None, return summaries for all buildings.
            year: Calendar year (e.g. 2024).
            month: Calendar month (1-12).

        Returns:
            List of MonthlySummary objects, one per building.
        """
        ...

    async def find_anomalies(
        self,
        building_id: str | None,
        threshold_stddev: float = 2.0,
    ) -> list[AnomalyRecord]:
        """Detect anomalous energy readings using statistical deviation.

        A reading is anomalous if it deviates from the building's mean
        by more than `threshold_stddev` standard deviations.

        Args:
            building_id: If provided, check only this building.
                         If None, check all buildings.
            threshold_stddev: Number of standard deviations to use as
                              the anomaly threshold (default: 2.0).

        Returns:
            List of AnomalyRecord objects describing anomalous readings.
        """
        ...

    async def execute_readonly_query(
        self,
        sql: str,
        params: dict[str, Any],
        fetch_limit: int,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Execute a pre-validated read-only SQL SELECT statement.

        This method must only be called with SQL that has been validated
        as a single SELECT statement by the caller. Raw user input must
        not be passed here without prior validation.

        Args:
            sql: Pre-validated SQL SELECT statement with :param placeholders.
            params: Bind parameter values keyed by placeholder name.
            fetch_limit: Maximum number of rows to fetch.

        Returns:
            Tuple of (column_names, rows) where each row is a plain tuple.
        """
        ...


# ---------------------------------------------------------------------------
# Session repository protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SessionRepositoryProtocol(Protocol):
    """Contract for conversation session persistence implementations."""

    async def create_session(self, session_id: str) -> Session:
        """Create and persist a new session.

        Args:
            session_id: UUID string to use as the session ID.

        Returns:
            The newly created Session object.
        """
        ...

    async def get_session(self, session_id: str) -> Session | None:
        """Return an existing session by ID, or None if not found.

        Args:
            session_id: The session UUID to look up.

        Returns:
            The Session object if found, else None.
        """
        ...

    async def update_last_active(self, session_id: str) -> None:
        """Update the last_active timestamp for a session to now.

        Args:
            session_id: The session UUID to update.
        """
        ...

    async def get_history(self, session_id: str) -> list[SessionTurn]:
        """Return all turns for a session in chronological order.

        Args:
            session_id: The session UUID.

        Returns:
            List of SessionTurn objects ordered by created_at ascending.
        """
        ...

    async def list_sessions(self, limit: int = 20) -> list[Session]:
        """Return recent sessions ordered by last_active descending.

        Args:
            limit: Maximum number of sessions to return (default 20).

        Returns:
            List of Session objects.
        """
        ...

    async def save_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
        tools_called: list[object],
        model: str,
        provider: str,
        latency_ms: int,
    ) -> SessionTurn:
        """Persist a conversation turn.

        Creates the session if it does not already exist.

        Args:
            session_id: The session UUID.
            question: The user's question.
            answer: The LLM's final answer.
            tools_called: List of tool call records (serializable).
            model: LLM model ID used.
            provider: LLM provider name.
            latency_ms: Total response latency in milliseconds.

        Returns:
            The persisted SessionTurn object.
        """
        ...


# ---------------------------------------------------------------------------
# Evaluation repository protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class EvalRepositoryProtocol(Protocol):
    """Contract for evaluation run and record persistence."""

    async def create_run(
        self,
        run_id: str,
        model: str,
        provider: str,
        task_count: int,
    ) -> EvaluationRun:
        """Create a new evaluation run record.

        Args:
            run_id: UUID string for the run.
            model: LLM model ID.
            provider: LLM provider name.
            task_count: Total number of tasks in this run.

        Returns:
            The newly created EvaluationRun object.
        """
        ...

    async def complete_run(
        self,
        run_id: str,
        pass_count: int,
    ) -> EvaluationRun:
        """Mark an evaluation run as complete.

        Args:
            run_id: UUID of the run to complete.
            pass_count: Number of tasks that passed.

        Returns:
            The updated EvaluationRun object.
        """
        ...

    async def save_record(
        self,
        run_id: str,
        task_id: str,
        question: str,
        tools_called: list[object],
        final_answer: str,
        expected_answer: str | None,
        passed: bool,
        score: float,
        judge_rationale: str | None,
        latency_ms: int,
    ) -> EvaluationRecord:
        """Persist a single evaluation task result.

        Args:
            run_id: UUID of the parent evaluation run.
            task_id: Task identifier (e.g. "TASK-009").
            question: The task question text.
            tools_called: List of tool call records.
            final_answer: The LLM's answer to the task.
            expected_answer: Expected answer string, or None for judge-scored tasks.
            passed: Whether the task was considered passed.
            score: Float score in [0.0, 1.0].
            judge_rationale: LLM-as-judge explanation, or None.
            latency_ms: Total task latency in milliseconds.

        Returns:
            The persisted EvaluationRecord object.
        """
        ...

    async def get_run(self, run_id: str) -> EvaluationRun | None:
        """Return an evaluation run by ID, or None if not found."""
        ...

    async def get_records(self, run_id: str) -> list[EvaluationRecord]:
        """Return all records for an evaluation run."""
        ...
