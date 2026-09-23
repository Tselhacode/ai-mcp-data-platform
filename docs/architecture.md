# Architecture Deep-Dive

This document expands on the high-level architecture in [ARCHITECTURE.md](../ARCHITECTURE.md).
It is the reference for developers working on specific components.

---

## Component Inventory

| Component | Location | Technology | Responsibility |
|---|---|---|---|
| React SPA | `frontend/` | React, TypeScript, Vite | User interface, conversation UI |
| FastAPI app | `backend/app/` | FastAPI, Pydantic | HTTP API, request routing — no LangChain |
| Agent service | `backend/agent/` | LangChain | Orchestration entry point; wraps LangChain agent |
| Analyst agent | `backend/agent/` | LangChain (impl TBD) | LangChain tool-calling agent |
| MCP tool loader | `backend/agent/mcp_tools.py` | LangChain MCP adapter | Loads FastMCP tools as `BaseTool` instances |
| LLM factory | `backend/llm/factory.py` | langchain-aws + langchain-core | `BaseChatModel` construction — only LangChain provider import |
| MCP server | `backend/mcp/` | FastMCP | Tool interface — independently usable; no LangChain |
| Application services | `backend/services/` | Pure Python | Business logic — no LangChain, no FastMCP client |
| Repositories | `backend/data/` | SQLAlchemy | Data access abstraction — no LangChain |
| Evaluations | `evaluations/` | pytest, Python | LLM quality measurement |
| Scripts | `scripts/` | Python | Seeding, migrations, utilities |
| Docker config | `docker/` | Docker Compose | Container orchestration |
| LangSmith | external | LangSmith SDK | Optional: agent tracing + eval datasets |

---

## API Endpoints (Planned)

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/query` | Submit a natural-language question |
| GET | `/api/v1/sessions` | List conversation sessions |
| GET | `/api/v1/sessions/{id}` | Get session with history |
| DELETE | `/api/v1/sessions/{id}` | Clear a session |
| GET | `/api/v1/health` | Liveness probe |
| GET | `/api/v1/ready` | Readiness probe (DB + LLM connectivity) |
| POST | `/api/v1/evaluations/run` | Trigger an evaluation run (internal) |
| GET | `/api/v1/evaluations` | List evaluation runs |
| GET | `/api/v1/evaluations/{run_id}` | Get evaluation run detail |

---

## Request / Response Models

### POST /api/v1/query

Request:
```json
{
  "session_id": "string | null",
  "question": "Which buildings used the most energy last month?"
}
```

Response:
```json
{
  "session_id": "abc123",
  "answer": "Building B007 had the highest consumption...",
  "tools_used": [
    {
      "tool": "get_monthly_summary",
      "args": { "month": "2024-12" },
      "result_summary": "Returned 42 building records"
    }
  ],
  "latency_ms": 1240
}
```

---

## Service Layer Contracts

### AgentService  (`backend/agent/agent_service.py`)

The public entry point for AI-driven queries. FastAPI calls this.
Contains no business logic — coordinates session management and agent invocation.

```python
from langchain_core.language_models.base import BaseChatModel

class AgentService:
    def __init__(
        self,
        llm: BaseChatModel,              # injected: ChatBedrock or FakeChatModel
        session_service: SessionService, # from backend/services/ — no LangChain
        analyst_agent: AnalystAgent,     # from backend/agent/ — wraps LangChain
    ): ...

    async def run(
        self,
        question: str,
        session_id: str | None,
    ) -> AgentResult: ...
```

`AgentService` is the only component in `backend/services/`-adjacent code that
imports `BaseChatModel`. Application services (`backend/services/`) have no
LangChain imports at all. The factory in `backend/llm/factory.py` is the only
place that imports `ChatBedrock` or any provider-specific LangChain package.

### EnergyService  (`backend/services/energy_service.py`)

Pure Python. Called by MCP tool handlers, not by the agent directly.

```python
class EnergyService:
    def __init__(self, repo: EnergyRepositoryProtocol): ...

    async def get_monthly_summary(
        self,
        building_id: str | None,
        start_year_month: str,
        end_year_month: str,
    ) -> list[MonthlySummary]: ...
    # ... other methods
