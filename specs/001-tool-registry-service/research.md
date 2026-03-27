# Research: Tool Registry Service

**Feature**: 001-tool-registry-service
**Date**: 2026-03-26

## Research Tasks & Decisions

### RT-001: Tool Discovery Strategy (Simplified)

**Decision**: Capability-tag filtering via SQL + full catalog listing.
No vector embeddings or semantic search.

**Rationale**:
- At the expected scale (~20-50 tools), all tool definitions fit easily
  in a single LLM prompt (200-500 tokens per tool × 50 tools = ~25K tokens,
  well within modern 128K+ context windows).
- The LLM is a better tool selector than cosine similarity — it understands
  intent, context, and subtle distinctions between tools.
- Capability-tag filtering (`WHERE capability = X`) covers the narrowing
  use case without any embedding infrastructure.
- Eliminates 3 embedding provider backends
  (sentence-transformers, Google GenAI, OpenAI), re-embedding on updates,
  503 handling for embedding failures, and vector dimension management.
- If the tool catalog grows to 500+ tools in the future, semantic search
  can be added then. YAGNI applies.

**Alternatives considered and deferred**:
- **Vector embeddings + embedding providers** — full semantic search over tool
  descriptions. Technically elegant but adds disproportionate complexity
  for 20-50 tools. The embedding provider alone required 3 backends,
  a pluggable interface, and cloud API key management.
- **Qdrant / Pinecone / ChromaDB** — even heavier vector store options.
  Not justified at any foreseeable scale for this use case.

### RT-002: ~~Vector Storage~~ (REMOVED)

Superseded by RT-001 simplification. Vector storage is not needed when
tool discovery is done via capability-tag filtering and the LLM selects
from the full catalog.

### RT-003: SQLAlchemy Sync vs Async

**Decision**: Async SQLAlchemy with `aiomysql` driver

**Rationale**:
- FastAPI is async-native; using sync SQLAlchemy would block the event loop
  on every database call, defeating the purpose of async.
- `aiomysql` is a well-maintained async MySQL driver for Python.
- SQLAlchemy 2.0+ has first-class async support via `AsyncSession` and
  `create_async_engine`.

**Alternatives considered**:
- **Sync SQLAlchemy with `PyMySQL`** — simpler but blocks the event loop.
  Would require thread pool executors for every DB call, adding complexity
  and reducing throughput.
- **Raw `aiomysql` without ORM** — maximum performance but loses SQLAlchemy's
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
- Async-compatible with `aiomysql`.
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
(Phase 2+). The registry itself does not make any LLM or embedding calls.

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
| MySQL | Docker Compose (`mysql:8.0`) | AWS RDS MySQL 8.0 |
| Registry service | `uvicorn` on localhost | EC2 instance (or ECS Fargate) |
| Redis (Phase 5) | Docker Compose | Amazon ElastiCache |
| Langfuse (Phase 4) | Docker Compose (self-hosted) | EC2 or Langfuse Cloud |

**Rationale**:
- AWS RDS MySQL 8.0 `db.t3.micro` is free-tier eligible for 12 months.
- EC2 `t3.micro` (free tier) or `t3.small` is sufficient for the registry
  service in early phases. Can scale to ECS Fargate later.
- The `DATABASE_URL` connection string is the only config difference between
  local and AWS — the application code is identical.
- Docker Compose remains the local development setup. AWS is for staging and
  production. No changes to application code needed — only environment
  variables.

**Alternatives considered**:
- **AWS Aurora Serverless** — auto-scaling and pay-per-use but adds complexity.
  Standard RDS is simpler and more predictable.
- **GCP Cloud SQL** — equally capable but user prefers AWS.
- **Self-managed EC2 MySQL** — full control but loses managed backups,
  patching, and failover. Not worth the operational overhead.
- **ECS Fargate from day one** — cleaner but adds Docker image registry
  (ECR), task definitions, and networking complexity. EC2 is simpler for
  v1; migrate to Fargate when scaling demands it.
