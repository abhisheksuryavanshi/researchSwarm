# researchSwarm — Local development and AWS deployment

This document is derived from the repository as it exists today (Python package `researchswarm-registry`, single FastAPI app in `registry.app`, Alembic migrations, Docker Compose for MySQL only).

---

## Project overview

**What it does:** A multi-agent research system built around a **tool registry** (FastAPI + MySQL). Agents run as a **LangGraph** pipeline (Researcher → Analyst → Critic → Synthesizer, with optional loop-back) and talk to the registry over HTTP (`RegistryClient`). A **conversational session layer** (`conversation/`) can be mounted on the same FastAPI app: it uses **Redis** for locks/working-set cache and **MySQL** for durable session rows and snapshots. If Redis/MySQL for conversation or LLM setup fails at startup, the coordinator is skipped and the app still serves registry routes (see `registry/app.py` lifespan).

**Architecture (as implemented):**

- **One process:** `uvicorn registry.app:app` exposes tool registry APIs under `/tools/*` and session APIs under `/v1/sessions*` when the coordinator initializes.
- **Agents:** `agents/` — LangGraph graph, Gemini via `langchain-google-genai`, optional Langfuse tracing.
- **Persistence:** SQLAlchemy 2 async + `aiomysql`; Alembic migrations under `alembic/versions/`.
- **Session layer:** `conversation/` — coordinator, intent classification, MySQL + Redis stores.

**Tech stack (from `pyproject.toml`):** Python 3.9+, FastAPI, Uvicorn, SQLAlchemy 2 (async), aiomysql, httpx, structlog, pydantic-settings, Alembic, LangGraph, LangChain / LangChain-Google-GenAI, Langfuse, Redis (hiredis). Dev extras: pytest, pytest-asyncio, ruff, black, coverage.

---

## Prerequisites

