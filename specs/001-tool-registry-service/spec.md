# Feature Specification: Tool Registry Service

**Feature Branch**: `001-tool-registry-service`
**Created**: 2026-03-26
**Status**: Draft
**Input**: User description: "Build the Tool Registry Service — a standalone FastAPI service with PostgreSQL backing that supports tool registration, semantic search over tool descriptions, runtime binding, health checks, and usage stats."

## Clarifications

### Session 2026-03-26

- Q: Can registered tools be updated, or are they immutable? → A: Add `PUT /tools/{id}` endpoint that updates metadata in-place (re-embeds description if changed).
- Q: What happens when the cloud embedding provider is unreachable during registration? → A: Registration fails with 503. Tool is NOT persisted without an embedding. Operator retries.
- Q: Can tools be deleted from the registry? → A: Soft delete. `DELETE /tools/{id}` sets `status = 'deprecated'`. Tool remains in DB (preserves usage log integrity) but is excluded from search. Reversible via `PUT`.
- Q: Should tool_usage_logs have a retention policy? → A: No retention in v1. Logs grow unbounded. Acceptable at current scale (~200 tools, low invocation volume). Revisit if storage becomes a concern.
- Q: Should the API use a version prefix (e.g., /v1/tools/...)? → A: No path prefix — it pollutes URLs for an internal service. Keep paths as `/tools/...`. If versioning is ever needed, use a query param.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Tool Registration (Priority: P1)

An operator registers a new tool with the registry by providing metadata
(name, description, capabilities, version), input/output schemas, an
invocation endpoint, and a health-check path. The registry validates the
payload, persists the tool, and embeds the description for future semantic
search.

**Why this priority**: Nothing else works without tools in the registry.
Registration is the foundational write path.

**Independent Test**: POST a tool payload, verify 201 response, then GET the
tool by ID and confirm all fields match.

**Acceptance Scenarios**:

1. **Given** an empty registry, **When** a valid tool payload is POSTed to
   `/tools/register`, **Then** the tool is persisted and a 201 response
   returns the tool with a generated `tool_id`.
2. **Given** a tool payload missing required fields (e.g., no `name`),
   **When** POSTed to `/tools/register`, **Then** a 422 response is returned
   with validation errors.
3. **Given** a tool with duplicate `tool_id`, **When** POSTed to
   `/tools/register`, **Then** a 409 response is returned.

---

### User Story 2 — Semantic Tool Search (Priority: P1)

An agent needs a capability (e.g., "financial data extraction") and queries
the registry. The registry searches by capability tags and semantic
similarity over tool descriptions, returning ranked results.

**Why this priority**: Search is the primary read path — the mechanism by
which agents discover tools at runtime. Equal priority with registration
because both are needed for the core loop.

**Independent Test**: Seed 5+ tools, search by capability tag, verify
matching tools are returned. Search by natural language query, verify
semantic ranking is sensible.

**Acceptance Scenarios**:

1. **Given** 5 registered tools, **When** `GET /tools/search?capability=financial_data`
   is called, **Then** only tools with the `financial_data` capability tag
   are returned, ordered by relevance.
2. **Given** 5 registered tools, **When** `GET /tools/search?query=parse SEC filings`
   is called, **Then** tools are returned ranked by semantic similarity to
   the query, with the SEC parser ranked highest.
3. **Given** both `capability` and `query` params, **When** search is called,
   **Then** results are filtered by capability first, then ranked by semantic
   similarity within that subset.
4. **Given** a search with no matches, **When** called, **Then** an empty
   list is returned (not an error).

---

### User Story 3 — Runtime Tool Binding (Priority: P2)

After discovering a tool via search, an agent requests a LangChain-compatible
tool definition so it can bind and invoke the tool within the current
execution. The registry returns a structured definition including name,
description, input schema, and invocation endpoint.

**Why this priority**: Binding is the bridge between discovery and execution.
It depends on registration and search being functional.

**Independent Test**: Register a tool, call `GET /tools/{id}/bind`, verify
the response contains a valid LangChain tool schema (name, description,
args_schema, endpoint).

