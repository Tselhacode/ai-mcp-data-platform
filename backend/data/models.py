"""SQLAlchemy ORM models for the AI MCP Data Platform.

Defines all database tables as mapped classes. Models are shared between
SQLite (local dev) and PostgreSQL (production) — only the connection URL differs.

Schema is managed by Alembic migrations. Never call Base.metadata.create_all()
from application code; use `alembic upgrade head` instead.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    pass


class Building(Base):
    """Metadata about a monitored building.

    The id (e.g. "B001") is assigned at seed time and serves as the
    primary identifier in all energy readings.
    """

    __tablename__ = "buildings"

    id: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    floor_count: Mapped[int] = mapped_column(Integer, nullable=False)
    area_sqft: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    readings: Mapped[list["EnergyReading"]] = relationship(
        "EnergyReading", back_populates="building", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"Building(id={self.id!r}, name={self.name!r})"


class EnergyReading(Base):
    """A single energy consumption reading for a building at a point in time.

    Hourly readings are the primary data source for analytics.
    Indexes support the main access patterns: range queries by building+time,
    cross-building time queries, and type-filtered queries.
    """

    __tablename__ = "energy_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    building_id: Mapped[str] = mapped_column(
        String(10), ForeignKey("buildings.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    kwh: Mapped[float] = mapped_column(Float, nullable=False)
    reading_type: Mapped[str] = mapped_column(String(20), nullable=False)
    meter_id: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    building: Mapped["Building"] = relationship(
        "Building", back_populates="readings", lazy="noload"
    )

    __table_args__ = (
        # Primary access pattern: range queries for a specific building
        Index("ix_energy_readings_building_timestamp", "building_id", "timestamp"),
        # Cross-building time queries
        Index("ix_energy_readings_timestamp", "timestamp"),
        # Type-filtered queries
        Index("ix_energy_readings_type_timestamp", "reading_type", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"EnergyReading(id={self.id!r}, building_id={self.building_id!r}, "
            f"timestamp={self.timestamp!r}, kwh={self.kwh!r})"
        )


class Session(Base):
    """A conversation session between a user and the AI analyst.

    Sessions group conversation turns and allow context to be maintained
    across multiple questions.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_active: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    turns: Mapped[list["SessionTurn"]] = relationship(
        "SessionTurn", back_populates="session", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"Session(id={self.id!r})"


class SessionTurn(Base):
    """A single question-answer turn within a conversation session.

    Stores the full context needed to reconstruct what happened:
    the question, answer, which tools were called, and performance metrics.
    """

    __tablename__ = "session_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    tools_called: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    session: Mapped["Session"] = relationship(
        "Session", back_populates="turns", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"SessionTurn(id={self.id!r}, session_id={self.session_id!r})"


class EvaluationRun(Base):
    """A single evaluation run executing a suite of agent tasks.

    Records aggregate results (pass_count / task_count) alongside
    per-task EvaluationRecord entries.
    """

    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    task_count: Mapped[int] = mapped_column(Integer, nullable=False)
    pass_count: Mapped[int] = mapped_column(Integer, nullable=False)

    records: Mapped[list["EvaluationRecord"]] = relationship(
        "EvaluationRecord", back_populates="run", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"EvaluationRun(id={self.id!r}, model={self.model!r})"


class EvaluationRecord(Base):
    """Result of a single evaluation task within an evaluation run.

    Captures everything needed to audit agent behavior: the question, tools used,
    the answer produced, whether it passed, and the judge's rationale.
    """

    __tablename__ = "evaluation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("evaluation_runs.id"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(String(50), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    tools_called: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    final_answer: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    judge_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    run: Mapped["EvaluationRun"] = relationship(
        "EvaluationRun", back_populates="records", lazy="noload"
    )

    def __repr__(self) -> str:
        return (
            f"EvaluationRecord(id={self.id!r}, task_id={self.task_id!r}, "
            f"passed={self.passed!r})"
        )
