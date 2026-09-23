# Architecture

This document describes the system architecture of the AI MCP Data Platform.
It covers component design, data flow, and the rationale behind key decisions.

---

## 1. System Components

```
┌──────────────────────────────────────────────────────────────────────┐
│                          Client Layer                                 │
│   Browser ──► React SPA (TypeScript / Vite)                         │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ HTTPS / REST JSON
┌──────────────────────────────▼───────────────────────────────────────┐
│                     API Layer  (backend/app/)                         │
│   FastAPI — thin routing only; no business logic, no LangChain       │
│   ├── POST /api/v1/query                                             │
│   ├── GET  /api/v1/sessions                                          │
│   ├── GET  /api/v1/health                                            │
│   └── POST /api/v1/evaluations/run                                   │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ Python function calls
┌──────────────────────────────▼───────────────────────────────────────┐
│              Agent / Orchestration Layer  (backend/agent/)            │
│                                                                      │
│   AgentService     — entry point; manages sessions + invokes agent  │
│   AnalystAgent     — constructs + runs LangChain agent               │
│   EvaluationService — runs agent for evaluation tasks               │
│                                                                      │
│   LangChain lives here.  Specific implementation (AgentExecutor /   │
│   LangGraph / other) decided at implementation time.                 │
│                                                                      │
│   BaseChatModel (abstract, from langchain_core)                      │
│   ├── ChatBedrock  (production — via llm/factory.py)                │
│   └── FakeChatModel (tests — via llm/factory.py or direct inject)   │
│                                                                      │
│   Calls SessionService for conversation history (infrastructure).   │
│   Calls energy domain ONLY through MCP — never imports services/.   │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ MCP protocol (stdio / SSE)
┌──────────────────────────────▼───────────────────────────────────────┐
│                    MCP Server  (backend/mcp/)                         │
│   FastMCP — independently usable by any MCP-compatible client        │
│                                                                      │
│   Tools: list_buildings · get_building_consumption · compare_buildings│
│          get_monthly_summary · find_anomalies · get_schema           │
│          run_safe_query                                              │
│                                                                      │
│   Each tool calls Application Services — not the DB directly.       │
│   No LangChain dependency.                                           │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ Python function calls
┌──────────────────────────────▼───────────────────────────────────────┐
│               Application Service Layer  (backend/services/)          │
│                                                                      │
│   EnergyService    — energy analytics business logic                 │
│   SessionService   — conversation history management                 │
│                                                                      │
│   Pure Python. No LangChain. No FastMCP client. No LangSmith.       │
│   Usable standalone: by MCP tools, API routes, scripts, or tests.   │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ Python function calls
┌──────────────────────────────▼───────────────────────────────────────┐
│                  Repository Layer  (backend/data/)                    │
│   EnergyRepository · SessionRepository · EvalRepository              │
│   Pure Python Protocols + SQLAlchemy implementations.               │
│   No LangChain. No FastMCP. No agent.                               │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ SQLAlchemy (async)
┌──────────────────────────────▼───────────────────────────────────────┐
│                       Database Layer                                  │
│   SQLite (local dev)  /  PostgreSQL (production)                    │
│   Only DATABASE_URL changes between environments.                   │
└──────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────────┐
                    │  LangSmith  (optional, external)  │
                    │  Observes Agent/Orchestration     │
                    │  Layer when LANGSMITH_TRACING=true│
                    │  Zero impact when disabled.       │
                    └──────────────────────────────────┘
```

---

## 2. Data Flow

### Natural Language Query

