# AGENTS.md — Instructions for AI Coding Agents

This file provides guidance for any AI coding agent working in this repository,
regardless of the tool or framework being used.

CLAUDE.md contains Claude Code-specific rules. Read both files.
Where they overlap, this file provides the higher-level principle;
CLAUDE.md provides the Claude-specific implementation rule.

---

## Repository Purpose

This is an AI Data Analyst platform. The core loop is:

```
User question → LLM → MCP tools → SQL database → LLM → Answer
```

The engineering goals are:
1. Demonstrate clean AI/MCP/API architecture
2. Be testable, observable, and evaluable
3. Serve as an AI engineering portfolio project

---

## Layered Architecture — The Most Important Rule

This repository enforces strict layer separation:

```
API routes / MCP tools
        ↓  (call only)
Application services
        ↓  (call only)
Repository interfaces
        ↓  (call only)
Database / external systems
```

**Cross-layer violations are bugs, not style issues.**

- Routes do not touch the database
- MCP tools do not contain business logic
- Services do not import FastAPI or FastMCP
- Repositories do not call services

When you are unsure which layer something belongs to, ask: "Can I test this
without starting a web server or opening a database connection?" If the answer
should be yes but isn't, the code is in the wrong layer.

---

## Reading Before Writing

Before modifying any file:

1. Read the file
2. Read its test file
3. Read the relevant docs/ page
4. Understand what already exists before adding anything new

Agents that skip this step produce inconsistent code.

---

## Working with the MCP Server

MCP tools are the primary interface between the LLM and the data. When adding
or modifying tools:

- Read docs/mcp.md for the tool contract and naming conventions
- Verify the tool calls a service function, not the repository directly
- Verify the tool has a clear docstring (this becomes the LLM's tool description)
- Add or update the tool's integration test
- Validate the tool schema is registered correctly with FastMCP
- Update docs/mcp.md with the new or changed tool specification

---

## Working with the LLM and Agent Layer

- LangChain lives in `backend/agent/` only
- `backend/services/`, `backend/mcp/`, and `backend/data/` have zero LangChain imports
- Only `backend/llm/factory.py` imports `langchain_aws` / `ChatBedrock`
- Never instantiate `ChatBedrock` in tests — use `FakeChatModel`
- LangSmith must be disabled in all automated tests (`LANGSMITH_TRACING=false` in conftest.py)
- Read `docs/llm.md` before adding providers or changing the agent layer
- Do not assume the LangChain MCP adapter API — verify at implementation time
- Do not assume `AgentExecutor` is the right choice — inspect current LangChain APIs first

---

## Working with Evaluations

The evaluations in `evaluations/` are the ground truth for LLM quality.
When changing MCP tools or services:

- Run the evaluation suite to check for regressions
- If a tool signature changes, update the evaluation task definitions
- Do not change expected_answer values without documenting why

When adding new evaluation tasks:
- Add a task definition to `evaluations/tasks/`
- Ensure the task has an unambiguous expected outcome or a clear judge rubric
- Document the task in docs/evaluations.md

---

## Working with the Database

- All schema changes require an Alembic migration
- Never modify the SQLite file directly during development; use migrations
- Seed data lives in `scripts/seed.py`; use it to populate the local DB
- Repository interfaces are in `backend/data/repositories/` — add new query
  methods there, not in services

---

## Test Expectations

An agent should not report a task complete unless:

- All existing tests still pass
- New tests cover the new behavior
- The test command and output are reported explicitly

If you cannot run tests (e.g., environment issue), say so explicitly. Do not
silently skip testing.

---

## Logging Expectations

Every agent-introduced piece of application code that:
- Makes an LLM call
- Makes a database call
- Handles a user request
- Executes an MCP tool

...must emit a structured log event. Logging is not optional. See CLAUDE.md
for the required log fields.

---

## Security Expectations

- No secrets in code or documentation
- No raw user input in SQL
- All MCP tools read-only
- No internal stack traces exposed to external API callers
- Dependencies added only with justification

---

## Documentation Expectations

When you add or change something:

| Change type              | Documentation to update              |
|--------------------------|---------------------------------------|
| New MCP tool             | docs/mcp.md                          |
| New API endpoint         | docs/architecture.md (API section)   |
| New database table       | docs/database.md                     |
| New LLM provider         | docs/llm.md                          |
| New evaluation task      | docs/evaluations.md                  |
| Architecture decision    | ARCHITECTURE.md                      |
| New dev workflow         | docs/local-development.md            |
| New deployment step      | docs/deployment.md                   |

---

## Communicating Changes

At the end of every task, report:

1. Files changed (with paths)
2. Tests run and results
3. Architectural implications (if any)
4. Remaining risks or open questions

---

## Anti-Patterns to Avoid

| Anti-pattern | Why it's wrong |
|---|---|
| Business logic in MCP tool handler | Cannot be tested without MCP runtime |
| Business logic in FastAPI route | Cannot be tested without HTTP client |
| Direct DB access in service | Bypasses repository, breaks swappability |
| Real network calls in unit tests | Slow, fragile, non-deterministic |
| `import boto3` in service code | Ties business logic to AWS |
| Raw SQL in service functions | Bypasses repository abstraction |
| Skipping tests to save time | Creates unknown regressions |
| Adding features not asked for | Increases scope, creates bugs |
| Logging secrets or PII | Security violation |
| Mocking the database in integration tests | Hides real query bugs |
| Importing `langchain_aws` in services | Breaks provider abstraction boundary |
| Enabling LangSmith in tests | Makes tests network-dependent and costly |
| Putting agent logic in MCP tools | Tools must remain independently testable |
