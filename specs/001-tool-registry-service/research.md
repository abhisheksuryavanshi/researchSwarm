# Research: Tool Registry Service

**Feature**: 001-tool-registry-service
**Date**: 2026-03-26

## Research Tasks & Decisions

### RT-001: Embedding Provider for Semantic Search

**Decision**: Pluggable embedding provider behind an `EmbeddingProvider`
interface, with three backends:

| Backend | Config value | Dimensions | Use case |
|---------|-------------|-----------|----------|
| `sentence-transformers/all-MiniLM-L6-v2` | `local` | 384 | Local dev, CI, offline |
| Google GenAI `text-embedding-004` | `google` | 768 | Default for testing & production (free tier) |
| OpenAI `text-embedding-3-small` | `openai` | 1536 | Alternative production provider |

**Rationale**:
- The registry MUST work in local dev without API keys (constitution
  Principle II — layered independence). Local `sentence-transformers`
  satisfies this.
- For deployed environments, Google GenAI's embedding API has a generous
  free tier (~1500 requests/minute) making it ideal for testing and
  early production. The `google-genai` Python SDK is lightweight.
- OpenAI and Anthropic (via proxy) are supported as alternatives for teams
  that already have those API keys.
- The `EmbeddingProvider` interface is a simple protocol: `embed(text) →
  list[float]`. Swapping providers requires only a config change
  (`EMBEDDING_PROVIDER=google`), no code changes.