```

No LangChain. No FastMCP client. Testable with `FakeEnergyRepository` alone.

### EvaluationService  (`backend/agent/evaluation_service.py`)

Lives in `backend/agent/` because it runs the LangChain agent to evaluate tasks.

```python
class EvaluationService:
    def __init__(
        self,
        agent_service: AgentService,
        eval_repo: EvalRepositoryProtocol,
    ): ...

    async def run_task(
        self,
        task: EvaluationTask,
    ) -> EvaluationRecord: ...

    async def run_suite(
        self,
        tasks: list[EvaluationTask],
        run_id: str | None = None,
    ) -> EvaluationRun: ...
```

---

## Configuration

All runtime configuration comes from environment variables (no hard-coded values).

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/db.sqlite` | Database connection string |
| `LLM_PROVIDER` | `fake` | `bedrock` or `fake` |
| `LLM_MODEL` | `anthropic.claude-3-5-sonnet-20241022-v2:0` | Bedrock model ID |
| `LLM_MAX_TOKENS` | `4096` | Max tokens per LLM response |
| `LLM_MAX_ITERATIONS` | `10` | Max agent tool-calling loop iterations |
| `AWS_REGION` | `us-east-1` | AWS region for Bedrock |
| `LOG_LEVEL` | `INFO` | Python log level |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `sse` |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins |
| `LANGSMITH_TRACING` | `false` | Enable LangSmith tracing (`true`/`false`) |
| `LANGSMITH_API_KEY` | *(unset)* | LangSmith API key (required if tracing=true) |
| `LANGSMITH_PROJECT` | `ai-mcp-data-platform` | LangSmith project namespace |

---

## Dependency Injection

Services are composed at application startup using a dependency injection container
(using FastAPI's `Depends()` system for API routes, and direct construction for tests).

```python
# ── Application service test (no LangChain needed) ──────────────────
from backend.services.energy_service import EnergyService
from backend.data.fake import FakeEnergyRepository

energy_service = EnergyService(repo=FakeEnergyRepository(seed_data))
# Test directly — no agent, no LangChain, no MCP

# ── Agent layer test (FakeChatModel injected) ─────────────────────────
from backend.llm.fake import FakeChatModel, ScriptedResponse
from backend.agent.agent_service import AgentService
from backend.agent.analyst_agent import AnalystAgent
from backend.agent.mcp_tools import FakeMCPTools
from backend.services.session_service import SessionService
from backend.data.fake import FakeSessionRepository

agent_service = AgentService(
    llm=FakeChatModel(script=[ScriptedResponse(content="42 buildings.")]),
    session_service=SessionService(repo=FakeSessionRepository()),
    analyst_agent=AnalystAgent(
        llm=fake_llm,
        tools=FakeMCPTools(tool_results={"list_buildings": {"buildings": []}}),
    ),
)

# ── Production (FastAPI dependency) ───────────────────────────────────
def get_agent_service(
    db: AsyncSession = Depends(get_db),
    llm: BaseChatModel = Depends(get_llm),             # from llm/factory.py
    mcp_tools: list[BaseTool] = Depends(get_mcp_tools), # from agent/mcp_tools.py
) -> AgentService:
    session_service = SessionService(repo=SQLAlchemySessionRepository(db))
    analyst_agent = AnalystAgent(llm=llm, tools=mcp_tools)
    return AgentService(
        llm=llm,
        session_service=session_service,
        analyst_agent=analyst_agent,
    )
```

Application service tests inject `FakeEnergyRepository` only — no LangChain.
Agent layer tests inject `FakeChatModel` — no real LLM, no real MCP calls.

---

## Error Handling Strategy

- **Validation errors (4xx):** FastAPI/Pydantic handles automatically; return structured `{"error": "message"}` JSON
- **LLM provider errors:** Caught in `AgentService`/`AnalystAgent`, logged, return user-friendly message
- **Database errors:** Caught in repositories, logged, re-raised as domain exceptions
- **MCP tool errors:** Returned to the LLM as a tool error result (not raised); LLM decides how to handle
- **Unexpected errors (5xx):** Caught at FastAPI middleware level, logged with full stack trace, return generic 500

Internal error details are never returned to the client.
