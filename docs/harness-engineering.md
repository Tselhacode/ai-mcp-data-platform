# Harness Engineering

---

## What Is Harness Engineering?

Harness engineering is the practice of designing a repository so that AI coding
agents can work safely and efficiently within it.

A well-designed harness:
- Gives agents clear rules and architecture they can follow
- Provides fast feedback when agents make mistakes (tests, linters, type checking)
- Makes it hard to accidentally introduce security vulnerabilities or break architecture
- Makes changes reviewable (structured logs, test output, documented decisions)

This document describes the concrete harness elements in this repository.

---

## Two Distinct Feedback Loops

This project contains two kinds of AI agents, each with its own feedback loop.
They must not be confused.

### Loop 1: Coding Agent Harness

Controls and evaluates **Claude Code** (or any AI coding agent) when it makes
code changes.

```
Claude Code (coding agent)
        │
        │  Edits code / creates files
        ▼
Claude Hooks (automated triggers)
        │
        ├── ruff check (linting)
        ├── mypy (type checking)
        ├── pytest (relevant tests)
        ├── check_secrets.sh (security)
        └── check_mcp_writes.sh (MCP safety)
        │
        ▼
Feedback to Claude Code
        │
        └── Fix issues → repeat
```

**What it checks:** Does the code work correctly? Does it follow architecture rules?
Are there security problems? Did the agent break existing tests?

**Frequency:** Runs on every edit, within the same Claude Code session.

**Does not require:** A real LLM API, LangSmith, or the application to be running.

---

### Loop 2: Application Agent Evaluation

