# AI MCP Data Platform

A full-stack AI Data Analyst application demonstrating production-grade AI engineering:
MCP server engineering, LLM/tool interaction, SQL analytics, evaluation-driven development,
and harness engineering.

> **Status:** Architecture and documentation phase. Implementation has not begun.
> This document describes planned architecture, not completed features.

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
| CI/CD             | GitHub Actions (planned)                            |
| AWS (future)      | ECS / RDS / Bedrock / CloudWatch                    |

---

## Planned Capabilities

- **Natural language analytics** — Ask questions about energy consumption data in plain English
- **MCP tool execution** — LLM selects and calls tools to query the database
- **Multi-step reasoning** — Agent chains multiple tool calls to answer complex questions
- **Conversation history** — Frontend maintains session context
- **Evaluation harness** — Automated LLM evaluation against predefined analytical tasks
- **Observability** — Structured logging, tool call tracing, evaluation recording
- **Safe-by-default LLM** — Agent refuses unsafe modification requests

---

## Planned MCP Tools

| Tool                       | Description                                              |
|----------------------------|----------------------------------------------------------|
| `list_buildings`           | Return all buildings in the dataset                      |
| `get_building_consumption` | Return consumption for a building over a time range      |
| `compare_buildings`        | Compare two buildings across a time period               |
| `get_monthly_summary`      | Summarize consumption by month for one or all buildings  |
| `find_anomalies`           | Detect anomalous consumption readings                    |
| `get_schema`               | Return database schema (safe, read-only)                 |
| `run_safe_query`           | Execute a pre-validated read-only query                  |

See [docs/mcp.md](docs/mcp.md) for detailed tool specifications.

---

## Evaluation Approach

The evaluation system has two complementary layers:

**Layer 1 — Application and MCP tests** (always run in CI):
- MCP tool contracts, database queries, API contracts, security rules
- Uses `FakeChatModel` — no LLM API cost, runs offline

**Layer 2 — Agent evaluations** (run manually or on schedule):
- LLM agent quality: tool selection, multi-step reasoning, answer accuracy, safety refusals
- Results recorded locally as JSONL; optionally traced in LangSmith
- Task definitions live in the repository (reproducible without LangSmith)

Planned evaluation tasks:

1. Highest consumption building (single tool call, exact match)
2. Two-building comparison (comparison, LLM judge)
3. Month-over-month change detection (trend, exact match on building set)
4. Anomaly detection (anomaly, LLM judge)
5. Multi-step Q3→Q4 comparison (multi_step, LLM judge)
6. Unsafe modification refusal (safety, automated)
7. Unknown building graceful handling (lookup, LLM judge)
8. Schema discovery (multi_step, LLM judge)
9. July-to-August largest increase (trend, LLM judge — detailed worked example)

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
cd backend && python -m uvicorn app.main:app --reload

# Frontend only
cd frontend && npm run dev

# Run evaluations
cd evaluations && python -m pytest
```

---

## Testing Overview

| Test type        | Location            | Runner   |
|------------------|---------------------|----------|
| Backend unit     | `backend/tests/`    | pytest   |
| Backend integration | `backend/tests/` | pytest   |
| MCP contract     | `backend/tests/mcp/`| pytest   |
| Frontend unit    | `frontend/src/`     | vitest   |
| Evaluations      | `evaluations/`      | pytest   |

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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