| Tool | Minimum / notes |
|------|------------------|
| **Python** | 3.9+ (`requires-python = ">=3.9"` in `pyproject.toml`; CI/local often use 3.9.6) |
| **Docker Engine** | Recent version with **Docker Compose V2** (`docker compose` CLI) |
| **Git** | Any recent version (clone) |
| **Package manager** | Either **[uv](https://github.com/astral-sh/uv)** (lockfile `uv.lock` present) **or** **pip** with a virtualenv |

**Optional but useful:**

- `curl` — verify HTTP endpoints from the shell.
- Google AI **API key** for Gemini — required for real LLM calls (`GOOGLE_API_KEY`).

**Not in repo (⚠️ TODO):**

- No `Dockerfile` or `requirements.txt` at repository root (install via `pyproject.toml` only).
- `docker-compose.yml` defines **MySQL only** — not Redis or Langfuse (README mentions them; run Redis separately for full conversation features).

---

## Environment configuration

Values load from **environment variables** and/or a **`.env`** file in the repository root (`env_file=".env"` in `registry.config.Settings`, `agents.config.AgentConfig`, and `conversation.config.ConversationSettings`).

### Registry (`registry/config.py`)

| Variable | Purpose | Accepted values | Example |
|----------|---------|-----------------|--------|
| `DATABASE_URL` | Async MySQL DSN for SQLAlchemy (`aiomysql`) | `mysql+aiomysql://user:password@host:port/database` | `mysql+aiomysql://root:root@localhost:3306/researchswarm` |
| `LOG_LEVEL` | Structlog / app logging | Typical: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

### Agent layer (`agents/config.py`)

| Variable | Purpose | Accepted values | Example |
|----------|---------|-----------------|--------|
| `GOOGLE_API_KEY` | Gemini API key | Non-empty string when calling the real model | *(secret)* |
| `LLM_PROVIDER` | Provider label | Default `google` | `google` |
| `LLM_MODEL` | Model id | String | `gemini-2.0-flash` |
| `LLM_TEMPERATURE` | Sampling | Float | `0.1` |
| `LLM_TIMEOUT_SECONDS` | Per-call timeout | Integer ≥ 1 | `30` |
| `LLM_MAX_RETRIES` | LLM retries | Integer ≥ 0 | `3` |
| `MAX_ITERATIONS` | Graph iteration cap | Integer **1–5** | `3` |
| `GRAPH_TIMEOUT_SECONDS` | `asyncio.wait_for` around graph invoke | Integer ≥ 1 | `60` |
| `REGISTRY_BASE_URL` | Base URL for registry HTTP client | HTTP(S) URL, no trailing path | `http://localhost:8000` |
| `TOOL_INVOCATION_TIMEOUT_SECONDS` | Dynamic tool HTTP timeout | Integer ≥ 1 | `30` |
| `MAX_TOOL_FALLBACK_ATTEMPTS` | Fallback attempts | Integer **1–10** | `3` |
| `LANGFUSE_ENABLED` | Enable Langfuse callback | `true` / `false` | `true` |
| `LANGFUSE_HOST` | Langfuse API host | URL | `http://localhost:3000` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key | String | *(from Langfuse)* |
| `LANGFUSE_SECRET_KEY` | Langfuse secret | String | *(from Langfuse)* |
| `TOKEN_USAGE_WARN_THRESHOLD` | Token warning threshold (logs) | Integer | `100000` |
| `TRACE_EXCERPT_MAX_CHARS` | Max chars in trace excerpts | Integer | `2048` |

`agents/tracing.py` also reads `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST` from the environment when building the callback handler.

### Conversation layer (`conversation/config.py`)

These use the prefix **`CONVERSATION_`** (via `env_prefix` in Pydantic settings).

| Variable | Purpose | Constraints | Default (in code) |
|----------|---------|-------------|-------------------|
| `CONVERSATION_REDIS_URL` | Redis for locks + working set | Redis URL | `redis://localhost:6379/0` |
| `CONVERSATION_DATABASE_URL` | MySQL for session tables | Same DSN style as `DATABASE_URL` | `mysql+aiomysql://root:root@localhost:3306/researchswarm` |
| `CONVERSATION_LLM_MODEL` | Intent classifier model | String | `gemini-2.0-flash` |
| `CONVERSATION_INTENT_CONFIDENCE_THRESHOLD` | Below → clarification path | 0.0–1.0 | `0.55` |
| `CONVERSATION_TURN_LOCK_TTL_SECONDS` | Redis lock TTL | 5–3600 | `120` |
| `CONVERSATION_REDIS_WORKING_SET_TTL_SECONDS` | Cached session doc TTL | 60–2592000 (30d cap) | `86400` |
| `CONVERSATION_GOOGLE_API_KEY` | Optional override for conversation-side LLM | String or empty | `None` |

⚠️ **TODO:** Root `.env.example` does **not** yet list `CONVERSATION_*` variables; add them to `.env` manually for full session API behavior.

### Tests (`tests/conftest.py`)

| Variable | Purpose | Example |
|----------|---------|--------|
| `TEST_DATABASE_URL` | MySQL for integration tests | `mysql+aiomysql://root:root@localhost:3306/researchswarm_test` |

Tests expect MySQL on **localhost:3306** unless you override the URL and networking.

### Alembic

Migrations read **`sqlalchemy.url`** from **`alembic.ini`** (currently `mysql+aiomysql://root:root@localhost:3306/researchswarm`), **not** automatically from `DATABASE_URL`.

⚠️ **TODO:** If your MySQL URL differs from `alembic.ini`, update that file or use Alembic’s documented pattern to inject the URL from the environment before running migrations.

---

## Installation

From a clean machine (macOS or Linux):

```bash
git clone <your-remote-url> researchSwarm
cd researchSwarm
```

**1. Start MySQL (Docker Compose)**

```bash
docker compose up -d mysql
```

**2. Install Python dependencies**

Using **uv** (recommended; uses `uv.lock`):

```bash
uv sync --extra dev
```

Using **pip** and a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

**3. Environment file**

```bash
cp .env.example .env
# Edit .env: set GOOGLE_API_KEY, optional Langfuse keys, and align DATABASE_URL if needed
```

**4. Redis (required for conversation coordinator)**

Not defined in `docker-compose.yml`. Example:

```bash
docker run -d --name researchswarm-redis -p 6379:6379 redis:7-alpine
```

**5. Database migrations**

Ensure `alembic.ini` `sqlalchemy.url` matches your MySQL database, then:

```bash
uv run alembic upgrade head
# or: .venv/bin/alembic upgrade head
```

Revisions in repo: `001_initial_schema`, `002_conversation_session_tables`.

**6. Seed tool catalog (idempotent)**

```bash
uv run python -m registry.seed
# or: python -m registry.seed
```

---

## Running locally

**Infrastructure**

- MySQL: `docker compose up -d mysql` (port **3306**, DB `researchswarm`, root password `root` per `docker-compose.yml`).
- Redis: separate container or local Redis on **6379** (see above).

**Application**

```bash
uv run uvicorn registry.app:app --host 0.0.0.0 --port 8000 --reload
```

**Langfuse (optional)** — not bundled in Compose; point `LANGFUSE_*` at your instance or set `LANGFUSE_ENABLED=false` for local runs without tracing.

There is **no separate worker process** in this repository; session turns and registry are served by the same Uvicorn process.

---

## Verifying the setup

| Check | Command / URL | Expected |
|-------|----------------|----------|
| OpenAPI schema | `curl -sSf http://127.0.0.1:8000/openapi.json \| head` | JSON document |
| Swagger UI | Browser: `http://127.0.0.1:8000/docs` | FastAPI docs page |
| Tool search | `curl -sSf "http://127.0.0.1:8000/tools/search"` | JSON with `results` / `total` after seed |
| Session API | `POST http://127.0.0.1:8000/v1/sessions` with `Authorization: Bearer <owner>` | **201** with `session_id` if coordinator started; **503** if coordinator skipped |
| Coordinator logs | Uvicorn stdout | `conversation_coordinator_initialized` or `conversation_coordinator_skipped` with error |

**Automated tests**

```bash
cd /path/to/researchSwarm
uv run pytest
# or: .venv/bin/pytest
```

Integration tests need MySQL reachable at the configured test URL (default `localhost:3306`).

---

## AWS deployment guide

There is **no container definition in-repo** (no `Dockerfile`). The following matches the **actual dependencies** (FastAPI app, MySQL, Redis, outbound HTTPS to Gemini + Langfuse + tool endpoints).

### Suggested services

| Concern | AWS service | Notes |
|---------|-------------|--------|
| App | **ECS Fargate** or **EC2** | Run Uvicorn (or Gunicorn+Uvicorn workers). ⚠️ Add a `Dockerfile` or use a buildpack; not provided here. |
| MySQL | **Amazon RDS for MySQL** (8.x compatible) | Align with `mysql+aiomysql://...` DSN. |
| Redis | **ElastiCache for Redis** | Use `rediss://` if TLS required; update `CONVERSATION_REDIS_URL`. |
| Secrets | **Secrets Manager** or **SSM Parameter Store** | Store `GOOGLE_API_KEY`, `LANGFUSE_SECRET_KEY`, DB password, etc. |
| Load balancing | **Application Load Balancer** | Target group → service port **8000** (or your chosen port). |
| Observability | **CloudWatch Logs** | Ship container stdout; optional **Langfuse** SaaS or self-hosted on EC2/ECS. |

### Environment variables in AWS

- Map the same variables as in [Environment configuration](#environment-configuration).
- Inject at task/runtime: ECS task definition `secrets` (Secrets Manager / SSM), or EC2 via `systemd` `EnvironmentFile` pulled from SSM.

⚠️ **TODO:** Production `alembic.ini` — run migrations from CI or a one-off task with a job-specific `DATABASE_URL` / `sqlalchemy.url`; do not commit production credentials.

### IAM (high level)

- **ECS task execution role:** Pull images, write logs, read secrets referenced by the task.
- **ECS task role (app):** If the app later calls AWS APIs (S3, etc.), grant least privilege here. Current code uses **HTTP to registry/tools** and external LLM APIs only — no AWS SDK requirement in `pyproject.toml`.
- **Operators / CI:** Permission to deploy ECS services, update task definitions, and read deployment secrets.

### Deployment commands

⚠️ **TODO:** No IaC (Terraform/CDK) or ECS task definitions exist in this repo. After you add a `Dockerfile`, a typical flow is: build image → push to **ECR** → update ECS service. Example shape (values are placeholders):

```bash
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker build -t researchswarm-registry:latest .
docker tag researchswarm-registry:latest <account>.dkr.ecr.<region>.amazonaws.com/researchswarm-registry:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/researchswarm-registry:latest
# Then update ecs service / task definition to new image and env vars
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|----------------|-----|
| `alembic` connects to wrong DB | URL in `alembic.ini` | Set `sqlalchemy.url` to match RDS/local MySQL (see [Alembic](#alembic)). |
| App works but `/v1/sessions` returns **503** | Conversation coordinator not initialized | Start **Redis**; check MySQL; ensure migrations **002** applied; read logs for `conversation_coordinator_skipped`. |
| `Access denied` for MySQL | Credentials / host | Match `DATABASE_URL` and `CONVERSATION_DATABASE_URL` to RDS security groups and user grants. |
| Gemini errors / empty responses | Missing or invalid key | Set `GOOGLE_API_KEY` in `.env` or environment. |
| Port **3306** already in use | Local MySQL vs Compose | Stop conflicting service or change Compose port mapping. |
| Port **6379** in use | Another Redis | Change host port in `docker run` and set `CONVERSATION_REDIS_URL` accordingly. |
| Langfuse warnings / no traces | Keys or host | Set `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST`, or set `LANGFUSE_ENABLED=false`. |
| pytest skips / DB errors | MySQL not running | Start MySQL on `localhost:3306` or set `TEST_DATABASE_URL` and ensure DB exists. |

---

## Quick reference: one-liners

```bash
docker compose up -d mysql
docker run -d --name researchswarm-redis -p 6379:6379 redis:7-alpine
uv sync --extra dev && cp -n .env.example .env
uv run alembic upgrade head && uv run python -m registry.seed
uv run uvicorn registry.app:app --host 0.0.0.0 --port 8000 --reload
```

(`cp -n` does not overwrite an existing `.env`.)