Evaluates the **LangChain agent** (the application's AI) when it answers
user questions.

```
User task (e.g. "Which building had the largest July-to-August increase?")
        │
        ▼
LangChain agent
        │
        ├── Selects MCP tools
        ├── Calls FastMCP server
        ├── Retrieves data from SQL database
        └── Produces final answer
        │
        ▼
LangSmith traces (if enabled)
        │
        ▼
Evaluation
        │
        ├── Correct building identified? (automated or LLM judge)
        ├── Correct numeric values? (automated)
        └── Refusal for unsafe requests? (automated)
        │
        ▼
EvaluationRecord (JSONL + optional LangSmith experiment)
        │
        ▼
Agent / tool / prompt improvement
```

**What it checks:** Does the agent reason correctly? Does it select the right tools?
Does it produce accurate, grounded answers? Does it refuse unsafe requests?

**Frequency:** Runs manually or on a schedule when model/prompt/tool changes are made.

**Does require:** A real LLM (for meaningful results), seed data, evaluation tasks.

---

### Why They Are Different

| Property | Coding Agent Harness | Application Agent Evaluation |
|---|---|---|
| Subject | Claude Code | LangChain agent |
| What's measured | Code correctness | Answer quality |
| Triggers | Every code edit | Model/prompt/tool changes |
| Speed | < 5 seconds | Minutes per run |
| LLM required | No (FakeChatModel) | Yes (for real eval) |
| LangSmith needed | Never | Optional |
| Runs in CI | Yes (offline tests) | No (too slow/costly) |
| Primary artifact | Test pass/fail | EvaluationRecord + score |

The harness prevents the coding agent from breaking the system.
The evaluation framework measures whether the application agent is doing its job well.

A change that breaks no unit tests but causes the agent to give wrong answers
will be caught by the evaluation framework, not the harness. Both layers are
necessary.

---

## Harness Components

### 1. Agent Instruction Files

| File | Purpose |
|---|---|
| `CLAUDE.md` | Rules for Claude Code sessions |
| `AGENTS.md` | Rules for all AI coding agents |
| `ARCHITECTURE.md` | Architecture decisions and boundaries |
| `docs/` | Deep-dive documentation for each component |

These files are the coding agent's "manual." They prevent agents from guessing at
architecture and reinventing patterns that already exist.

**Key principles encoded in these files:**
- Layer boundaries (routes → services → repositories)
- LangChain boundary (only factory.py imports provider-specific code)
- Logging requirements
- Security rules (no writes via MCP, no secrets in logs)
- Test requirements (FakeChatModel, SQLite in-memory, LangSmith disabled in tests)

---

### 2. Claude Hooks (Planned)

Claude Hooks run shell commands at specific points in a Claude Code session.
They provide automated feedback before Claude makes a mistake.

#### Planned hooks

**Post-tool: after any Python file edit**
```bash
ruff check "$CHANGED_FILE"
mypy "$CHANGED_MODULE"
```

**Post-tool: after any test file edit**
```bash
pytest "$CHANGED_TEST_FILE" -x
```

**Post-session: before session ends**
```bash
pytest backend/tests/ -q
scripts/hooks/check_secrets.sh
scripts/security/check_mcp_writes.sh
```

Hooks are configured in `.claude/settings.json` and documented in
`scripts/hooks/README.md`.

---

### 3. Automated Tests

Tests provide the most concrete feedback for coding agents. If an agent breaks
something, the test suite catches it.

Test categories and their harness role:

| Test type | Harness role |
|---|---|
| Unit tests | Catch logic errors in services immediately |
| Integration tests | Catch incorrect database queries, API contract breaks |
| MCP contract tests | Catch tool schema changes that break the LLM interface |
| Evaluation offline tests | Catch regressions in evaluation framework structure |
| Security tests | Catch SQL injection attempts, write operations |

**Note:** These tests are part of the coding agent harness. They test infrastructure
correctness, not agent answer quality. Agent quality is measured by the evaluation framework.

---

### 4. Linting and Type Checking

```bash
# Python — must pass before any PR merge
ruff check backend/          # linting
ruff format --check backend/ # formatting
mypy backend/                # type checking (strict)

# TypeScript — must pass before any PR merge
eslint frontend/src/
tsc --noEmit
```

**mypy strict mode** catches a significant class of bugs that coding agents
commonly introduce (wrong types passed to repositories, missing Optional handling,
incorrect LangChain model usage).

---

### 5. MCP Contract Validation (Planned)

A suite of tests that:
1. Register all MCP tools from the FastMCP server
2. Verify each tool's schema matches the spec in `docs/mcp.md`
3. Call each tool with valid inputs and verify output shape
4. Call each tool with invalid inputs and verify structured error response

This catches the common agent error of changing a tool's input schema without
updating the evaluation tasks that reference it. An agent can change a tool and
still pass unit tests — the contract test is the guard.

---

### 6. Security Checks (Planned)

```bash
# Check for secrets in staged files
scripts/hooks/check_secrets.sh

# Check for SQL injection risks
scripts/security/check_raw_sql.sh

# Check for write operations in MCP tools
scripts/security/check_mcp_writes.sh

# Check for provider-specific imports outside factory.py
scripts/security/check_llm_imports.sh

# Check dependencies for known vulnerabilities
pip-audit
npm audit
```

These run in CI and optionally as Claude Hooks.

---

### 7. Documentation Validation (Planned)

```bash
# Check all MCP tools in docs/mcp.md exist in server.py
scripts/validate/check_mcp_docs.sh

# Check all API endpoints in docs/architecture.md exist in routes
scripts/validate/check_api_docs.sh

# Check all evaluation tasks in docs/evaluations.md have task files
scripts/validate/check_eval_tasks.sh
```

Documentation drift is a common failure mode when coding agents make changes.

---

### 8. Evaluation Offline Tests as Regression Guard

The offline evaluation tests (using `FakeChatModel`) run in CI. They verify:
- Evaluation tasks can be loaded and executed
- `EvaluationRecord` is created with the correct structure
- Scoring logic produces correct pass/fail for known scripted responses

This is NOT the same as running real agent evaluations. It verifies the
evaluation framework itself is working, which is part of the coding agent harness.

---

## Agent Workflow

The intended workflow for any AI coding agent:

```
1. Read ARCHITECTURE.md and relevant docs/ page
2. Read the files to be changed
3. Make the change
4. Run: ruff check && mypy && pytest (relevant tests)
5. If tests fail: fix the issue
6. Report: files changed, tests run, results, risks
```

Claude Hooks automate steps 4–5, giving the agent immediate feedback.

---

## Design Rationale

**Why not just rely on code review?**
Code review catches problems after the fact. Hooks and tests catch them
during the session, when the agent can still fix them.

**Why both CLAUDE.md and AGENTS.md?**
CLAUDE.md is Claude Code-specific (hooks, session behavior, reporting format).
AGENTS.md covers principles that apply to any agent (layer architecture, testing
requirements, security rules). Separating them keeps each file focused.

**Why FakeChatModel instead of VCR cassettes?**
VCR cassettes record real API responses but are opaque to the coding agent.
FakeChatModel is explicit, readable, and can express tool-use sequences. Coding
agents can read and understand the test fixtures, making them easier to maintain.

**Why SQLite for testing instead of mocking?**
Mocked databases pass tests for code that would fail against a real database.
SQLite in-memory is fast enough (< 100ms for typical test queries) and
catches real query bugs.

**Why is LangSmith not part of the coding agent harness?**
LangSmith measures application agent quality. The coding agent harness measures
code quality. They operate at different levels. The harness must work offline
and for free in CI. LangSmith is paid and external. Conflating them would make
CI dependent on LangSmith availability.
