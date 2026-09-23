"""Initial schema: buildings, energy_readings, sessions, session_turns,
evaluation_runs, evaluation_records.

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all initial tables and indexes."""

    # ── buildings ──────────────────────────────────────────────────────────
    op.create_table(
        "buildings",
        sa.Column("id", sa.String(10), primary_key=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("floor_count", sa.Integer, nullable=False),
        sa.Column("area_sqft", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    # ── energy_readings ────────────────────────────────────────────────────
    op.create_table(
        "energy_readings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "building_id",
            sa.String(10),
            sa.ForeignKey("buildings.id"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("kwh", sa.Float, nullable=False),
        sa.Column("reading_type", sa.String(20), nullable=False),
        sa.Column("meter_id", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_index(
        "ix_energy_readings_building_timestamp",
        "energy_readings",
        ["building_id", "timestamp"],
    )
    op.create_index(
        "ix_energy_readings_timestamp",
        "energy_readings",
        ["timestamp"],
    )
    op.create_index(
        "ix_energy_readings_type_timestamp",
        "energy_readings",
        ["reading_type", "timestamp"],
    )

    # ── sessions ───────────────────────────────────────────────────────────
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("last_active", sa.DateTime, nullable=False),
    )

    # ── session_turns ──────────────────────────────────────────────────────
    op.create_table(
        "session_turns",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("sessions.id"),
            nullable=False,
        ),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("tools_called", sa.JSON, nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    # ── evaluation_runs ────────────────────────────────────────────────────
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("task_count", sa.Integer, nullable=False),
        sa.Column("pass_count", sa.Integer, nullable=False),
    )

    # ── evaluation_records ─────────────────────────────────────────────────
    op.create_table(
        "evaluation_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("evaluation_runs.id"),
            nullable=False,
        ),
        sa.Column("task_id", sa.String(50), nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("tools_called", sa.JSON, nullable=False),
        sa.Column("final_answer", sa.Text, nullable=False),
        sa.Column("expected_answer", sa.Text, nullable=True),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("judge_rationale", sa.Text, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    """Drop all initial tables in reverse dependency order."""
    op.drop_table("evaluation_records")
    op.drop_table("evaluation_runs")
    op.drop_table("session_turns")
    op.drop_table("sessions")
    op.drop_index("ix_energy_readings_type_timestamp", table_name="energy_readings")
    op.drop_index("ix_energy_readings_timestamp", table_name="energy_readings")
    op.drop_index("ix_energy_readings_building_timestamp", table_name="energy_readings")
    op.drop_table("energy_readings")
    op.drop_table("buildings")
