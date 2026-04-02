# Quickstart: Observability (004)

Verify Langfuse + structlog + registry usage for the research graph.

## Prerequisites

- Python 3.9+, project deps installed (`uv sync`).
- Optional: running **Langfuse** (see root `README.md` / docker-compose) and env vars:
  - `LANGFUSE_PUBLIC_KEY`
  - `LANGFUSE_SECRET_KEY`
  - `LANGFUSE_HOST` (e.g. `http://localhost:3000`)
- Optional: **`TRACE_EXCERPT_MAX_CHARS`** (or `AgentConfig.trace_excerpt_max_chars`, default `2048`) caps text sent in Langfuse spans/generations.

## Enable Langfuse in agent config

```python
from agents.config import AgentConfig

cfg = AgentConfig.model_validate({
    "langfuse_enabled": True,
    "langfuse_public_key": "...",
    "langfuse_secret_key": "...",
    "langfuse_host": "http://localhost:3000",
    "trace_excerpt_max_chars": 2048,
})
```

## Run the graph

Use `default_graph_context(cfg)` and `invoke_research_graph` as in [specs/003-dynamic-tool-binding/quickstart.md](../003-dynamic-tool-binding/quickstart.md).

**Correlation bootstrap** (library entrypoint):

- **`trace_id`**: required; must be a UUID string (caller supplies root trace id).
- **`session_id`** (legacy): optional client hint; if provided, it is stored as **`client_session_id`** only. The **canonical** `session_id` for the run is always a **new server-generated UUID** in merged state.
- **`client_session_id`**: optional explicit client hint (same semantics as legacy `session_id`; if both are set, `client_session_id` wins for the hint).

`invoke_research_graph` binds structlog contextvars (`session_id`, `trace_id`, `client_session_id`, `agent_id="graph"`) for the duration of the run.

## Registry HTTP edge (informative)

`RequestLoggingMiddleware` binds:

- `trace_id` from `X-Trace-ID` (or generated UUID)
- `client_session_id` from `X-Session-ID` (optional)

Canonical `session_id` for a research run is **not** the registry header; it is issued when the graph starts.

## Validate structured logs (no Langfuse required)

```bash
cd /path/to/researchSwarm
pytest tests/unit/test_observability.py tests/contract/test_observability_log_shape.py -q
```

With `capture_logs`, assert `trace_id`, canonical `session_id`, optional `client_session_id`, and node / graph events appear in output.

## Validate traces

1. Enable Langfuse and run one successful graph invocation.
2. Open Langfuse UI → Traces.
3. Confirm one trace per run (aligned with `trace_id`), `langfuse_session_id` metadata matching canonical `session_id`, nested LLM generations, **`route_after_critic`** span, tool spans from tool discovery, and truncated payloads where excerpts exceed the configured cap.

## Validate registry usage

With registry API reachable and a tool invoked:

- Check `tool_usage_logs` for rows with matching **canonical** `session_id` (from graph state), `agent_id`, `latency_ms`, `success`.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| No traces in Langfuse | Keys/host; `langfuse_enabled`; network; **FR-008** drops on failure |
| Logs missing `session_id` | Contextvars not bound at `invoke_research_graph` entry |
| Duplicate session confusion | Compare `client_session_id` (hint) vs canonical `session_id` in logs and usage rows |
