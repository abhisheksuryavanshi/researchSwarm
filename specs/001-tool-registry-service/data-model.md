# Data Model: Tool Registry Service

**Feature**: 001-tool-registry-service
**Date**: 2026-03-26

## Entity Relationship Diagram

```text
┌───────────────────────────────────┐
│              tools                │
├───────────────────────────────────┤
│ tool_id       VARCHAR(100) PK     │
│ name          VARCHAR(255) NOT NULL│
│ description   TEXT NOT NULL        │
│ version       VARCHAR(50) NOT NULL │
│ endpoint      VARCHAR(500) NOT NULL│
│ method        VARCHAR(10) DEFAULT  │
│               'POST'               │
│ input_schema  JSONB NOT NULL       │
│ output_schema JSONB NOT NULL       │
│ health_check  VARCHAR(500)         │
│ status        VARCHAR(20) DEFAULT  │
│               'active'             │
│ embedding     VECTOR(768)           │
│ avg_latency_ms FLOAT DEFAULT 0     │
│ cost_per_call  FLOAT DEFAULT 0     │
│ created_at    TIMESTAMPTZ NOT NULL │
│ updated_at    TIMESTAMPTZ NOT NULL │
└──────────┬────────────────────────┘
           │ 1
           │
           │ N
┌──────────▼────────────────────────┐
│        tool_capabilities          │
├───────────────────────────────────┤
│ id            SERIAL PK           │
│ tool_id       VARCHAR(100) FK     │
│ capability    VARCHAR(100) NOT NULL│
│ UNIQUE(tool_id, capability)       │
└───────────────────────────────────┘

┌───────────────────────────────────┐
│        tool_usage_logs            │
├───────────────────────────────────┤
│ id            SERIAL PK           │
│ tool_id       VARCHAR(100) FK     │
│ agent_id      VARCHAR(100)        │
│ session_id    VARCHAR(100)        │
│ latency_ms    FLOAT NOT NULL      │
│ success       BOOLEAN NOT NULL    │
│ error_message TEXT                 │
│ invoked_at    TIMESTAMPTZ NOT NULL│
│               DEFAULT NOW()       │
└───────────────────────────────────┘
```

## Entity Details

### Tool

The primary entity representing a registered tool in the catalog.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `tool_id` | `VARCHAR(100)` | PK | Unique identifier (e.g., `sec-filing-parser-v1`). Provided by the registrant. |
| `name` | `VARCHAR(255)` | NOT NULL | Human-readable name. |
| `description` | `TEXT` | NOT NULL | Natural language description. Embedded for semantic search. |
| `version` | `VARCHAR(50)` | NOT NULL | Semver string (e.g., `1.0.0`). |
| `endpoint` | `VARCHAR(500)` | NOT NULL | HTTP URL for tool invocation. Validated as a URL at registration. |
| `method` | `VARCHAR(10)` | DEFAULT `'POST'` | HTTP method for invocation (`GET`, `POST`). |
| `input_schema` | `JSONB` | NOT NULL | JSON Schema defining the tool's input parameters. |
| `output_schema` | `JSONB` | NOT NULL | JSON Schema defining the tool's output structure. |
| `health_check` | `VARCHAR(500)` | NULLABLE | Relative or absolute URL path for health checks. NULL means no health check available. |
| `status` | `VARCHAR(20)` | DEFAULT `'active'` | One of: `active`, `degraded`, `unhealthy`, `deprecated`. |
| `embedding` | `VECTOR(768)` | NULLABLE | Description embedding from the configured `EmbeddingProvider`. Dimension depends on provider: local=384, Google GenAI=768, OpenAI=1536. Column sized for Google GenAI (default deployed provider); local embeddings are zero-padded to match. |
| `avg_latency_ms` | `FLOAT` | DEFAULT `0` | Rolling average latency (updated from usage logs). |
| `cost_per_call` | `FLOAT` | DEFAULT `0` | Estimated cost per invocation (for budget tracking). |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, auto | Creation timestamp. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, auto | Last modification timestamp. |

**Indexes**:
- `ix_tools_status` on `status` — for filtering active tools in search.
- `ix_tools_embedding` — pgvector IVFFlat or HNSW index (deferred until >100 tools). Works with both local Docker and AWS RDS PostgreSQL 16.

### ToolCapability

Junction entity for many-to-many mapping between tools and capability tags.
A single tool can have multiple capabilities, and multiple tools can share
a capability.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `SERIAL` | PK | Auto-incrementing surrogate key. |
| `tool_id` | `VARCHAR(100)` | FK → tools.tool_id, ON DELETE CASCADE | Parent tool reference. |
| `capability` | `VARCHAR(100)` | NOT NULL | Capability tag (e.g., `financial_data`, `web_search`). |

**Constraints**:
- `UNIQUE(tool_id, capability)` — prevents duplicate tags per tool.

**Indexes**:
- `ix_tool_capabilities_capability` on `capability` — for tag-based filtering in search.

### ToolUsageLog

Append-only audit log of every tool invocation. Used for aggregating
statistics and debugging.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `SERIAL` | PK | Auto-incrementing surrogate key. |
| `tool_id` | `VARCHAR(100)` | FK → tools.tool_id | Tool that was invoked. |
| `agent_id` | `VARCHAR(100)` | NULLABLE | Agent that invoked the tool (e.g., `researcher`). |
| `session_id` | `VARCHAR(100)` | NULLABLE | Research session ID for correlation. |
| `latency_ms` | `FLOAT` | NOT NULL | Invocation latency in milliseconds. |
| `success` | `BOOLEAN` | NOT NULL | Whether the invocation succeeded. |
| `error_message` | `TEXT` | NULLABLE | Error details if `success = false`. |
| `invoked_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | Timestamp of invocation. |

**Indexes**:
- `ix_tool_usage_logs_tool_id` on `tool_id` — for per-tool aggregation.
- `ix_tool_usage_logs_invoked_at` on `invoked_at` — for time-range queries.

## State Transitions

### Tool Status

```text
active ──► degraded ──► unhealthy
  ▲            │             │
  │            ▼             │
  └──── active ◄─────────────┘
                             │
active ──► deprecated ───────┘ (terminal, manual only)
```

- `active → degraded`: Health check responds but exceeds 500ms.
- `degraded → unhealthy`: Health check fails or connection refused.
- `unhealthy → active`: Health check passes within budget.
- `degraded → active`: Health check passes within budget.
- `active → deprecated`: Manual operator action only.

## Validation Rules

- `tool_id`: Must match `^[a-z0-9][a-z0-9-]*[a-z0-9]$` (lowercase
  alphanumeric with hyphens, 3-100 chars).
- `name`: 1-255 characters, non-empty after trimming.
- `description`: 10+ characters (must be meaningful for embedding).
- `version`: Must match semver pattern `^\d+\.\d+\.\d+$`.
- `endpoint`: Must be a valid HTTP/HTTPS URL.
- `input_schema` / `output_schema`: Must be valid JSON Schema objects
  (validated at registration).
- `capabilities`: Each tag must match `^[a-z][a-z0-9_]*$` (lowercase
  snake_case).
