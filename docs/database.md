# Database Design

---

## Overview

The database stores energy consumption data for a set of buildings, organized
by time series readings. The schema is intentionally simple to keep the focus
on the AI/MCP engineering rather than complex data modeling.

**Local development:** SQLite via `aiosqlite`
**Production:** PostgreSQL via `asyncpg`

The same SQLAlchemy models work for both. Only `DATABASE_URL` changes.

---

## Schema

### buildings

Stores metadata about each monitored building.

| Column | Type | Description |
|---|---|---|
| id | TEXT (PK) | Building identifier (e.g. "B001") |
| name | TEXT | Human-readable building name |
| address | TEXT | Physical address |
| floor_count | INTEGER | Number of floors |
| area_sqft | REAL | Total floor area in square feet |
| created_at | DATETIME | Record creation time |

### energy_readings

Stores individual consumption readings (time series).

| Column | Type | Description |
|---|---|---|
| id | INTEGER (PK) | Auto-increment |
| building_id | TEXT (FK → buildings.id) | Building reference |
| timestamp | DATETIME | Reading timestamp (UTC) |
| kwh | REAL | Kilowatt-hours consumed in this period |
| reading_type | TEXT | `electricity`, `gas`, `solar` |
| meter_id | TEXT | Source meter identifier |
| created_at | DATETIME | Record creation time |

Indexes:
- `(building_id, timestamp)` — primary access pattern for range queries
- `(timestamp)` — for cross-building time queries
- `(reading_type, timestamp)` — for type-filtered queries

### sessions

Stores conversation sessions.

| Column | Type | Description |
|---|---|---|
| id | TEXT (PK) | UUID |
| created_at | DATETIME | Session start time |
| last_active | DATETIME | Last activity time |

### session_turns

Stores individual turns within a conversation.

| Column | Type | Description |
|---|---|---|
| id | INTEGER (PK) | Auto-increment |
| session_id | TEXT (FK → sessions.id) | Session reference |
| question | TEXT | User question |
| answer | TEXT | LLM final answer |
| tools_called | JSON | List of tool calls (name, args, result summary) |
| model | TEXT | LLM model used |
| provider | TEXT | LLM provider used |
| latency_ms | INTEGER | Total response latency |
| created_at | DATETIME | Turn timestamp |

### evaluation_runs

| Column | Type | Description |
|---|---|---|
| id | TEXT (PK) | UUID |
| model | TEXT | LLM model used |
| provider | TEXT | LLM provider |
| started_at | DATETIME | Run start time |
| completed_at | DATETIME | Run end time |
| task_count | INTEGER | Total tasks in run |
| pass_count | INTEGER | Tasks that passed |

### evaluation_records

| Column | Type | Description |
|---|---|---|
| id | INTEGER (PK) | Auto-increment |
| run_id | TEXT (FK → evaluation_runs.id) | Run reference |
| task_id | TEXT | Task identifier |
| question | TEXT | Task question |
| tools_called | JSON | Full tool call trace |
| final_answer | TEXT | LLM answer |
| expected_answer | TEXT | Expected answer (if exact-match) |
| passed | BOOLEAN | Pass/fail |
| score | REAL | 0.0 – 1.0 |
| judge_rationale | TEXT | LLM-as-judge explanation |
| latency_ms | INTEGER | Total latency |
| created_at | DATETIME | Record time |

---

## Repository Interface

```python
from typing import Protocol
from datetime import datetime

class EnergyRepositoryProtocol(Protocol):
    async def get_buildings(self) -> list[Building]: ...
    async def get_building(self, building_id: str) -> Building | None: ...
    async def get_consumption(
        self,
        building_id: str,
        start: datetime,
        end: datetime,
        reading_type: str = "electricity",
    ) -> list[EnergyReading]: ...
    async def get_monthly_summary(
        self,
        building_id: str | None,
        year: int,
        month: int,
    ) -> list[MonthlySummary]: ...
    async def find_anomalies(
        self,
        building_id: str | None,
        threshold_stddev: float = 2.0,
    ) -> list[AnomalyRecord]: ...
```

---

## Migrations

All schema changes use Alembic:

```bash
# Create a new migration
alembic revision --autogenerate -m "add meter_id to energy_readings"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

Migration files live in `backend/alembic/versions/`.
Migration files are version-controlled and reviewed like application code.

---

## Seed Data

The local development database is seeded with synthetic energy data:

- 20 buildings
- 2 years of hourly electricity readings
- Known anomalies planted at specific dates (used to validate evaluation tasks)
- Gas and solar readings for a subset of buildings

Seed script: `scripts/seed.py`

The seed data is deterministic (fixed random seed) so evaluation expected answers
are stable across environments.

---

## PostgreSQL Compatibility Notes

When moving to PostgreSQL:
- `TEXT` columns work identically
- `JSON` columns work identically (PostgreSQL has native `JSONB` which is faster)
- `DATETIME` becomes `TIMESTAMP WITH TIME ZONE` — use timezone-aware Python datetimes
- Connection string changes from `sqlite+aiosqlite://` to `postgresql+asyncpg://`
- Alembic handles the migration; no application code changes required