```
User types question
        │
        ▼
React frontend
        │ POST /api/v1/query  { session_id, question }
        ▼
FastAPI route handler   (backend/app/)
        │
        ▼
AgentService.run(question, session_id)   (backend/agent/)
        │
        ├─► SessionService.get_history(session_id)   ← direct call (infrastructure)
        │           returns prior conversation turns
        │
        ├─► llm/factory.py → BaseChatModel
        │
        ├─► AnalystAgent constructed with:
        │       - BaseChatModel
        │       - MCP tools (as LangChain BaseTool instances)
        │       - conversation history
        │
        ├─► agent.invoke(question)   ← LangChain manages the loop
        │       │
        │       │  LangChain tool-calling loop:
        │       │
        │       ├─► LLM selects tool (e.g. get_monthly_summary)
        │       │
        │       ├─► MCP client calls FastMCP server tool
        │       │       │         (MCP protocol boundary)
        │       │       ▼
        │       │   FastMCP tool handler   (backend/mcp/)
        │       │       │
        │       │       ▼
        │       │   EnergyService.get_monthly_summary(...)   (backend/services/)
        │       │       │
        │       │       ▼
        │       │   EnergyRepository.query(...)   (backend/data/)
        │       │       │
        │       │       ▼
        │       │   SQLAlchemy → SQLite / PostgreSQL
        │       │       │
        │       │       ▼
        │       │   Result returned up the chain
        │       │
        │       ├─► Tool result returned to LangChain agent
        │       │
        │       └─► LLM produces final answer (loop repeats if needed)
        │
        │       ◄── LangSmith traces every LLM + tool call (if enabled)
        │
        ├─► agent returns final answer + tool call trace
        │
        ├─► SessionService.save_turn(...)   ← direct call (infrastructure)
        │
        ▼
FastAPI returns response to frontend
        │
        ▼
React renders answer
```

### Evaluation Flow

```
EvaluationTask definition (task_id, question, expected_answer)
        │
        ▼
EvaluationService.run_task(task)
        │
        │  Uses same AgentService.run() flow as above
        │  LangSmith dataset + evaluator used for agent evals (if enabled)
        │
        ▼
EvaluationRecord {
    task_id, model, provider,
    tools_called, tool_args, tool_results,
    final_answer, expected_answer,
    pass/fail, score, timestamp
}
        │
        ├─► JSONL log (always — local, no external dependency)
        └─► LangSmith experiment record (if enabled)
```

---

## 3. API Architecture

**Decision: FastAPI as a thin routing layer only.**

Routes do not contain business logic. They:
1. Parse and validate the request (Pydantic models)
2. Call a service
3. Return the service result

This means the services can be tested directly without HTTP, and a different
framework (e.g. Flask, gRPC) could replace FastAPI without touching business logic.

**Versioning:** All routes are under `/api/v1/`. When breaking changes are needed,
`/api/v2/` is added without removing v1 immediately.

**Authentication:** Not implemented in the initial version. The architecture uses
FastAPI middleware so auth can be added without changing route logic.

---

## 4. MCP Architecture

**Decision: MCP tools are thin adapters, not business logic containers.**

```
MCP Tool (FastMCP decorator)
    │  Validates input with Pydantic
    │  Calls service function
    │  Returns structured result
    ▼
Application Service (pure Python)
    │  Contains all business logic
    │  Calls repository
    │  Can be called by MCP tools, API routes, or tests directly
    ▼
Repository (abstract interface)
    │
    ▼
Database implementation
```

**Why FastMCP:** FastMCP provides a clean decorator-based API for defining MCP tools
in Python. The tools are registered with minimal boilerplate, and the server handles
the MCP protocol (stdio or SSE) without application code needing to know the wire format.

**Why MCP tools are NOT replaced by LangChain tools:** The MCP server is independently
usable by any MCP-compatible client, not just LangChain. It could be called by Claude
Desktop, another agent framework, or a future CLI tool. LangChain adapts MCP tools into
`BaseTool` instances as a client — it does not replace the server.

**MCP transport:** stdio for local development (subprocess), SSE for network
deployment. FastMCP supports both; the choice is configuration, not code change.

**Tool safety:** All MCP tools are read-only by design. The `run_safe_query` tool
runs queries through a SQL allowlist validator before execution. There is no MCP
tool that performs INSERT, UPDATE, or DELETE.

---

## 5. Database Architecture

**Decision: Repository pattern with async SQLAlchemy.**

```
Abstract interface (Python Protocol)
    EnergyRepositoryProtocol
        get_buildings() -> list[Building]
        get_consumption(building_id, start, end) -> list[ConsumptionRecord]
        ...

Concrete implementation
    SQLAlchemyEnergyRepository
        implements EnergyRepositoryProtocol
        uses async SQLAlchemy session

Test implementation
    FakeEnergyRepository
        implements EnergyRepositoryProtocol
        uses in-memory dict
```

