# Contract: Correlation identifiers and structured logs

**Feature**: [spec.md](../spec.md)  
**Consumers**: Agent graph, registry HTTP service, operators / log aggregators, Langfuse.

## Canonical identifiers

| Identifier | Semantics |
|------------|-----------|
| `session_id` | **Server-issued** UUID for one research run. Single source of truth for registry usage logs and internal correlation. |
| `client_session_id` | Optional string supplied by a client; stored in state, structlog context, and Langfuse trace **metadata** only. |
| `trace_id` | UUID for the root trace; must match across structlog and Langfuse for that run. |
| `agent_id` | Logical actor: graph node name or tool subsystem name (`tool_discovery`, etc.). |

## HTTP headers (informative)

Existing registry middleware uses:

- `X-Trace-ID` — request correlation; echoed on response.
- `X-Session-ID` — **legacy**: treated as session hint at registry edge; **when this feature fully applies to a run entrypoint**, the value MUST map to **`client_session_id`**, not canonical `session_id`, unless the entrypoint is updated to return a new canonical id (e.g. response header `X-Session-ID` = server session).

Document the chosen header contract in the public API when the research HTTP endpoint lands; until then, **library callers** use `invoke_research_graph` state fields.

## Structured JSON log contract

Each log line emitted through structlog with active run context **SHOULD** include:

```json
{
  "event": "string",
  "level": "info",
  "timestamp": "ISO-8601",
  "trace_id": "uuid",
  "session_id": "uuid",
  "agent_id": "string",
  "client_session_id": "string or omitted"
}
```

**Unknown values**: Per spec User Story 2 — omit key or use explicit sentinel (documented in implementation, e.g. `agent_id`: `"unknown"` only if truly unresolvable).

## Langfuse trace metadata

Trace or root span **SHOULD** include tags/metadata:

- `session_id` = canonical server id
- `client_session_id` when present
- `trace_id` aligned with logs (if not implicit)

## Registry usage log

`POST /tools/usage-log` JSON:

- `session_id` **MUST** be the **canonical** server `session_id` for that run when available (not the client hint alone).

## Non-blocking failure behavior

- Failed Langfuse export: **no retry** beyond optional single in-process attempt; **no unbounded queue** (**FR-008**).
- Failed usage log: response to user/tool path **succeeds or fails based on tool logic only**; logging failure is a warning log only.
