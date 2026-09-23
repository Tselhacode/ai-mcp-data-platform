# Contributing

Thank you for contributing to the AI MCP Data Platform.

---

## Before You Start

1. Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system design.
2. Read [CLAUDE.md](CLAUDE.md) if you are using Claude Code.
3. Read [AGENTS.md](AGENTS.md) if you are using any AI coding assistant.
4. Check existing issues and PRs before starting work.

---

## Development Setup

> Full instructions: [docs/local-development.md](docs/local-development.md)

Requirements:
- Python 3.12+
- Node.js 20+
- Docker + Docker Compose
- `uv` (Python package manager)

```bash
# Backend
cd backend
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Frontend
cd frontend
npm install

# Run all tests
cd backend && pytest
cd frontend && npm run test
```

---

## Branching

- `main` — stable, deployable
- `feature/<short-description>` — new features
- `fix/<short-description>` — bug fixes
- `docs/<short-description>` — documentation only

Do not commit directly to `main`.

---

## Commit Messages

Follow Conventional Commits:

```
feat: add compare_buildings MCP tool
fix: handle empty consumption result in monthly summary
docs: update MCP tool specification in docs/mcp.md
test: add integration test for get_building_consumption
refactor: extract SQL validator into separate module
chore: pin SQLAlchemy to 2.0.35
```

Keep the subject line under 72 characters.
Add a body if the change needs explanation.

---

## Pull Requests

- Keep PRs focused. One concern per PR.
- Include test coverage for all new behavior.
- Update documentation for any changed behavior.
- Ensure `ruff`, `mypy`, and `pytest` all pass before requesting review.
- Fill in the PR template completely.

---

## Code Style

**Python:**
- `ruff` for linting and formatting
- `mypy` for type checking (strict mode)
- All public functions have type annotations
- All public functions have docstrings
- Line length: 88 characters

**TypeScript:**
- `eslint` + `prettier`
- Strict TypeScript
- No `any` types without justification

Run the linters:
```bash
# Python
cd backend && ruff check . && ruff format --check . && mypy .

# TypeScript
cd frontend && npm run lint && npm run type-check
```

---

## Testing Requirements

- All new features require tests.
- All bug fixes require regression tests.
- Unit tests must not make network calls or hit a real database.
- Integration tests use SQLite in-memory.
- Tests must pass before a PR is merged.

---

## Security

- Never commit credentials, API keys, or `.env` files.
- Never log secrets or PII.
- Report security vulnerabilities privately via GitHub Security Advisories.

---

## Documentation

Update the relevant `docs/` file when you:
- Add or change an MCP tool → `docs/mcp.md`
- Add or change an API endpoint → `docs/architecture.md`
- Change the database schema → `docs/database.md`
- Change the LLM integration → `docs/llm.md`
- Add an evaluation task → `docs/evaluations.md`

---

## Questions

Open a GitHub Discussion or issue. Tag the question with the appropriate label
(`architecture`, `mcp`, `llm`, `database`, `frontend`, `evaluations`).
