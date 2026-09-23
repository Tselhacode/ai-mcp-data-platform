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

### 2. Claude Hooks

Claude Hooks run shell commands at specific points in a Claude Code session.
They provide automated feedback before Claude moves on.

#### Implemented hooks

**Post-tool-use: after any Python file edit (`.claude/settings.json`)**
```bash
# Runs ruff lint + format on every edited Python file
case "$FILEPATH" in
  *.py) cd backend && uv run ruff check --fix "$FILEPATH" \
                   && uv run ruff format "$FILEPATH" ;;
esac
```

This fires immediately after every `Edit` or `Write` tool call on a `.py` file.
Non-Python files (TypeScript, YAML, etc.) are skipped.

**What this prevents:**
- Committing code with lint violations
- Leaving manual import ordering after a refactor
- Formatting inconsistencies that cause noisy diffs

**Limitations:**
- Does not run mypy or pytest automatically (too slow for per-edit feedback)
- Does not run on file renames or deletions

Hooks are configured in `.claude/settings.json`.

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

### 5. MCP Contract Tests

A suite of 84 integration tests in `backend/tests/integration/mcp/` that:
1. Start the FastMCP server in-process against an in-memory SQLite database
2. Call each tool with valid inputs and verify output shape and values
3. Call each tool with invalid inputs and verify structured error responses
4. Verify SQL security constraints (`run_readonly_query` rejects writes, UNION, multi-statement)

This catches the common agent error of changing a tool's input schema without
updating the evaluation tasks that reference it. An agent can change a tool and
still pass unit tests — the contract test is the guard.

```bash
cd backend && uv run pytest tests/integration/mcp/ -v
```

---

### 6. Security Checks

```bash
# Detect secrets in the repository (runs in CI)
python scripts/check_secrets.py

# Enforce architecture boundaries (runs in CI)
cd backend && python ../scripts/check_architecture.py
```

**`check_secrets.py`** scans all tracked files for:
- AWS Access Key IDs (`AKIA...`, `ASIA...`)
- AWS Secret Keys
- LangSmith API keys (`ls-...`, `lsv2_...`)
- OpenAI-style keys (`sk-...`)
- Anthropic API keys (`sk-ant-...`)
- Private key markers
- Hard-coded passwords

Skips `.venv`, `node_modules`, `__pycache__`, `.git`, `.claude`,
lock files, and binary formats.

**`check_architecture.py`** enforces import boundaries:
- `services/`, `data/`, `app/` cannot import from `langchain`, `langsmith`, or `fastmcp`
- `mcp/` cannot import from `langchain` or `langsmith`
- Only `llm/factory.py` may import `langchain_aws` or `ChatBedrock`

Both scripts exit with code 1 on violations, failing the CI job.

---

### 7. Documentation Accuracy

The harness relies on documentation that matches the code. Key doc/code pairs that
should remain consistent:

| Document | Code it describes |
|---|---|
| `docs/mcp.md` | `backend/mcp/tools/*.py` tool signatures |
| `docs/evaluations.md` | `evaluations/tasks/*.py` task definitions |
| `docs/llm.md` | `backend/llm/factory.py`, `backend/agent/` |
| `docs/database.md` | `backend/data/models.py` |
| `CLAUDE.md` / `AGENTS.md` | Entire repository structure |

When modifying tools, tasks, or APIs, update the corresponding doc page in the
same commit. This is enforced as a requirement in CLAUDE.md.

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
