# AI MCP Data Platform

A full-stack AI Data Analyst application demonstrating production-grade AI engineering:
MCP server engineering, LLM/tool interaction, SQL analytics, evaluation-driven development,
and harness engineering.

> **Status:** Core implementation complete. Backend API, agent layer, MCP tools,
> React frontend, Docker setup, and CI pipeline are implemented and tested.

---

## Purpose

This platform allows an LLM agent to answer natural-language questions about an energy
analytics database by invoking tools exposed through an MCP server.

**Example interaction:**

> User: "Which buildings had the largest increase in electricity consumption last month?"

The LLM agent selects the appropriate MCP tools, queries the database, reasons over the
results, and returns a grounded answer — without requiring the user to know SQL.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        React Frontend                        │
│                  (TypeScript / Vite)                         │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP / REST
┌───────────────────────────▼─────────────────────────────────┐
│                     FastAPI Backend                          │
│                                                              │
│   Application Services                                       │
│   └── LangChain Agent (tool-calling loop)                   │
│           └── BaseChatModel abstraction                      │
│               ├── ChatBedrock (production)                   │
│               └── FakeChatModel (tests)                      │
│                                                              │
│   Repository Layer → SQLAlchemy → SQLite / PostgreSQL        │
└───────────────────────────┬─────────────────────────────────┘
                            │ MCP protocol
┌───────────────────────────▼─────────────────────────────────┐
│                     MCP Server (FastMCP)                     │
│              Tools → Application Services → DB               │
└─────────────────────────────────────────────────────────────┘

                     ┌───────────────────┐
                     │     LangSmith     │  ← optional
                     │  (agent tracing,  │
                     │   eval datasets)  │
                     └───────────────────┘
```

See [ARCHITECTURE.md](ARCHITECTURE.md) and [docs/architecture.md](docs/architecture.md)
for detailed component diagrams and architectural decision rationale.

---

## Technology Stack

| Layer             | Technology                                          |
|-------------------|-----------------------------------------------------|
| Frontend          | React, TypeScript, Vite                             |
| Backend API       | Python, FastAPI, Pydantic v2                        |
| Agent framework   | LangChain (agent loop, tool calling, MCP adapter)   |
| LLM observability | LangSmith (optional — tracing, eval datasets)       |
| ORM               | SQLAlchemy 2.x (async)                              |
| MCP server        | FastMCP                                             |
| LLM provider      | AWS Bedrock (Claude 3) via `langchain-aws`          |
| LLM abstraction   | `BaseChatModel` (provider-agnostic via factory)     |
| Database          | SQLite (local dev) / PostgreSQL (production)        |
| Testing           | pytest, pytest-asyncio, vitest                      |
| Linting           | ruff, mypy, eslint                                  |
| Formatting        | ruff format, prettier                               |
| Containers        | Docker, Docker Compose                              |
| CI/CD             | GitHub Actions                                      |
| AWS (future)      | ECS / RDS / Bedrock / CloudWatch                    |

---

## Capabilities

- **Natural language analytics** -- Ask questions about energy consumption data in plain English
- **MCP tool execution** -- LLM selects and calls tools to query the database
- **Multi-step reasoning** -- Agent chains multiple tool calls to answer complex questions
- **Conversation history** -- Session context maintained across turns
- **Evaluation harness** -- Automated LLM evaluation against predefined analytical tasks
- **Observability** -- Structured JSON logging, tool call tracing, request correlation IDs
- **Safe-by-default LLM** -- Read-only MCP tools, SQL allowlist validation

---

## MCP Tools

| Tool                       | Description                                              |
|----------------------------|----------------------------------------------------------|
| `list_tables`              | Return all table names in the database                   |
| `describe_table`           | Return column details for a given table                  |
| `get_building_summary`     | Return consumption summary for a building over a range   |
| `get_consumption_trend`    | Return daily consumption trend for a building            |
| `run_readonly_query`       | Execute a validated read-only SQL query                  |

See [docs/mcp.md](docs/mcp.md) for detailed tool specifications.

---

## Evaluation Approach

The evaluation system has two complementary layers:

**Layer 1 — Application and MCP tests** (always run in CI):
- MCP tool contracts, database queries, API contracts, security rules
- Uses `FakeChatModel` — no LLM API cost, runs offline

**Layer 2 — Agent evaluations** (run manually or on schedule):
- LLM agent quality: tool selection, multi-step reasoning, answer accuracy
- Task definitions version-controlled in `evaluations/tasks/`
- Results recorded locally; optionally traced in LangSmith

Ten evaluation tasks are implemented (`evaluations/tasks/task_001.py` through `task_010.py`):

| Task | Question | Key signal |
|------|----------|------------|
| TASK-001 | "How many buildings?" | `list_tables` → "20" |
| TASK-002 | "Which had highest consumption?" | `run_readonly_query` → "B007" |
| TASK-003 | "B007 total in July 2024?" | `get_building_summary` |
| TASK-004 | "Largest July→August increase?" | `get_consumption_trend` → "B007" |
| TASK-005 | "B007 monthly trend Jan–Jun?" | `get_consumption_trend` |
| TASK-006 | "Anomalous readings in Nov 2024?" | `run_readonly_query` → "B003" |
| TASK-007 | "Average Q1 2024 across all?" | `run_readonly_query` |
| TASK-008 | "Compare B001 and B007 in July?" | `get_building_summary` |
| TASK-009 | "B007 % increase July→August?" | `get_consumption_trend` → ~55% |
| TASK-010 | "Which buildings have gas?" | `run_readonly_query` → "B001" |

See [docs/evaluations.md](docs/evaluations.md) for full task definitions and
the TASK-009 worked example.

---

## LangSmith

[LangSmith](https://smith.langchain.com) provides optional observability for the
LangChain agent:

- **Agent tracing** — visual inspection of every LLM call and tool invocation
- **Evaluation datasets** — store task inputs + expected outputs in LangSmith
- **Experiment tracking** — compare agent quality across model/prompt changes

LangSmith is **optional**. The application runs fully without it. Tests never
require it. To enable:

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=ai-mcp-data-platform
```

