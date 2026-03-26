# Quickstart: Tool Registry Service

## Prerequisites

- Python 3.11+
- Docker & Docker Compose (for local PostgreSQL with pgvector)
- ~200MB disk for the `all-MiniLM-L6-v2` embedding model (local dev only,
  downloaded on first run)

## Setup (Local Development)

### 1. Start infrastructure

```bash
docker compose up -d postgres
```

This starts PostgreSQL 16 with the `pgvector` extension pre-installed.

### 2. Install dependencies

```bash
pip install -e ".[dev]"
```

Or using the requirements file:

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Key variables for **local development** (no API keys needed):

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/researchswarm
EMBEDDING_PROVIDER=local
LOG_LEVEL=INFO
```

For **deployed environments** (AWS RDS + Google GenAI):

```env
DATABASE_URL=postgresql+asyncpg://user:pass@your-rds-instance.region.rds.amazonaws.com:5432/researchswarm
EMBEDDING_PROVIDER=google
GOOGLE_API_KEY=your-google-genai-api-key
LOG_LEVEL=INFO
```

Alternative providers:

```env
# OpenAI embeddings (also works with Cursor API key)
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your-openai-or-cursor-api-key
OPENAI_API_BASE=https://api.openai.com/v1  # or Cursor's endpoint

# LLM provider for agents (Phase 2+, configured via LiteLLM)
LLM_MODEL=gemini/gemini-2.0-flash       # Google GenAI (free tier)
# LLM_MODEL=gpt-4o                      # OpenAI
# LLM_MODEL=claude-3-5-sonnet-20241022  # Anthropic
```

### 4. Run migrations

```bash
alembic upgrade head
```

This creates the `tools`, `tool_capabilities`, and `tool_usage_logs` tables
and enables the `pgvector` extension.

### 5. Seed the registry

```bash
python -m registry.seed
```

Populates the registry with 7 tools (SerpAPI, ArXiv, GitHub, Wikipedia,
Calculator, URL Scraper, SEC Filing Parser). Idempotent — safe to run
multiple times.

### 6. Start the service

```bash
uvicorn registry.app:app --host 0.0.0.0 --port 8000 --reload
```

The API is now available at `http://localhost:8000`.

## Verify It Works

### Register a tool

```bash
curl -X POST http://localhost:8000/tools/register \
  -H "Content-Type: application/json" \
  -d '{
    "tool_id": "test-tool-v1",
    "name": "Test Tool",
    "description": "A test tool for verifying registration works correctly",
    "capabilities": ["testing"],
    "input_schema": {"type": "object", "properties": {"input": {"type": "string"}}},
    "output_schema": {"type": "object", "properties": {"output": {"type": "string"}}},
    "endpoint": "http://localhost:9999/test",
    "version": "1.0.0"
  }'
```

Expected: 201 with the tool object.

### Search for tools

```bash
# By capability
curl "http://localhost:8000/tools/search?capability=financial_data"

# By semantic query
curl "http://localhost:8000/tools/search?query=parse+SEC+filings"
```

Expected: Ranked list of matching tools.

### Bind a tool

```bash
curl "http://localhost:8000/tools/sec-filing-parser-v1/bind"
```

Expected: LangChain-compatible tool definition with `name`, `description`,
`args_schema`, `endpoint`.

### Check health

```bash
curl "http://localhost:8000/tools/sec-filing-parser-v1/health"
```

Expected: Health status (likely `unhealthy` for seeded tools since their
endpoints aren't running).

### View stats

```bash
curl "http://localhost:8000/tools/stats"
```

Expected: Per-tool usage statistics (zeroed out for fresh registry).

## Running Tests

```bash
# All tests
pytest

# Contract tests only
pytest tests/contract/

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# With coverage
pytest --cov=registry --cov-report=term-missing
```

## API Documentation

FastAPI auto-generates interactive docs:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## AWS Deployment

### RDS PostgreSQL Setup

1. Create an RDS PostgreSQL 16 instance (`db.t3.micro` for free tier).
2. Enable the `pgvector` extension (Alembic migration handles
   `CREATE EXTENSION vector` automatically).
3. Set `DATABASE_URL` to the RDS connection string.

### EC2 Deployment

1. Launch an EC2 `t3.micro` or `t3.small` instance (Amazon Linux 2023).
2. Install Python 3.11+, clone the repo, install dependencies.
3. Set environment variables (RDS URL, Google GenAI API key).
4. Run with: `uvicorn registry.app:app --host 0.0.0.0 --port 8000`
5. (Optional) Use systemd or supervisord for process management.

### Security Group Configuration

- RDS: Allow inbound PostgreSQL (5432) from EC2 security group only.
- EC2: Allow inbound HTTP (8000) from your IP / load balancer.
- Both in the same VPC for private networking.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `pgvector` extension not found | Use the `pgvector/pgvector:pg16` Docker image (local) or verify RDS PostgreSQL 16 (AWS). |
| Embedding model download fails | Check internet connectivity. Model is cached in `~/.cache/huggingface/`. Only needed for `EMBEDDING_PROVIDER=local`. |
| Google GenAI API errors | Verify `GOOGLE_API_KEY` is set. Check free tier quotas at https://ai.google.dev/. |
| `asyncpg` connection refused | Verify PostgreSQL is running: `docker compose ps` (local) or check RDS endpoint + security groups (AWS). |
| Migration fails | Ensure the database exists. Local: `docker compose exec postgres createdb researchswarm`. AWS: connect via psql to RDS and `CREATE DATABASE`. |
| Cursor API key not working | Set `OPENAI_API_KEY` to your Cursor key and `OPENAI_API_BASE` to Cursor's endpoint URL. |