**Acceptance Scenarios**:

1. **Given** a registered tool, **When** `GET /tools/{id}/bind` is called,
   **Then** a LangChain-compatible tool definition is returned with `name`,
   `description`, `args_schema` (JSON Schema), and `endpoint`.
2. **Given** a non-existent tool ID, **When** bind is called, **Then** a 404
   response is returned.
3. **Given** a tool with a complex input schema, **When** bind is called,
   **Then** the `args_schema` field is valid JSON Schema that can be used for
   Pydantic model generation.

---

### User Story 4 — Health Checks (Priority: P3)

An operator or monitoring system queries the health of a registered tool.
The registry proxies the health check to the tool's configured health
endpoint and returns the result along with latency.

**Why this priority**: Health checks are important for production reliability
but not required for the core discover-bind-invoke loop to function.

**Independent Test**: Register a tool with a health endpoint, call
`GET /tools/{id}/health`, verify the proxied response includes status
and latency.

**Acceptance Scenarios**:

1. **Given** a registered tool with a reachable health endpoint, **When**
   `GET /tools/{id}/health` is called, **Then** the response includes
   `status: "healthy"` and `latency_ms`.
2. **Given** a tool whose health endpoint is unreachable, **When** health
   check is called, **Then** the response includes `status: "unhealthy"`
   and an error message.
3. **Given** a tool whose health endpoint times out (>500ms), **When**
   health check is called, **Then** the tool is marked `status: "degraded"`.

---

### User Story 5 — Usage Statistics (Priority: P3)

An operator views usage statistics for all tools — invocation counts,
average latency, error rates — to understand which tools are most used
and which are underperforming.

**Why this priority**: Stats are an operational concern. Useful for
production but not blocking for the core flow.

**Independent Test**: Log several tool invocations, call
`GET /tools/stats`, verify aggregated metrics are returned per tool.

**Acceptance Scenarios**:

1. **Given** multiple tool invocations logged, **When** `GET /tools/stats`
   is called, **Then** per-tool aggregates are returned: `invocation_count`,
   `avg_latency_ms`, `error_rate`, `last_invoked_at`.
2. **Given** no invocations logged for a tool, **When** stats are called,
   **Then** that tool appears with zeroed-out metrics.

---

### User Story 6 — Registry Seeding (Priority: P2)

The registry is seeded with 5-8 initial tools (SerpAPI Search, ArXiv Parser,
GitHub API, Wikipedia, Calculator, URL Scraper, SEC Filing Parser, News API)
so that agents have tools available from first startup.

**Why this priority**: Without seed data, there is nothing to search or
bind. Required for demo and integration testing.

**Independent Test**: Run the seed script, verify all seeded tools appear
in search results and can be bound.

**Acceptance Scenarios**:

1. **Given** an empty registry, **When** the seed script is run, **Then** at
   least 5 tools are registered with valid metadata, schemas, and capability
   tags.
2. **Given** a registry already containing seeded tools, **When** the seed
   script is run again, **Then** it is idempotent — no duplicates are
   created.

---

### Edge Cases

- What happens when a tool's endpoint URL is malformed at registration time?
  422 with a validation error — URLs MUST be validated via Pydantic.
- What happens when the embedding provider fails during registration?
  503 with structured error log — registration MUST NOT succeed with a
  missing embedding vector. The tool is not persisted. Operator retries.
  This applies to both `POST /tools/register` and `PUT /tools/{id}` when
  description changes.
- What happens when `pgvector` similarity search returns no results above
  a threshold? Return an empty list, not an error.
- What happens when multiple tools share identical capability tags but
  different descriptions? Semantic search MUST differentiate them by
  description embedding similarity.
- What happens when a tool is registered with an empty `capabilities` list?
  Allowed — the tool can still be found via semantic search on description.
- What happens when `PUT /tools/{id}` is called with a partial payload?
  All fields in the request body replace the existing values. Omitted
  optional fields retain their current values. `tool_id` is immutable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept tool registrations via `POST /tools/register`
  with validated Pydantic schemas.