- pgvector column uses `VECTOR(768)` as the default dimension (Google
  GenAI's output size). When using local/OpenAI, vectors are
  padded/truncated or the column is provisioned at init time based on
  the configured provider's dimension.

**Alternatives considered**:
- **Hardcoded single provider** — simpler but forces all environments to
  use the same backend. Blocks offline development if cloud-only, or
  blocks production quality if local-only.
- `all-mpnet-base-v2` — slightly better local quality (768 dims) but 2x
  the vector size and slower inference. Unnecessary when Google GenAI is
  the production target.
- **LiteLLM for embeddings** — LiteLLM supports embedding routing but
  adds a heavy dependency for something achievable with a 20-line
  interface.

### RT-002: Vector Storage for Semantic Search

**Decision**: PostgreSQL with `pgvector` extension (AWS RDS PostgreSQL in
deployed environments)

**Rationale**:
- Keeps everything in a single database — no separate vector store service
  to deploy, configure, or maintain.
- `pgvector` supports cosine similarity (`<=>` operator), L2 distance, and
  inner product natively.
- For the expected corpus size (~50-200 tools), exact search is fast enough.
  IVFFlat or HNSW indexes can be added later if needed.
- The `pgvector` Python package integrates cleanly with SQLAlchemy via a
  custom `Vector` column type.
- **AWS RDS PostgreSQL 16** supports pgvector natively (available as a
  trusted extension since late 2023). No custom AMI or manual extension
  installation required — just `CREATE EXTENSION vector`.

**Alternatives considered**:
- **Qdrant / Pinecone / Weaviate** — purpose-built vector DBs with better
  scaling, but add a separate service dependency. Overkill for <1000 vectors.
- **In-memory numpy array** — fastest but loses persistence across restarts
  and doesn't scale to multi-instance deployment.
- **ChromaDB** — lightweight but adds another embedded database; redundant
  when PostgreSQL is already in the stack.
- **Amazon OpenSearch with vector search** — managed service but adds a
  second data store and doubles infra cost. Not justified for <1000 vectors.

### RT-003: SQLAlchemy Sync vs Async

**Decision**: Async SQLAlchemy with `asyncpg` driver

**Rationale**:
- FastAPI is async-native; using sync SQLAlchemy would block the event loop
  on every database call, defeating the purpose of async.
- `asyncpg` is the highest-performance PostgreSQL driver for Python async.
- SQLAlchemy 2.0+ has first-class async support via `AsyncSession` and
  `create_async_engine`.
- The `pgvector` package supports async SQLAlchemy.

**Alternatives considered**:
- **Sync SQLAlchemy with `psycopg2`** — simpler but blocks the event loop.
  Would require thread pool executors for every DB call, adding complexity
  and reducing throughput.
- **Raw `asyncpg` without ORM** — maximum performance but loses SQLAlchemy's
  schema management, migrations, and query builder. Not worth the tradeoff
  for a service with 3 tables.

### RT-004: Health Check Proxying

**Decision**: `httpx.AsyncClient` with 500ms timeout

**Rationale**:
- `httpx` is the modern async HTTP client for Python — supports timeouts,
  connection pooling, and retries natively.
- A shared `AsyncClient` instance (connection pool) avoids per-request
  connection overhead.
- 500ms timeout aligns with the constitution's health check budget.
- Responses are classified: <500ms = healthy, timeout = degraded,
  connection error = unhealthy.

**Alternatives considered**:
- **`aiohttp`** — equally capable but `httpx` has a cleaner API and is
  the FastAPI-recommended HTTP client.
- **Background health polling** — proactively checking tools on a schedule
  rather than on-demand. Good for production but adds complexity (scheduler,
  state management). Deferred to Phase 4.

### RT-005: LangChain Tool Definition Format

**Decision**: Return a JSON structure matching LangChain's `StructuredTool`
constructor arguments.

**Rationale**:
- LangChain's `StructuredTool` accepts: `name` (str), `description` (str),
  `args_schema` (JSON Schema or Pydantic model), and a callable.
- The `/bind` endpoint returns `name`, `description`, `args_schema`
  (as JSON Schema), and `endpoint` (the HTTP URL to invoke).
- The consuming agent constructs the callable on its side — wrapping the
  endpoint in an HTTP call. This keeps the registry decoupled from
  LangChain's runtime.

**Format**:
```json
{
  "name": "sec-filing-parser-v1",
  "description": "Parses SEC EDGAR filings and extracts structured data",
  "args_schema": {
    "type": "object",
    "properties": {
      "ticker": {"type": "string", "description": "Stock ticker symbol"},
      "filing_type": {"type": "string", "enum": ["10-K", "10-Q", "8-K"]}
    },
    "required": ["ticker"]
  },
  "endpoint": "http://tools-service:8001/sec-parser",
  "method": "POST"
}
```

### RT-006: Database Migration Strategy

**Decision**: Alembic for schema migrations

**Rationale**:
- Standard migration tool for SQLAlchemy projects.
- Supports auto-generation of migration scripts from model changes.
- Async-compatible with `asyncpg`.
- The `pgvector` extension creation (`CREATE EXTENSION vector`) is handled
  in the initial migration.

**Alternatives considered**:
- **Manual SQL scripts** — simpler but error-prone and doesn't track applied
  state.
- **SQLAlchemy `create_all`** — fine for prototyping but doesn't support
  incremental schema changes. Unsuitable for production.

### RT-007: Structured Logging Setup

**Decision**: `structlog` with JSON renderer, bound to `trace_id` and
`session_id` context vars.

**Rationale**:
- Constitution Principle V mandates `structlog` with JSON output.
- `structlog` context variables (bound loggers) allow `trace_id`,
  `session_id`, and `agent_id` to be set once per request and
  automatically included in every log line.
- FastAPI middleware sets context vars from request headers on each request.

### RT-008: Seed Tool Inventory

**Decision**: Seed 7 tools covering distinct capability domains.

| Tool | Capabilities | Endpoint (placeholder) |
|------|-------------|----------------------|
| SerpAPI Web Search | `web_search`, `general_knowledge` | `http://tools:8001/serp` |
| ArXiv Paper Search | `academic_papers`, `arxiv` | `http://tools:8001/arxiv` |
| GitHub Repository Search | `code_search`, `github`, `repositories` | `http://tools:8001/github` |
| Wikipedia Lookup | `general_knowledge`, `encyclopedia` | `http://tools:8001/wikipedia` |
| Calculator | `math`, `calculation` | `http://tools:8001/calculator` |
| URL Scraper | `web_scraping`, `content_extraction` | `http://tools:8001/scraper` |
| SEC Filing Parser | `financial_data`, `sec_filings`, `document_parsing` | `http://tools:8001/sec-parser` |

### RT-009: LLM Provider Strategy (Cross-Phase)

**Decision**: Use LiteLLM as the unified LLM gateway for all agent LLM calls
(Phase 2+). The registry itself does not make LLM calls — only embedding
calls — but the provider abstraction pattern established here carries forward.

**Provider priority**:

| Provider | SDK | Use case | API key env var |
|----------|-----|----------|-----------------|
| Google GenAI | `google-genai` | Default for testing (free tier) | `GOOGLE_API_KEY` |
| OpenAI | `openai` | Production alternative, Cursor API key compatible | `OPENAI_API_KEY` |
| Anthropic | `anthropic` | Production alternative | `ANTHROPIC_API_KEY` |

**Rationale**:
- Google GenAI's free tier is the most generous for testing: Gemini 2.0
  Flash allows 15 requests/minute and 1 million tokens/day at no cost.
  This is sufficient for development and integration testing.
- LiteLLM provides a single `completion()` interface that routes to any
  provider based on the model string prefix (`gemini/`, `gpt-4o`,
  `claude-3-5-sonnet`). No agent code changes needed to switch providers.
- The Cursor API key (OpenAI-compatible endpoint) can be used by setting
  `OPENAI_API_KEY` and `OPENAI_API_BASE` — LiteLLM supports custom base
  URLs natively.
- Configuration is entirely via environment variables — no code changes
  to switch between providers.

**Alternatives considered**:
- **Direct SDK per provider** — maximum control but requires maintaining
  3 separate integration paths. LiteLLM abstracts this.
- **LangChain's ChatModel abstraction** — works but adds the full LangChain
  dependency. LiteLLM is lighter when using LangGraph (which already has
  LiteLLM integration).
- **Hardcoded to one provider** — simplest but locks the project to a
  single vendor. Unacceptable given the multi-provider requirement.

### RT-010: AWS Infrastructure Strategy

**Decision**: AWS-first deployment with local Docker fallback for development.

| Component | Local (dev) | AWS (deployed) |
|-----------|------------|----------------|
| PostgreSQL + pgvector | Docker Compose (`pgvector/pgvector:pg16`) | AWS RDS PostgreSQL 16 (pgvector extension) |
| Registry service | `uvicorn` on localhost | EC2 instance (or ECS Fargate) |
| Redis (Phase 5) | Docker Compose | Amazon ElastiCache |
| Langfuse (Phase 4) | Docker Compose (self-hosted) | EC2 or Langfuse Cloud |
| Embedding model (local) | In-process `sentence-transformers` | N/A (use Google GenAI API) |

**Rationale**:
- AWS RDS PostgreSQL 16 supports pgvector as a trusted extension. No custom
  images required. `db.t3.micro` is free-tier eligible for 12 months.
- EC2 `t3.micro` (free tier) or `t3.small` is sufficient for the registry
  service in early phases. Can scale to ECS Fargate later.
- The `DATABASE_URL` connection string is the only config difference between
  local and AWS — the application code is identical.
- Docker Compose remains the local development setup. AWS is for staging and
  production. No changes to application code needed — only environment
  variables.

**AWS RDS pgvector setup**:
```sql
-- Run once after creating the RDS instance (handled by Alembic migration)
CREATE EXTENSION IF NOT EXISTS vector;
```

**Alternatives considered**:
- **AWS Aurora Serverless** — auto-scaling and pay-per-use but pgvector
  support varies by version. Standard RDS is simpler and more predictable.
- **GCP Cloud SQL** — equally capable but user prefers AWS.
- **Self-managed EC2 PostgreSQL** — full control but loses managed backups,
  patching, and failover. Not worth the operational overhead.
- **ECS Fargate from day one** — cleaner but adds Docker image registry
  (ECR), task definitions, and networking complexity. EC2 is simpler for
  v1; migrate to Fargate when scaling demands it.
