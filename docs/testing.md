# Testing Strategy

---

## Principles

1. **Tests must be deterministic.** No flakiness. No random failures.
2. **Unit tests must be fast.** No network calls. No database I/O. Target < 1ms per test.
3. **Integration tests use real databases.** SQLite in-memory — not mocked sessions.
4. **No real LLM calls in automated tests.** All LLM interactions use `FakeChatModel`.
5. **LangSmith is always disabled in tests.** `LANGSMITH_TRACING=false` in `conftest.py`.
6. **Tests are first-class code.** Unreadable tests are a bug.
7. **A failing test is a blocker.** Nothing merges with a failing test.

---

## Test Pyramid

```
          ┌──────────────────────────────────┐
          │  Agent Evaluations (online)       │  (real LLM, optional LangSmith)
          │  Runs manually / on schedule      │  NOT in CI
          └──────────────┬───────────────────┘
               ┌─────────▼──────────────────────┐
               │  Agent Evaluations (offline)    │  (FakeChatModel)
               │  Verify eval framework works    │  In CI
               └─────────┬──────────────────────┘
          ┌───────────────▼──────────────────────────┐
          │         Integration tests                 │  (API, DB, MCP tools)
          │  FakeChatModel + SQLite in-memory         │  In CI
          └───────────────┬──────────────────────────┘
     ┌─────────────────────▼────────────────────────────┐
     │                  Unit tests                       │  (services, validators)
     │  FakeChatModel + FakeRepository, no I/O           │  In CI
     └──────────────────────────────────────────────────┘
```

The two types of agent evaluation are kept separate because online evaluations
are slow, costly, and require AWS credentials. They run on demand, not in CI.

---

## Backend Tests

### Location

```
backend/tests/
├── unit/
│   ├── services/         # Service layer tests (FakeRepo + FakeChatModel)
│   ├── validators/       # SQL allowlist validator tests
│   ├── models/           # Pydantic model validation tests
│   └── llm/              # FakeChatModel behavior tests
├── integration/
│   ├── api/              # FastAPI route tests (TestClient + SQLite in-memory)
│   ├── repositories/     # Repository tests (SQLite in-memory)
│   └── mcp/              # MCP tool tests (real tools + real services + SQLite)
└── conftest.py           # Shared fixtures; sets LANGSMITH_TRACING=false
```

### Running

```bash
cd backend

# All tests
pytest

# Unit only
pytest tests/unit/ -v

# Integration only
pytest tests/integration/ -v

# Specific file
pytest tests/unit/services/test_query_service.py -v

# With coverage
pytest --cov=app --cov-report=term-missing

# Fast fail
pytest -x
```

---

## conftest.py (Critical)

The shared `conftest.py` must disable LangSmith unconditionally:

```python
# backend/tests/conftest.py
import os
import pytest

# Disable LangSmith for all tests — no network calls, no API key required
os.environ["LANGSMITH_TRACING"] = "false"
```

This must be the first thing in conftest.py. No test should ever require
LangSmith connectivity.

---

## Unit Test Patterns

There are two distinct kinds of unit tests. Application service tests need no
LangChain. Agent layer tests use `FakeChatModel`.

### Application service test (no LangChain)

```python
# tests/unit/services/test_energy_service.py
import pytest
from backend.services.energy_service import EnergyService
from backend.data.fake import FakeEnergyRepository

@pytest.fixture
def energy_service():
    return EnergyService(repo=FakeEnergyRepository(seed_data=SEED_BUILDINGS))

async def test_monthly_summary_returns_all_buildings(energy_service):
    summaries = await energy_service.get_monthly_summary(
        building_id=None,
        start_year_month="2024-07",
        end_year_month="2024-08",
    )
    assert len(summaries) == 20
    assert all(s.total_kwh >= 0 for s in summaries)
```

No LangChain import. No `FakeChatModel`. Tests the business logic in isolation.

### Agent layer test (FakeChatModel injected)

```python
# tests/unit/agent/test_agent_service.py
import pytest
from langchain_core.messages import ToolCall
from backend.llm.fake import FakeChatModel, ScriptedResponse
from backend.agent.agent_service import AgentService
from backend.agent.analyst_agent import AnalystAgent
from backend.agent.mcp_tools import FakeMCPTools
from backend.services.session_service import SessionService
from backend.data.fake import FakeSessionRepository

@pytest.fixture
def agent_service():
    fake_llm = FakeChatModel(script=[
        ScriptedResponse(
            assert_input_contains="largest increase",
            tool_calls=[ToolCall(
                name="get_monthly_summary",
                args={"start_year_month": "2024-07", "end_year_month": "2024-08"},
                id="call_1",
            )],
        ),
        ScriptedResponse(
            content="Building B007 had the largest increase, rising from "
                    "9,200 kWh in July to 14,291 kWh in August (+55%).",
        ),
    ])
    return AgentService(
        llm=fake_llm,
        session_service=SessionService(repo=FakeSessionRepository()),
        analyst_agent=AnalystAgent(
            llm=fake_llm,
            tools=FakeMCPTools(tool_results={
                "get_monthly_summary": {"summaries": [
                    {"building_id": "B007", "year_month": "2024-07", "total_kwh": 9200.0},
                    {"building_id": "B007", "year_month": "2024-08", "total_kwh": 14291.0},
                ]},
            }),
        ),
    )

async def test_handles_trend_question(agent_service):
    result = await agent_service.run(
        question="Which building had the largest increase in consumption from July to August?",
        session_id=None,
    )
    assert "B007" in result.answer
    assert result.tools_used[0].tool == "get_monthly_summary"

async def test_saves_session_turn(agent_service):
    result = await agent_service.run(
        question="Which building had the largest increase?",
        session_id="sess_001",
    )
    assert result.session_id == "sess_001"
```