- **FR-002**: System MUST store tool metadata, capability tags, and input/output
  schemas in PostgreSQL.
- **FR-003**: System MUST embed tool descriptions at registration time via a
  pluggable `EmbeddingProvider` (local `sentence-transformers` for dev, Google
  GenAI `text-embedding-004` for deployed environments, OpenAI as alternative)
  and store vectors in pgvector. Provider is selected via `EMBEDDING_PROVIDER`
  env var.
- **FR-004**: System MUST support semantic search via
  `GET /tools/search?capability=X&query=Y` with pgvector cosine similarity.
- **FR-005**: System MUST return LangChain-compatible tool definitions via
  `GET /tools/{id}/bind`.
- **FR-006**: System MUST proxy health checks to registered tool endpoints
  via `GET /tools/{id}/health` with a 500ms timeout.
- **FR-007**: System MUST log all tool invocations (agent_id, tool_id,
  session_id, latency, success/failure) to `tool_usage_logs`.
- **FR-008**: System MUST aggregate usage stats per tool via `GET /tools/stats`.
- **FR-009**: System MUST provide a seed script that populates 5-8 tools
  idempotently.
- **FR-010**: All endpoints MUST return structured JSON error responses on
  failure (never raw 500s).
- **FR-011**: System MUST use structured JSON logging via `structlog` with
  correlation IDs.
- **FR-012**: System MUST support updating existing tools via
  `PUT /tools/{id}`. All mutable fields (name, description, capabilities,
  input/output schemas, endpoint, version, health_check, cost_per_call) are
  replaceable. If `description` changes, the embedding MUST be regenerated.
  Returns 200 on success, 404 if tool not found, 422 on validation errors.
- **FR-013**: System MUST support soft-deleting tools via
  `DELETE /tools/{id}`. This sets `status = 'deprecated'`. The tool row and
  usage logs are preserved. Deprecated tools are excluded from search results.
  Status can be restored to `active` via `PUT /tools/{id}`. Returns 200 on
  success, 404 if tool not found.

### Key Entities

- **Tool**: The primary entity — name, description, capabilities, schemas,
  endpoint, version, health check path, status.
- **ToolCapability**: Many-to-many mapping of capability tags to tools,
  enabling tag-based filtering.
- **ToolUsageLog**: Append-only log of every tool invocation with agent_id,
  tool_id, session_id, latency_ms, success, timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `GET /tools/search` returns results in < 100ms with 50 tools
  in the registry.
- **SC-002**: `GET /tools/{id}/bind` returns a valid LangChain-compatible
  definition in < 200ms.
- **SC-003**: `POST /tools/register` validates, persists, and embeds in
  < 2 seconds.
- **SC-004**: Seeded registry contains at least 5 tools with distinct
  capability tags and valid health endpoints.
- **SC-005**: Contract tests cover all 5 endpoint request/response schemas.
- **SC-006**: All structured logs include `trace_id` and `session_id` fields.

## Assumptions

- **Local dev**: PostgreSQL is available via Docker Compose
  (`pgvector/pgvector:pg16` image). No cloud API keys required — local
  `sentence-transformers` used for embeddings.
- **Deployed**: PostgreSQL is AWS RDS PostgreSQL 16 with the `pgvector`
  extension enabled. Service runs on EC2. Embeddings via Google GenAI
  (free tier) or OpenAI API.
- The `pgvector` extension is available in both the Docker image and AWS
  RDS PostgreSQL 16.
- LLM provider for agents (Phase 2+) is Google GenAI by default (generous
  free tier for Gemini 2.0 Flash). Can switch to OpenAI (Cursor API key
  compatible) or Anthropic via LiteLLM config. No code changes needed.
- Tool endpoints referenced in seed data may not actually be running;
  health checks for seeded tools are expected to return "unhealthy" until
  the actual tool services are deployed.
- This service has no authentication — it runs inside the internal network
  (VPC on AWS). Auth is a future concern.
- The registry is a single-instance service (no horizontal scaling in v1).
  EC2 `t3.micro` or `t3.small` is sufficient.
