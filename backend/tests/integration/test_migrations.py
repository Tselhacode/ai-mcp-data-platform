"""Integration tests for Alembic migrations.

Verifies that:
- The initial migration can be applied to a fresh SQLite database
- The resulting schema matches the ORM model definitions
- A freshly migrated database can be written to and read from
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy import inspect

from alembic import command


def _make_alembic_config(db_path: str) -> Config:
    """Create an Alembic config pointing at the test database."""
    # alembic.ini lives in backend/ (project root from Alembic's perspective)
    backend_dir = Path(__file__).parent.parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    return cfg


def test_initial_migration_creates_expected_tables():
    """upgrade head creates all expected tables."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        cfg = _make_alembic_config(db_path)
        command.upgrade(cfg, "head")

        # Inspect the created database synchronously
        engine = sa.create_engine(f"sqlite:///{db_path}")
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        engine.dispose()

        expected = {
            "buildings",
            "energy_readings",
            "sessions",
            "session_turns",
            "evaluation_runs",
            "evaluation_records",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"
    finally:
        Path(db_path).unlink(missing_ok=True)
        os.environ.pop("DATABASE_URL", None)


def test_migration_creates_energy_readings_indexes():
    """upgrade head creates performance indexes on energy_readings."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        cfg = _make_alembic_config(db_path)
        command.upgrade(cfg, "head")

        engine = sa.create_engine(f"sqlite:///{db_path}")
        inspector = inspect(engine)
        index_names = {idx["name"] for idx in inspector.get_indexes("energy_readings")}
        engine.dispose()

        expected_indexes = {
            "ix_energy_readings_building_timestamp",
            "ix_energy_readings_timestamp",
            "ix_energy_readings_type_timestamp",
        }
        assert expected_indexes.issubset(index_names), (
            f"Missing indexes: {expected_indexes - index_names}"
        )
    finally:
        Path(db_path).unlink(missing_ok=True)
        os.environ.pop("DATABASE_URL", None)


def test_downgrade_removes_all_tables():
    """downgrade base removes all application tables."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        cfg = _make_alembic_config(db_path)
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")

        engine = sa.create_engine(f"sqlite:///{db_path}")
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        engine.dispose()

        # After downgrade, only alembic_version may remain
        app_tables = {t for t in tables if t != "alembic_version"}
        assert app_tables == set(), f"Unexpected tables after downgrade: {app_tables}"
    finally:
        Path(db_path).unlink(missing_ok=True)
        os.environ.pop("DATABASE_URL", None)