**SQLite for local development** — zero-dependency, file-based, fast to seed.
**PostgreSQL for production** — the same SQLAlchemy models work without change;
only the connection URL and driver differ.

Schema migrations will use Alembic. Migration files are version-controlled.

See [docs/database.md](docs/database.md) for schema design.

---

## 6. Agent / Orchestration Layer and LLM Architecture

**Decision: LangChain lives in `backend/agent/` only. Application services are LangChain-free.**

```
backend/agent/          ← LangChain lives here
    AgentService        — public entry point (FastAPI calls this)
    AnalystAgent        — constructs and runs the LangChain agent
    EvaluationService   — runs AgentService for evaluation tasks
    mcp_tools.py        — loads FastMCP tools as LangChain BaseTool instances

backend/llm/
    factory.py          — ONLY file that imports langchain-aws / ChatBedrock
    fake.py             — FakeChatModel for tests

backend/services/       ← no LangChain imports
backend/mcp/            ← no LangChain imports
backend/data/           ← no LangChain imports
```

**LLM provider abstraction:**
```
llm/factory.py
    create_llm(settings) -> BaseChatModel
    ├── LLM_PROVIDER=bedrock  →  ChatBedrock  (from langchain-aws)
    └── LLM_PROVIDER=fake     →  FakeChatModel (custom scripted implementation)
```

`AgentService` accepts `BaseChatModel` (from `langchain_core`) as a constructor
parameter. The factory is called at application startup. In tests, `FakeChatModel`
is injected directly — the factory is never called.

**LangChain implementation choice deferred:**
The specific LangChain agent implementation — whether `AgentExecutor`,
`create_react_agent`, LangGraph, or another currently recommended pattern —
will be decided at implementation time by inspecting the current LangChain
and LangGraph APIs. The choice will be documented with rationale at that point.
Do not assume any specific API from this document.

**MCP adapter:**
The package and API for loading FastMCP tools as LangChain `BaseTool` instances
will be verified at implementation time. The package name and import path
documented here may not reflect the current state of the LangChain ecosystem.

**Why LangChain for agent orchestration:**
- Provides a tested tool-calling loop (avoids reimplementing from scratch)
- Zero-configuration LangSmith integration via env vars
- Active ecosystem for MCP integration
- `BaseChatModel` abstraction supports fake + real providers

**Why the agent layer is separate from application services:**
- `backend/services/` must be usable without LangChain installed
- MCP tool handlers must be testable without starting a LangChain agent
- Repository tests must have no LangChain dependency whatsoever
- The MCP server is a standalone service — any MCP-compatible client can use it

**How to replace LangChain:**
Only `backend/agent/` and `backend/llm/factory.py` change. Application services,
MCP server, repositories, and database are untouched. `FakeChatModel` is replaced
by a new fake for the replacement framework. `AnalystAgent` is replaced by a new
orchestrator that uses the same `SessionService` and MCP client.

See [docs/llm.md](docs/llm.md) for the provider interface, FakeChatModel, and LangSmith.

---

## 7. LangSmith Integration

**Decision: LangSmith for optional observability and agent evaluation.**

```
LangSmith (optional)
    ├── Automatic tracing of LangChain execution
    │   (every LLM call, tool call, chain step)
    │
    ├── Evaluation datasets
    │   (evaluation task inputs + expected outputs stored in LangSmith)
    │
    └── Experiment tracking
        (compare agent runs across model versions, prompts, tools)
```

**Why LangSmith:**
- Integrates with zero code changes — tracing is automatic when env vars are set
- Provides visual trace inspection (invaluable for debugging multi-step agent behavior)
- Supports offline evaluations using LangSmith datasets and evaluators
- Enables experiment comparison across model/prompt changes

**Why LangSmith is optional:**
- Not all environments have LangSmith access (CI, offline dev, contributors)
- The application works fully without it — structured JSON logging covers the essentials
- LangSmith is a paid service; development should not require it
- Automated tests must never depend on LangSmith connectivity

