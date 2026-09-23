# Local Development

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.12+ | pyenv or python.org |
| Node.js | 20+ | nvm or nodejs.org |
| uv | latest | `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Docker | 24+ | docker.com |
| Docker Compose | V2 | included with Docker Desktop |
| Git | any | git-scm.com |

---

## Quick Start (Docker)

```bash
git clone https://github.com/Tselhacode/ai-mcp-data-platform.git
cd ai-mcp-data-platform

# Copy example env file
cp .env.example .env

# Start everything
docker compose up

# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# API docs: http://localhost:8000/docs
```

---

## Backend Setup (without Docker)

```bash
cd backend

# Create virtual environment and install dependencies
uv sync --all-extras

# Set up environment
cp ../.env.example ../.env
# Edit .env as needed

# Run database migrations
alembic upgrade head

# Seed the database
uv run python scripts/seed.py

# Start the development server
uv run uvicorn app.main:app --reload --port 8000
```

**Backend available at:** http://localhost:8000
**API docs (Swagger):** http://localhost:8000/docs
**API docs (ReDoc):** http://localhost:8000/redoc

---

## Frontend Setup (without Docker)

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

**Frontend available at:** http://localhost:5173

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Database
DATABASE_URL=sqlite+aiosqlite:///./data/db.sqlite

# LLM Provider
LLM_PROVIDER=fake                          # use 'fake' for local dev, 'bedrock' for AWS
LLM_MODEL=anthropic.claude-3-5-sonnet-20241022-v2:0
LLM_MAX_TOKENS=4096
LLM_MAX_ITERATIONS=10

# AWS (only needed if LLM_PROVIDER=bedrock)
AWS_REGION=us-east-1
# AWS credentials via env or ~/.aws/credentials

# MCP
MCP_TRANSPORT=stdio

# Logging
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:80
```

**Never commit `.env` to git.**

---

## Running Tests

```bash
# All backend tests
cd backend && uv run pytest

# Unit tests only (fast, no I/O)
uv run pytest tests/unit/

# Integration tests
uv run pytest tests/integration/

# E2E tests (full pipeline with FakeChatModel)
uv run pytest tests/e2e/

# With coverage
uv run pytest --cov=app --cov-report=html

# Frontend tests
cd frontend && npm run test

# Evaluation suite (offline, uses FakeChatModel)
cd backend && PYTHONPATH=$(pwd) uv run pytest ../evaluations/tests/ -v
```

---

## Running Linters and Type Checkers

```bash
cd backend

# Linting + formatting check
uv run ruff check .
uv run ruff format --check .

# Auto-fix formatting
uv run ruff format .

# Type checking
uv run mypy .

# Run everything at once
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

```bash
cd frontend

# Linting
npm run lint

# Type checking
npm run type-check

# Formatting
npm run format
```

---

## Database Operations

```bash
cd backend

# Create a new migration after model changes
alembic revision --autogenerate -m "describe the change"

# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# View migration history
alembic history

# Reset database (development only)
rm ../data/db.sqlite && alembic upgrade head && python -m scripts.seed
```

---

## Using the MCP Server Directly

For debugging, you can run the MCP server directly and inspect its tools:

```bash
cd backend

# Start MCP server (stdio mode)
uv run python -m mcp._server

# Or use the MCP inspector (if installed)
npx @modelcontextprotocol/inspector uv run python -m mcp._server
```

---

## Running Evaluations

```bash
# Run full offline evaluation suite (from repo root)
cd backend && PYTHONPATH=$(pwd) uv run pytest ../evaluations/tests/ -v

# Run against real Bedrock (requires AWS credentials and seed data)
cd backend && LLM_PROVIDER=bedrock PYTHONPATH=$(pwd) uv run pytest ../evaluations/tests/ -v
```

---

## Directory Layout During Development

```
ai-mcp-data-platform/
├── data/               # Not committed — created by setup
│   ├── db.sqlite       # Local SQLite database
│   ├── logs/           # Structured log output
│   └── evals/          # Evaluation JSONL results
├── backend/
│   └── .venv/          # Not committed — created by uv venv
└── frontend/
    └── node_modules/   # Not committed — created by npm install
```

---

## Common Issues

**"No module named app"**
Make sure you are running commands from inside the `backend/` directory with
the virtual environment activated.

**SQLite database locked**
Only one process can write to SQLite at a time. Stop any running uvicorn process
before running migrations.

**Bedrock connection refused**
Ensure `AWS_REGION` is set and your AWS credentials are configured. Run
`aws sts get-caller-identity` to verify credentials.

**MCP server fails to start**
Check that all backend dependencies are installed with `uv sync --all-extras`.
