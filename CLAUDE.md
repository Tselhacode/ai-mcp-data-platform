# CLAUDE.md — Instructions for Claude Code Sessions

This file governs how Claude Code should work in this repository.
Read it fully before making any changes. These rules are not suggestions.

---

## Before You Touch Any Code

1. **Read the architecture first.** Read ARCHITECTURE.md and the relevant docs/ file
   before changing anything. Do not guess at structure.

2. **Read the file you are about to change.** Never edit a file you have not read
   in the current session.

3. **Understand the layer you are working in.** Is this a route, a service, a
   repository, an MCP tool, a test? Each layer has different responsibilities.
   Do not mix them.

4. **Check for existing patterns.** If similar code exists elsewhere in the
   repository, follow those patterns. Do not introduce new abstractions without
   a concrete reason.

---

## Making Changes

- **Make the smallest change that solves the problem.** Do not refactor surrounding
  code, add docstrings to unchanged functions, or "clean up while you're in there."

- **One concern per change.** A bug fix is a bug fix. A new feature is a new feature.
  Do not combine them.

- **Do not add features that were not asked for.** No "while I'm at it" additions.

- **Do not add error handling for scenarios that cannot happen.** Do not add
  `try/except` around code that is already guaranteed to succeed by the type system
  or by upstream validation.

- **Do not add configuration options for things that do not need to be configurable.**

- **Do not create new files unless necessary.** Prefer editing an existing file.

---

## Testing

- **Every new feature must have a test.** No exceptions.

- **Every bug fix must have a regression test.**

- **Run the tests before reporting a task complete.** Do not claim tests pass
  without running them.

- **Use `FakeChatModel` and `FakeRepository` in unit tests.** Never make real network
  calls or hit a real database in unit tests.

- **Integration tests use SQLite in-memory.** Do not mock the database in
  integration tests.

- **If tests fail, fix them. Do not skip them, comment them out, or mark them
  as xfail without explaining why.**

---

## Security

- **Never log secrets, credentials, API keys, or tokens.** Not at any log level.

- **Never commit `.env` files, secrets, or credentials.**

- **Never expose internal error details to the frontend.** Return a generic error
  message to the client; log the full error server-side.

- **All MCP tools must be read-only.** No INSERT, UPDATE, DELETE, or DDL through
  MCP tools. The `run_safe_query` tool must validate queries against a strict
  SQL allowlist before execution.

- **Never pass raw user input to SQLAlchemy `text()` without parameterization.**
  All queries use bound parameters.

- **Validate all LLM-generated SQL** through the SQL allowlist validator before
  execution, even if it looks safe.

---

## Logging

- **Log in structured JSON.** Never use plain `print()` for application logging.

- **Every LLM call must be logged** with: model, provider, input token count,
  output token count, latency, session_id.

- **Every MCP tool call must be logged** with: tool name, arguments, result
  summary, latency.

- **Every query must be logged** with: session_id, question (truncated), answer
  (truncated), tools used.

- **Errors must be logged** at ERROR level with full stack trace and context.

- **Do not log raw tool results or SQL query results at INFO level.** They may
  contain sensitive data. Use DEBUG level.

---

## MCP Tool Design

- **MCP tools are thin adapters.** They validate input, call a service function,
  and return a result. No business logic in the tool handler itself.

- **All tool inputs must have Pydantic models.** No `dict` or untyped parameters.

- **All tool outputs must be serializable.** Return Pydantic models or plain dicts.

- **Tools must have clear docstrings.** The docstring becomes the tool description
  that the LLM reads. Write it for the LLM, not just for humans.

- **Tool names must be descriptive and consistent.** Use `verb_noun` format:
  `get_building_consumption`, `compare_buildings`, `find_anomalies`.

- **Tools must not have side effects.** No writes, no state mutation.

---

## Database Access

- **All database access goes through the repository.** Services call repositories.
  MCP tools call services. Routes call services. Nobody else touches the database.

