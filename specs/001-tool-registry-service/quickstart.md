# Quickstart: Tool Registry Service

## Prerequisites

- Python 3.11+
- Docker & Docker Compose (for local MySQL)

## Setup (Local Development)

### 1. Start infrastructure

```bash
docker compose up -d mysql
```

This starts MySQL 8.0.

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

Key variables for **local development**:

```env
DATABASE_URL=mysql+aiomysql://root:root@localhost:3306/researchswarm
LOG_LEVEL=INFO
```

For **deployed environments** (AWS RDS):

```env
DATABASE_URL=mysql+aiomysql://user:pass@your-rds-instance.region.rds.amazonaws.com:3306/researchswarm
LOG_LEVEL=INFO
```

### 4. Run migrations

```bash
alembic upgrade head
```

This creates the `tools`, `tool_capabilities`, and `tool_usage_logs` tables.

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

# All tools (for passing full catalog to agent)
curl "http://localhost:8000/tools/search"
```

Expected: List of matching tools.

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

### RDS MySQL Setup

1. Create an RDS MySQL 8.0 instance (`db.t3.micro` for free tier).
2. Set `DATABASE_URL` to the RDS connection string.

### EC2 Deployment

1. Launch an EC2 `t3.micro` or `t3.small` instance (Amazon Linux 2023).
2. Install Python 3.11+, clone the repo, install dependencies.
3. Set environment variables (RDS URL).
4. Run with: `uvicorn registry.app:app --host 0.0.0.0 --port 8000`
5. (Optional) Use systemd or supervisord for process management.

### Security Group Configuration

- RDS: Allow inbound MySQL (3306) from EC2 security group only.
- EC2: Allow inbound HTTP (8000) from your IP / load balancer.
- Both in the same VPC for private networking.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `aiomysql` connection refused | Verify MySQL is running: `docker compose ps` (local) or check RDS endpoint + security groups (AWS). |
| Migration fails | Ensure the database exists. Local: `docker compose exec mysql mysql -uroot -proot -e "CREATE DATABASE IF NOT EXISTS researchswarm"`. AWS: connect via mysql client to RDS and `CREATE DATABASE`. |
