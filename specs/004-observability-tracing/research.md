# Research: 004 Agent observability and tracing

Consolidates technology choices and resolves planning unknowns for Langfuse + structlog + registry usage alignment with [spec.md](./spec.md).

---

## R1 — Langfuse integration surface for LLM vs custom spans

**Decision**: Keep **LangChain `CallbackHandler`** (`langfuse.langchain.CallbackHandler`) for **LLM generations** attached to `ainvoke(..., config={"callbacks": [...]})` in nodes. Add **`langfuse`** Python SDK **client** (or `Langfuse()` context manager) for **explicit spans** on **agent routing** (e.g. critic → researcher vs synthesizer) and optionally to **wrap tool invocations** where the default callback coverage is insufficient.

**Rationale**: CallbackHandler is already wired in the codebase pattern; it captures model metadata Langfuse expects. Routing decisions are not always visible as distinct spans unless we emit them explicitly.

**Alternatives considered**: OTEL-only export (rejected: constitution and spec target Langfuse for LLM UX); rely on logs only for routing (rejected: spec **FR-003** requires trace-oriented routing data).

---

## R2 — Truncated trace payloads (model + tool)

**Decision**: Implement a small **`truncate_for_trace(text: str | None, max_chars: int) -> str`** (and optional redaction hook) in `agents/tracing.py` or `agents/observability_redact.py`, default **max_chars** from `AgentConfig` (e.g. `trace_excerpt_max_chars`, default **2048**). Apply truncation to strings **before** they are sent to Langfuse for **custom spans** and, where the SDK allows, **enrich or replace** generation inputs/outputs via:

1. **Preferred**: Subclass or wrap callback behavior to trim `on_llm_end` / chain payloads, **or**
2. Use Langfuse **masking / metadata-only** patterns documented for the installed `langfuse` major version, **or**
3. Store full text only in application logs when policy allows (still subject to **FR-007**), never full bodies in Langfuse when over cap.

**Rationale**: Spec clarifications require truncated excerpts + metadata, not full bodies.

**Alternatives considered**: Full prompts in Langfuse with org-level scrubbing only (rejected: contradicts clarified spec).

---

## R3 — Best-effort export and registry usage

**Decision**: **No persistent queue**. On Langfuse flush/send failure: log structured warning once per batch pattern, drop. **`RegistryClient.log_usage`** keeps **try/except** with warning (already non-blocking); ensure no caller `await`s retry loops.

**Rationale**: Matches clarification Option A and **FR-008**.

**Alternatives considered**: Bounded Redis queue (deferred: out of spec scope).

---

## R4 — structlog full run path

**Decision**: At **`invoke_research_graph`** entry: `structlog.contextvars.bind_contextvars(session_id=..., trace_id=..., client_session_id=..., agent_id="graph")` (or `system` until node runs), then each node uses **`get_logger(trace_id, session_id, agent_id)`** as today. **Registry** service: keep **RequestLoggingMiddleware** binding `trace_id` + header session; if registry is not the run entrypoint, treat header `x-session-id` as **client hint** only when a future route starts a graph—until then, document alignment in [contracts/correlation-and-logs.md](./contracts/correlation-and-logs.md).

**Rationale**: Spec **FR-005** requires entry → graph → tools; graph invoke is the practical entrypoint in-repo today.

---

## R5 — Canonical `session_id` vs `client_session_id`

**Decision**: **`invoke_research_graph`** (or `merge_graph_defaults` / `validate_graph_input`) generates a **new UUID** for **`session_id`** when starting a run unless internal tests pin IDs. If input contains **`client_session_id`** (optional new state field) or legacy client value passed in, **do not** copy it into `session_id`; store **`client_session_id`** in state and bind to structlog + Langfuse trace metadata.

**Rationale**: Clarified spec **FR-004**.

**Alternatives considered**: Use client `session_id` as canonical (rejected by user clarification).

**Migration note**: `validate_graph_input` currently requires a non-empty `session_id` from the caller—implementation must **change** to server generation + optional client hint to avoid breaking spec compliance.

---

## R6 — `trace_id` semantics

**Decision**: Keep **`trace_id`** as UUID string in **ResearchState** for correlation with logs and Langfuse **trace** root; ensure Langfuse handler receives the same trace id via **session_id / trace_id** metadata (`LANGFUSE_TRACE_ID` patterns or handler config per Langfuse v4 docs). Exact env/session mapping is implementation detail validated in tests.

**Rationale**: Spec requires stable correlation across logs and traces; existing state already has `trace_id`.

---

## R7 — Testing strategy

**Decision**: Unit tests: truncation, bootstrap IDs, structlog capture. Integration: graph run with `langfuse_enabled=False` (default in tests) to assert **log keys**; optional mocked Langfuse client for span call counts when stable.

**Rationale**: CI must not require live Langfuse.