---

## Integration Test Patterns

### API route test

```python
# tests/integration/api/test_query_endpoint.py
import pytest
from httpx import AsyncClient
from backend.llm.fake import FakeChatModel, ScriptedResponse
from backend.app.main import create_app

@pytest.fixture
async def client(seeded_db):
    fake_llm = FakeChatModel(script=[
        ScriptedResponse(content="There are 20 buildings in the dataset."),
    ])
    app = create_app(db_url="sqlite+aiosqlite:///:memory:", llm=fake_llm)
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c

async def test_query_endpoint_returns_answer(client):
    response = await client.post("/api/v1/query", json={
        "question": "How many buildings are there?"
    })
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "session_id" in data
    assert isinstance(data["tools_used"], list)

async def test_query_creates_session(client):
    r1 = await client.post("/api/v1/query", json={"question": "Question 1"})
    session_id = r1.json()["session_id"]
    r2 = await client.post("/api/v1/query", json={
        "question": "Question 2", "session_id": session_id
    })
    assert r2.json()["session_id"] == session_id
```

### Repository test

```python
# tests/integration/repositories/test_energy_repository.py
async def test_get_buildings_returns_seeded_buildings(repo, seeded_data):
    buildings = await repo.get_buildings()
    assert len(buildings) == 20
    assert all(b.id.startswith("B") for b in buildings)

async def test_get_consumption_filters_by_date(repo, seeded_data):
    from datetime import datetime
    records = await repo.get_consumption(
        building_id="B007",
        start=datetime(2024, 7, 1),
        end=datetime(2024, 7, 31),
    )
    assert len(records) > 0
    assert all(r.building_id == "B007" for r in records)
```

---

## MCP Contract Tests

These tests verify that:
1. Every tool in `docs/mcp.md` is registered with FastMCP
2. Every registered tool accepts valid inputs without error
3. Every registered tool rejects invalid inputs with a structured error
4. Tool schemas have not silently changed

```python
# tests/integration/mcp/test_tool_contracts.py
async def test_all_documented_tools_are_registered(mcp_server):
    tools = await mcp_server.list_tools()
    tool_names = {t.name for t in tools}
    expected = {
        "list_buildings", "get_building_consumption", "compare_buildings",
        "get_monthly_summary", "find_anomalies", "get_schema", "run_safe_query",
    }
    assert expected == tool_names

async def test_get_monthly_summary_valid_input(mcp_server, seeded_db):
    result = await mcp_server.call_tool("get_monthly_summary", {
        "start_year_month": "2024-07",
        "end_year_month": "2024-08",
    })
    assert "summaries" in result
    assert isinstance(result["summaries"], list)

async def test_run_safe_query_rejects_write(mcp_server):
    result = await mcp_server.call_tool("run_safe_query", {
        "query": "DELETE FROM energy_readings WHERE building_id = 'B001'",
        "params": {},
    })
    assert "error" in result
    assert "not allowed" in result["error"].lower()
```

---

## Evaluation Offline Tests

These run in CI. They verify the evaluation framework structure using
`FakeChatModel` — they do NOT test agent answer quality.

```python
# evaluations/tests/test_task_july_august.py
from backend.llm.fake import FakeChatModel, ScriptedResponse
from langchain_core.messages import ToolCall
from evaluations.tasks.task_009 import TASK_009
from evaluations.runner import EvaluationRunner

async def test_task_009_records_correctly():
    """Offline: verify evaluation framework produces a correctly-structured record."""
    fake_llm = FakeChatModel(script=[
        ScriptedResponse(tool_calls=[ToolCall(
            name="get_monthly_summary",
            args={"start_year_month": "2024-07", "end_year_month": "2024-08"},
            id="call_1",
        )]),
        ScriptedResponse(content="Building B007 had the largest increase."),
    ])

    runner = EvaluationRunner(llm=fake_llm, db_url="sqlite+aiosqlite:///:memory:")
    record = await runner.run_task(TASK_009)

    assert record.task_id == "TASK-009"
    assert len(record.tool_calls) == 1
    assert record.tool_calls[0].tool_name == "get_monthly_summary"
    assert record.final_answer != ""
    assert record.langsmith_run_id is None  # LangSmith disabled in tests
```

---

## Frontend Tests

```
frontend/src/
├── components/
│   └── *.test.tsx     # Component tests (vitest + testing-library)
├── hooks/
│   └── *.test.ts      # Custom hook tests
└── api/
    └── *.test.ts      # API client tests (msw mocking)
```

```bash
cd frontend && npm run test
```

---

## CI Checks (Planned)

GitHub Actions runs on every PR:

```yaml
- LANGSMITH_TRACING=false (environment variable — always set)
- ruff check backend/
- ruff format --check backend/
- mypy backend/
- pytest backend/tests/ --cov --cov-fail-under=80
- pytest evaluations/tests/ (offline only, FakeChatModel)
- eslint frontend/src/
- tsc --noEmit
- npm run test (frontend)
```

Online evaluations (real LLM + optional LangSmith) are never run in CI.
They run manually or on a schedule with explicit credentials.

---

## Test Coverage Targets

| Component | Target |
|---|---|
| Services | 90%+ |
| Repositories | 85%+ |
| API routes | 80%+ |
| MCP tools | 85%+ |
| LLM factory + FakeChatModel | 90%+ |
| SQL allowlist validator | 100% |
| Evaluation framework (offline) | 90%+ |
