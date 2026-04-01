# Data model: Observability context (004)

Logical entities for correlation, logging, and tracing. Not all fields require new DB tables.

## Run correlation (in-process + Langfuse + logs)

| Field | Type | Source of truth | Notes |
|-------|------|-----------------|-------|
| `session_id` | UUID string | **Server** at run start | Canonical id for spec **FR-004** / **SC-002** |
| `client_session_id` | string \| null | Client header/body (optional) | Auxiliary; never replaces `session_id` |
| `trace_id` | UUID string | Server at run start (or propagated) | Root trace correlation; aligns with structlog `trace_id` |
| `agent_id` | string | Node name or fixed role id | e.g. `researcher`, `analyst`, `critic`, `synthesizer`, `tool_discovery` |

## ResearchState extensions (`agents/state.py`)

| Field | Required | Description |
|-------|----------|-------------|
| `session_id` | Yes | Canonical server-generated session |
| `client_session_id` | No | Optional client-supplied hint |
| `trace_id` | Yes | Trace root id (existing) |
| … | | Other existing fields unchanged |

**Validation rules (target)**:

- `trace_id`: valid UUID string (existing).
- `session_id`: valid UUID string **set by bootstrap**, not accepted from untrusted caller as authoritative (callers may pass hint only via `client_session_id`).
- `client_session_id`: optional string; max length TBD in implementation (e.g. 128 chars) to avoid log/trace bloat.

## Span types (Langfuse / trace UI)

| Span kind | Typical attributes | Payload policy |
|-----------|-------------------|----------------|
| `llm` / generation | model, latency_ms, token counts | Truncated redacted excerpts per **FR-001** |
| `tool` | tool_id, success, latency_ms | Truncated redacted input/output excerpts per **FR-002** |
| `routing` / `decision` | from_node, to_node, reason summary | Metadata-first; text truncated per **FR-003** |

## Structured log record (JSON)

Minimum keys when context is active (see [contracts/correlation-and-logs.md](./contracts/correlation-and-logs.md)):

- `session_id` (canonical)
- `agent_id`
- `trace_id`
- `client_session_id` (optional, when provided)
- `event` / `message` / standard structlog keys (`timestamp`, `level`, …)

## Tool usage record (registry)

Existing `POST /tools/usage-log` body (see registry router): `tool_id`, `agent_id`, `session_id`, `latency_ms`, `success`, `error_message`. **`session_id` SHOULD be the canonical** server session id for consistency with traces/logs.

## Relationships

- One **trace** (`trace_id`) per graph run (single-flight today).
- Many **spans** (LLM, tools, routing) under that trace.
- Many **log lines** sharing the same `trace_id` + `session_id` for the run.
- Many **usage records** per run (one per tool invocation attempt, per existing product behavior).
