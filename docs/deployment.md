# Deployment

---

## Overview

The local Docker Compose stack is designed to map cleanly to AWS services.
Moving from local to production requires only environment variable changes
and infrastructure provisioning — no code changes.

| Local | AWS |
|---|---|
| SQLite | RDS PostgreSQL |
| Docker Compose | ECS Fargate |
| Local LLM fake | AWS Bedrock |
| stdout logs | CloudWatch Logs |
| Local file storage | S3 (eval results) |
| No CDN | CloudFront + S3 (React static) |

---

## Local Docker Architecture

```
docker-compose.yml
├── backend
│   image: ai-mcp-data-platform/backend
│   ports: 8000:8000
│   volumes: ./backend → /app, ./data → /data
│   env_file: .env
│
└── frontend
    image: ai-mcp-data-platform/frontend
    ports: 5173:5173
    volumes: ./frontend → /app
```

**No separate database container** — SQLite is file-based, stored in `./data/db.sqlite`.

Start the stack:
```bash
docker compose up
docker compose up --build    # rebuild images
docker compose down          # stop and remove containers
```

---

## Docker Images

### Backend

```dockerfile
# Base: Python 3.12 slim
# 1. Install system deps
# 2. Install uv
# 3. Copy pyproject.toml and install dependencies
# 4. Copy application code
# 5. Run: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Production image omits dev dependencies (pytest, mypy, ruff).

### Frontend

Development: Vite dev server with hot reload.
Production: Multi-stage build — Vite build → nginx serving static files.

---

## AWS Architecture (Planned)

```
┌─────────────────────────────────────────────────────────────┐
│                        AWS Region                            │
│                                                             │
│  ┌─────────────┐    ┌────────────────────────────────────┐  │
│  │  CloudFront │    │         VPC                        │  │
│  │  + S3       │    │                                    │  │
│  │  (React SPA)│    │  ┌──────────────────────────────┐  │  │
│  └─────────────┘    │  │   Public Subnet               │  │  │
│                     │  │   ALB (Application Load       │  │  │
│                     │  │       Balancer)               │  │  │
│                     │  └──────────────┬───────────────┘  │  │
│                     │                 │                   │  │
│                     │  ┌──────────────▼───────────────┐  │  │
│                     │  │   Private Subnet              │  │  │
│                     │  │   ECS Fargate                 │  │  │
│                     │  │   (backend container)         │  │  │
│                     │  └──────┬───────────────────────┘  │  │
│                     │         │                           │  │
│                     │  ┌──────▼──────────────────────┐   │  │
│                     │  │   Private Subnet              │  │  │
│                     │  │   RDS PostgreSQL (Multi-AZ)   │  │  │
│                     │  └──────────────────────────────┘  │  │
│                     └────────────────────────────────────┘  │
│                                                             │
│  AWS Bedrock (Claude 3) ─────────────► ECS task            │
│  CloudWatch Logs ◄──────────────────── ECS container       │
│  ECR ────────────────────────────────► ECS image source    │
│  Secrets Manager ────────────────────► ECS task env vars   │
│  IAM Task Role ──────────────────────► Bedrock + RDS perms │
└─────────────────────────────────────────────────────────────┘
```

---

## Migration Path: Local → AWS

### Step 1: Provision RDS

```bash
# Terraform (planned) or AWS Console
# Create PostgreSQL 15 instance in private subnet
# Store credentials in AWS Secrets Manager
```

### Step 2: Run Alembic Migrations Against RDS

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@rds-host:5432/db \
  alembic upgrade head
```

### Step 3: Build and Push Docker Images to ECR

```bash
# Build production image
docker build -f docker/backend.Dockerfile -t ai-mcp-backend:latest backend/

# Push to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_REGISTRY
docker tag ai-mcp-backend:latest $ECR_REGISTRY/ai-mcp-backend:latest
docker push $ECR_REGISTRY/ai-mcp-backend:latest
```

### Step 4: Update ECS Task Definition

Environment variables in ECS task definition (sourced from Secrets Manager):
```json
{
  "DATABASE_URL": "arn:aws:secretsmanager:...:secret:db-url",
  "LLM_PROVIDER": "bedrock",
  "LLM_MODEL": "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "AWS_REGION": "us-east-1",
  "LOG_LEVEL": "INFO"
}
```

### Step 5: Deploy Static Frontend to S3 + CloudFront

```bash
cd frontend
npm run build

# Upload to S3
aws s3 sync dist/ s3://ai-mcp-frontend-bucket/ --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id $CF_DIST_ID --paths "/*"
```

---

## IAM Permissions

The ECS task role requires:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-*"
    },
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:ai-mcp-*"
    }
  ]
}
```

---

## Health Checks

| Endpoint | Used by |
|---|---|
| `GET /api/v1/health` | ECS liveness check, ALB health check |
| `GET /api/v1/ready` | ECS readiness check — verifies DB + LLM connectivity |

---

## Secrets Management

**Never** store credentials in:
- Docker images
- Git repository
- Environment files committed to version control

Production secrets live in AWS Secrets Manager and are injected into ECS
containers at task startup.

Local development uses `.env` (git-ignored).

---

## Logging in Production

All containers log to stdout in structured JSON format.
CloudWatch Logs agent (FireLens or awslogs driver) ships logs to CloudWatch.

Log groups:
- `/ai-mcp/backend` — FastAPI + MCP server logs
- `/ai-mcp/backend/llm` — LLM call logs (model, tokens, latency)
- `/ai-mcp/backend/tools` — MCP tool call logs
- `/ai-mcp/evaluations` — Evaluation run logs

CloudWatch Insights queries for common diagnostics are documented in
`scripts/cloudwatch_queries/`.