**Configuration:**
```bash
LANGSMITH_TRACING=true        # enable/disable all LangSmith calls
LANGSMITH_API_KEY=lsv2_...   # LangSmith API key
LANGSMITH_PROJECT=ai-mcp-data-platform  # project namespace
```

When `LANGSMITH_TRACING=false` (or the env var is absent):
- No network calls to LangSmith occur
- Local structured JSON logging works normally
- All tests pass without LangSmith credentials

How to replace LangSmith: The structured JSON logging already captures all
meaningful events. A different observability platform (Honeycomb, Datadog, a
custom dashboard) could consume those logs without any application code changes.

---

## 8. Evaluation Architecture

The evaluation system has two distinct layers serving different purposes.

### Layer 1: Application and MCP Tests

**What they test:** Deterministic behavior that does not require an LLM.

```
pytest (unit + integration)
    ├── MCP tool validation (schema, input/output contracts)
    ├── Database query correctness
    ├── Repository behavior
    ├── API endpoint behavior
    ├── SQL allowlist security
    └── Error handling
```

These tests run in CI on every PR. They use `FakeChatModel` and SQLite in-memory.
They are fast (< 1 second per test), offline, and deterministic.

### Layer 2: Agent Evaluations

**What they test:** LLM agent behavior — tool selection, multi-step reasoning,
answer quality, refusal of unsafe requests.

```
evaluations/ (pytest + optional LangSmith)
    ├── Offline evaluation (FakeChatModel — scripted responses)
    │   └── Verifies: evaluation framework records correctly, scoring works
    │
    └── Online evaluation (real LLM — Bedrock or other)
        ├── Local: JSONL output to data/evals/<run_id>.jsonl
        └── LangSmith: traces + experiment records (if enabled)
```

**Task definitions live in the repository** regardless of whether LangSmith is
used. This keeps the project reproducible without LangSmith access.

```
EvaluationTask
    id: str
    question: str
    expected_tools: list[str]
    expected_answer: str | None    # None = LLM-as-judge
    judge_rubric: str | None
    category: TaskCategory
    difficulty: Difficulty

EvaluationRecord
    task_id, question, model, provider
    tools_called: list[ToolCallRecord]
    final_answer, expected_answer
    passed: bool, score: float
    langsmith_run_id: str | None   # set if LangSmith was enabled
    latency_ms, input_tokens, output_tokens
```

See [docs/evaluations.md](docs/evaluations.md) for task definitions, the worked
example, and LangSmith integration details.

---

## 9. Logging Architecture

**Decision: Structured JSON logging throughout; LangSmith for agent-level tracing.**

Every log line is a JSON object with:
```json
{
  "timestamp": "2025-01-01T00:00:00Z",
  "level": "INFO",
  "service": "backend",
  "event": "tool_call",
  "tool": "get_building_consumption",
  "args": { "building_id": "B001", "start": "2024-12-01" },
  "duration_ms": 42,
  "session_id": "abc123"
}
```

Log categories:
- `query` — every user question and final answer
- `tool_call` — every MCP tool call with args, result, and duration
- `llm_call` — every LLM invocation with model, tokens, latency
- `error` — all exceptions with stack trace
- `eval` — every evaluation task execution and result

**Relationship to LangSmith:** Structured logs capture application-level events.
LangSmith captures the agent execution graph (steps, reasoning, tool use chains).
They are complementary — logs work without LangSmith; LangSmith adds richer
agent tracing on top.

**Local:** logs to stdout, captured by Docker Compose.
**AWS:** CloudWatch Logs agent collects stdout from ECS containers.

No secrets, PII, or raw SQL query results are logged at INFO level.

---

## 10. Testing Strategy

```
Unit tests (fast, no I/O, no LLM)
    ├── Application service logic with FakeRepository (no LangChain needed)
    ├── Agent layer logic with FakeChatModel + FakeMCPTools
    ├── SQL validator (allowlist)
    └── Pydantic model validation

Integration tests (real DB, no network, no real LLM)
    ├── Repository against SQLite in-memory
    ├── API routes against test FastAPI client
    └── MCP tool handlers against real services + SQLite

Agent evaluation tests — offline (deterministic)
    ├── All evaluation tasks against FakeChatModel
    └── Verify evaluation recording, scoring, JSONL output

Agent evaluation tests — online (requires LLM + optional LangSmith)
    └── Full evaluation suite against real model (run manually or scheduled)

MCP contract tests
    └── Tool schemas validated against FastMCP registration
```