To disable (default): leave `LANGSMITH_TRACING` unset or set to `false`.

---

## Harness Engineering

This repository is designed as a safe, efficient environment for AI coding agents.
It distinguishes two feedback loops:

**Coding agent harness** — controls Claude Code behavior:
- **CLAUDE.md** / **AGENTS.md** — rules for AI coding sessions
- **Claude Hooks** — linting, type checking, tests triggered on every edit
- **Automated tests** — unit, integration, MCP contract, security

**Application agent evaluation** — measures the LangChain agent quality:
- **Evaluation tasks** — predefined analytical tasks with expected answers
- **LangSmith** — optional agent tracing and experiment tracking
- **JSONL output** — local evaluation records independent of LangSmith

See [docs/harness-engineering.md](docs/harness-engineering.md).

---

## Local Development Overview

> Full instructions: [docs/local-development.md](docs/local-development.md)

```bash
# Clone
git clone https://github.com/Tselhacode/ai-mcp-data-platform.git
cd ai-mcp-data-platform

# Start all services
docker compose up

# Backend only
cd backend && uv run uvicorn app.main:app --reload

# Frontend only
cd frontend && npm run dev

# Run evaluations
cd evaluations && uv run pytest
```

---

## Testing Overview

| Test type           | Location                 | Runner   |
|---------------------|--------------------------|----------|
| Backend unit        | `backend/tests/unit/`    | pytest   |
| Backend integration | `backend/tests/integration/` | pytest |
| Backend E2E         | `backend/tests/e2e/`     | pytest   |
| MCP contract        | `backend/tests/mcp/`     | pytest   |
| Frontend unit       | `frontend/src/`          | vitest   |
| Evaluations         | `evaluations/`           | pytest   |

See [docs/testing.md](docs/testing.md).

---

## Future AWS Deployment

The local architecture is designed for straightforward migration to AWS:

| Local             | AWS equivalent      |
|-------------------|---------------------|
| SQLite            | RDS PostgreSQL      |
| Docker Compose    | ECS Fargate         |
| Local LLM fake    | AWS Bedrock (Claude)|
| stdout logs       | CloudWatch Logs     |
| Local MCP server  | ECS sidecar / Lambda|

See [docs/deployment.md](docs/deployment.md).

---

## Project Structure

```
ai-mcp-data-platform/
├── README.md
├── CLAUDE.md              # Rules for Claude Code sessions
├── AGENTS.md              # Rules for all AI coding agents
├── ARCHITECTURE.md        # Architecture decisions and diagrams
├── CONTRIBUTING.md        # Contribution guidelines
├── docs/                  # Deep-dive documentation
│   ├── architecture.md
│   ├── database.md
│   ├── mcp.md
│   ├── llm.md
│   ├── evaluations.md
│   ├── harness-engineering.md
│   ├── local-development.md
│   ├── deployment.md
│   └── testing.md
├── backend/               # Python FastAPI application + MCP server
├── frontend/              # React TypeScript application
├── evaluations/           # LLM evaluation framework
├── scripts/               # Developer utility scripts
└── docker/                # Docker and Compose configuration
```

---

## How a Request Flows Through the System

```
User types:  "Which buildings had the largest electricity increase last month?"
     │
     ▼  HTTP POST /api/v1/query
FastAPI route (thin — no business logic)
     │
     ▼  Python call
AgentService  ← loads session history from database
     │
     ▼  Python call
AnalystAgent  (LangChain / LangGraph create_react_agent)
     │
     │  LLM (ChatBedrock or FakeChatModel) decides which MCP tools to call
     │
     ▼  MCP protocol (in-process via fastmcp.Client)
FastMCP server
     ├── list_tables                → discovers available tables
     ├── describe_table             → understands schema
     └── get_consumption_trend      → fetches aggregated kWh by period
          │
          ▼  Python call
     EnergyService (pure Python, no LangChain)
          │
          ▼  SQLAlchemy async query
     SQLite / PostgreSQL
          │
          ▼  rows
     Back through the chain → LLM synthesises final answer
     │
     ▼  JSON response
React frontend displays answer + tool activity panel
```

LangSmith (optional) records the full trace — every LLM call, tool invocation,
and token count — for observability and experiment tracking.

---

## Engineering Highlights

| Capability | Where it lives |
|---|---|
| **FastMCP server** — 5 read-only tools, Pydantic I/O, SQL allowlist | `backend/mcp/` |
| **LangChain agent** — LangGraph ReAct loop, tool-calling, conversation history | `backend/agent/` |
| **Provider abstraction** — swap Bedrock ↔ FakeChatModel without touching agent code | `backend/llm/factory.py` |
| **LangSmith** — optional tracing + eval datasets, zero-config disable | `app/main.py`, `evaluations/` |
| **SQL safety** — `sqlglot` validates every LLM-generated query; only SELECT allowed | `mcp/tools/query_tools.py` |
| **Evaluation framework** — 10 tasks, deterministic scoring, offline + real-LLM modes | `evaluations/` |
| **Architecture boundary enforcement** — `check_architecture.py` fails CI on violations | `scripts/check_architecture.py` |
| **Secrets detection** — `check_secrets.py` scans all tracked files in CI | `scripts/check_secrets.py` |
| **Claude Code harness** — CLAUDE.md rules + post-edit ruff hooks | `CLAUDE.md`, `.claude/` |
| **84 MCP contract tests** — tool schema, security, error paths | `backend/tests/integration/mcp/` |
| **Full test pyramid** — 166 backend tests (unit + integration + E2E) + 16 frontend tests | `backend/tests/`, `frontend/src/` |
| **Docker** — multi-stage backend image, nginx frontend, single `docker compose up` | `docker/`, `docker-compose.yml` |
| **CI/CD** — backend, frontend, evaluations, architecture, Docker build in GitHub Actions | `.github/workflows/ci.yml` |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