- **Never write raw SQL in service or route code.** Use SQLAlchemy ORM or the
  repository pattern. Raw SQL belongs only in repository implementations.

- **All migrations must be Alembic migrations.** Never modify the database schema
  directly.

- **Never hard-code the database URL.** Use environment variables.

- **Use async SQLAlchemy sessions.** Do not use synchronous sessions in
  async FastAPI routes.

---

## LangChain Usage

- **LangChain lives in `backend/agent/` only.** It does not appear in
  `backend/services/`, `backend/mcp/`, `backend/data/`, or `backend/app/`.

- **`backend/services/` must have zero LangChain imports** — not even
  `langchain_core`. These are pure Python services, testable without LangChain
  installed.

- **`backend/mcp/` and `backend/data/` must have zero LangChain imports.**
  The MCP server and repositories are standalone components.

- **The only file that imports `langchain_aws` or `ChatBedrock` is
  `backend/llm/factory.py`.** All other LangChain code uses only
  `langchain_core` types. Treat violations as architecture bugs.

- **Never instantiate `ChatBedrock` in tests.** Use `FakeChatModel`.

- **`FakeChatModel` must support scripted tool-use sequences.** If you modify
  it, ensure it can still return `AIMessage` objects with `tool_calls` fields.

- **The LangChain agent implementation** (AgentExecutor / LangGraph / other)
  is decided at implementation time. Do not commit to a specific API in
  documentation or code comments without checking the current LangChain docs.

- **LangSmith must be disabled in all tests.** `conftest.py` sets
  `LANGSMITH_TRACING=false` and this must never be overridden in test code.

- **The model, provider, and all LangChain settings are configurable via
  environment variables.** Do not hard-code model IDs, region names, or
  LangSmith project names in application logic.

---

## Dependency Management

- **Pin dependencies with exact versions in lock files.** Use `uv` for Python,
  `npm` for the frontend.

- **Do not add new Python packages without justification.** The existing stack
  covers most needs. Justify every new dependency.

- **Do not install packages globally on the host.** Everything runs in virtual
  environments or containers.

- **Separate dev dependencies from runtime dependencies.** Do not ship test
  frameworks or linters in production images.

---

## Documentation

- **Update documentation when you change behavior.** If you change an API, update
  the relevant docs/ file. If you add a tool, update docs/mcp.md.

- **Do not let docs go stale.** A wrong doc is worse than no doc.

- **ARCHITECTURE.md is the source of truth for design decisions.** If you make
  a decision that differs from what is documented there, update ARCHITECTURE.md
  and note why.

---

## What to Report When a Task is Complete

At the end of every task, report:

1. **Files changed** — list every file modified, created, or deleted
2. **Tests run** — exact command used, number of tests, pass/fail
3. **Test results** — paste or summarize the test output
4. **Architectural implications** — does this change affect the architecture? If so, how?
5. **Remaining risks** — what could still go wrong? What is not yet tested?
6. **Documentation updated** — which docs were updated, if any

Do not mark a task complete if tests are failing.

---

## Things Claude Must Never Do

- Never use `--no-verify` to bypass git hooks
- Never commit directly to `main`
- Never hard-code credentials of any kind
- Never skip the architecture review step
- Never run `rm -rf` without explicit user confirmation
- Never add `# type: ignore` without a comment explaining why
- Never silence linter errors by disabling rules file-wide
- Never claim a feature is implemented without running a test that verifies it
- Never import `ChatBedrock` or `langchain_aws` outside `backend/llm/factory.py`
- Never import any LangChain package in `backend/services/`, `backend/mcp/`, or `backend/data/`
- Never instantiate `ChatBedrock` in tests — use `FakeChatModel`
- Never enable LangSmith tracing in tests (`LANGSMITH_TRACING` must be `false`)
- Never write INSERT/UPDATE/DELETE SQL in MCP tool handlers
- Never add business logic to MCP tool handlers — they call services only