**No mocked databases in integration tests.** SQLite in-memory is fast enough
and catches real query bugs that mocks would hide.

**No real LLM calls in unit or integration tests.** `FakeChatModel` handles all
LLM interactions in automated tests. This keeps CI fast, free, and offline.

See [docs/testing.md](docs/testing.md).

---

## 11. Local Docker Architecture

```
docker-compose.yml
    ├── backend         Python FastAPI + MCP server
    │   └── mounts: ./backend → /app
    ├── frontend        React dev server (Vite)
    │   └── mounts: ./frontend → /app
    └── (no separate DB container — SQLite is file-based)

Volumes:
    ./data/db.sqlite    ← persisted SQLite database
    ./data/logs/        ← structured log output
    ./data/evals/       ← evaluation JSONL results
```

Single `docker compose up` starts the entire local stack.
Hot reload is enabled for both backend (uvicorn --reload) and frontend (Vite HMR).
LangSmith is optional — set env vars in `.env` to enable.

---

## 12. Future AWS Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        AWS Region                        │
│                                                         │
│   Route 53 → CloudFront → S3 (React static build)      │
│                                                         │
│   ALB → ECS Fargate (backend container)                 │
│              │                                          │
│              ├─► RDS PostgreSQL (Multi-AZ)              │
│              ├─► AWS Bedrock (Claude 3 via LangChain)   │
│              └─► CloudWatch Logs                        │
│                                                         │
│   ECR  — container image registry                       │
│   Secrets Manager — DB credentials, LangSmith API key  │
│   IAM  — task role with Bedrock + RDS permissions       │
└─────────────────────────────────────────────────────────┘
```

**Migration path from local to AWS:**
1. Replace `DATABASE_URL=sqlite:///./data/db.sqlite` with RDS PostgreSQL URL (env var only)
2. Replace `LLM_PROVIDER=fake` with `LLM_PROVIDER=bedrock` (env var only)
3. Optionally set `LANGSMITH_TRACING=true` with key from Secrets Manager
4. Build Docker images, push to ECR
5. Deploy ECS task definition referencing ECR images
6. Static frontend build → S3 + CloudFront

No code changes are required between local and AWS — only environment variables differ.

---

## Key Architectural Decisions Summary

| Decision | Choice | Rationale |
|---|---|---|
| Service layer decoupled from FastAPI | Yes | Testability, replaceability |
| Repository pattern | Yes | Swap SQLite → PostgreSQL without logic changes |
| Agent layer separate from application services | Yes | Services usable without LangChain; MCP server independently testable |
| LangChain confined to `backend/agent/` | Yes | Application services, MCP server, repositories have zero LangChain dependency |
| LangChain implementation choice deferred | Yes | AgentExecutor vs. LangGraph decided at implementation time against current APIs |
| LangChain for agent orchestration | Yes | Tested tool-calling loop, LangSmith integration, MCP adapter |
| Factory pattern for LLM providers | Yes | Provider-specific imports isolated to `backend/llm/factory.py` |
| `BaseChatModel` as abstraction | Yes | LangChain standard; enables fake + real providers |
| MCP tools stay on FastMCP server | Yes | Server usable by any MCP client, not just LangChain |
| LangSmith optional | Yes | Not all environments have access; local logging is sufficient |
| SQLite for local dev | Yes | Zero ops overhead, fast seeding |
| Async SQLAlchemy | Yes | Required for FastAPI async routes |
| Structured JSON logging | Yes | Machine-parseable, CloudWatch compatible |
| Two-layer evaluation system | Yes | App/MCP tests are deterministic; agent evals measure LLM quality |
| Read-only MCP tools | Yes | Safety-by-design, no accidental writes |
| Alembic migrations | Yes | Version-controlled schema changes |
| FakeChatModel in all automated tests | Yes | Deterministic, offline, free |
