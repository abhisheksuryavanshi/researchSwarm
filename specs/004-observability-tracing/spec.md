# Feature Specification: Agent observability and tracing

**Feature Branch**: `004-observability-tracing`  
**Created**: 2026-04-01  
**Status**: Draft  
**Input**: User description: "Add Observability infrastructure — Langfuse trace integration for all LLM calls, tool invocations, and agent decisions with correlation IDs; structlog JSON logging with session_id/agent_id/trace_id; tool usage logging to the registry."

## Clarifications

### Session 2026-04-01

- Q: When trace/log export to the observability backend fails, what runtime policy should apply? → A: Best-effort drop (Option A): do not block or materially delay agent work; discard failed export batches after at most one optional in-process retry; no persistent queue and no unbounded buffering.
- Q: For language-model spans, what message body should be captured in traces (after redaction)? → A: Option B—**truncated** redacted excerpts of prompts/responses plus **metadata** (e.g. model id, latency, token counts); not full message bodies.
- Q: For tool invocation spans, what should be stored in the external trace (after redaction)? → A: Option A—**same policy as model spans**: truncated redacted excerpts of inputs/outputs plus metadata (tool identity, latency, outcome).
- Q: Which components must emit structured JSON logs with correlation fields when context exists? → A: Option A—**full run path**: API or job entry, graph execution, and tool layers all bind and emit `session_id`, `agent_id`, and trace correlation when a session/trace context is active.
- Q: Who supplies `session_id`, and what if the client sends one? → A: **Server-generated canonical `session_id`** at run start (Option A baseline). If the client supplies a session identifier, the system **MUST retain it as auxiliary metadata** (e.g. `client_session_id` or a documented equivalent) on traces and structured logs where applicable; it **MUST NOT** replace the canonical `session_id` used for internal correlation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — End-to-end trace for a research run (Priority: P1)

A platform engineer or operator receives a report that a research session behaved incorrectly. They open the observability trace view for that session and see a single correlated timeline: each language-model interaction, each tool execution, and each agent routing or decision step, all linked by shared correlation identifiers so they can follow cause and effect without stitching separate systems by hand.

**Why this priority**: Without correlated traces, debugging multi-step agent workflows is slow and error-prone. This is the primary value of the feature.

**Independent Test**: Run a standard research graph flow through to completion, then locate one trace (or equivalent correlated view) that contains spans or events for at least one model call, one tool invocation, and one agent decision, all sharing the same correlation identifier family.

**Acceptance Scenarios**:

1. **Given** a research session that completes normally, **When** an operator looks up that session in the trace UI, **Then** they see model calls, tool invocations, and agent decisions as distinct observability events within one correlated hierarchy.
2. **Given** multiple concurrent sessions, **When** an operator opens traces for two different sessions, **Then** each session’s events are isolated by correlation identifiers and do not cross-contaminate the other’s view.
3. **Given** a session that invokes a tool after a model call, **When** the operator inspects the trace, **Then** the tool span (or equivalent) is clearly associated with the same session and trace correlation context as the preceding model span.
4. **Given** a model call with long prompts or responses, **When** the operator opens the corresponding model span, **Then** the trace shows **truncated** redacted text excerpts and **metadata** (e.g. model identifier, latency, token counts)—not necessarily the full raw messages.
5. **Given** a tool returns a large payload, **When** the operator opens the tool span, **Then** the trace shows **truncated** redacted excerpts of arguments/results and **metadata** (tool identity, latency, outcome)—not full raw payloads.

---

### User Story 2 — Structured logs for filtering and incident response (Priority: P2)

During an incident, an operator streams or exports application logs and filters by session, agent, or trace correlation. From the **API or job entry** through **graph execution** and **tool** layers, every relevant log line is machine-parseable (JSON) and includes `session_id`, `agent_id`, and `trace_id` (or equivalent trace correlation fields) when those dimensions are known for the active run, so log aggregation tools can slice data without custom parsers.

**Why this priority**: Traces answer “what happened in order”; logs answer “what else was said around it” and integrate with existing alerting stacks. It is second priority after trace correlation.

**Independent Test**: Start a research run via the supported entrypoint (HTTP API or job runner), execute a bounded agent workflow, capture stdout or centralized log sink output, and verify that emitted JSON log records include the required identifiers on representative events at **entry**, **graph step**, **tool wrapper**, and **model gateway** (or equivalent).

**Acceptance Scenarios**:

1. **Given** an agent step runs within a known session and agent identity, **When** a log line is emitted for that step, **Then** the line is valid JSON and includes `session_id` and `agent_id`.
2. **Given** trace correlation is active for a run, **When** log lines are emitted during that run, **Then** they include a trace correlation field (`trace_id` or equivalent) consistent with the active trace.
3. **Given** a component that cannot determine one of the identifiers, **When** it logs, **Then** it either omits that field with a documented sentinel or marks it explicitly unknown rather than inventing a value (documented behavior in assumptions if needed).
4. **Given** a research run is started through the public API or job entry, **When** the entrypoint logs the start of work, **Then** the line is valid JSON and includes `session_id`, `agent_id` (or explicit unknown), and trace correlation once the trace context is established for that run.
5. **Given** the client includes its own session hint in the request, **When** logs and trace metadata are emitted for that run, **Then** the canonical `session_id` is the server-generated value and the client value appears only under the documented auxiliary field (e.g. `client_session_id`), not as `session_id`.

---

### User Story 3 — Tool usage visibility in the registry (Priority: P2)

Operations or governance needs a definitive record of which tools were used, when, and with what outcome. Every tool invocation performed through the agent stack is recorded with the tool registry’s usage logging capability (aligned with existing registry contracts), including enough context to tie usage back to session and agent where the registry supports it.

**Why this priority**: Registry usage supports cost, compliance, and capacity planning; it complements traces and logs.

**Independent Test**: Invoke a tool from an agent path, then query or inspect registry usage records and confirm a new entry exists with expected identifiers, timing, and success or failure status.

**Acceptance Scenarios**:

1. **Given** a successful tool call from an agent, **When** the call completes, **Then** the registry receives a usage log entry with success status and latency or duration where applicable.
2. **Given** a failed tool call (e.g., timeout or error response), **When** the failure is surfaced to the agent layer, **Then** the registry receives a usage log entry reflecting failure and the failure class where the API allows.
3. **Given** multiple tools in one session, **When** the session completes, **Then** each distinct invocation produces its own usage record (no silent merging that loses per-call auditability).

---

### Edge Cases

- Observability or trace export is temporarily unavailable (network or service outage): primary research functionality still completes; export uses **best-effort drop**—failed batches are not retried beyond at most one in-process attempt, are not queued without bound, and must not block or materially delay agent execution (see FR-008). Traces or log lines may be missing for that window.
- Registry usage API temporarily unavailable: same **non-blocking** policy applies to usage logging calls; invocations complete without waiting on registry durability. **SC-003** is asserted under acceptance conditions where the registry API is reachable.
- Session ends abruptly (process kill, OOM): last-known spans and logs should still be flushable where the platform allows; partial traces are acceptable if documented.
- Very high concurrency: correlation identifiers remain unique per session; no requirement in this spec for cross-session sampling reduction.
- Client sends a duplicate or reused “session” hint: canonical `session_id` remains unique per server-issued run; the hint is stored as metadata only and does not force id collisions in internal correlation.
- Tool invocations that bypass the registry-backed execution path: only invocations that go through the integrated stack are in scope for registry usage logging unless otherwise extended in a future feature.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST emit trace-oriented observability data for every language-model call in the agent execution path. Model spans MUST include **truncated, redacted** excerpts of prompts and responses (per organizational redaction policy and documented length limits—not full bodies) and MUST include **metadata** such as model identifier, latency, and token counts (or equivalents where the provider exposes them). Spans MUST attach correlation identifiers that tie model calls to the enclosing session and trace.
- **FR-002**: The system MUST emit trace-oriented observability data for every tool invocation in the agent execution path. Tool spans MUST include **truncated, redacted** excerpts of inputs and outputs (per organizational redaction policy and documented length limits—not full bodies), plus **metadata** including tool identity, outcome (success or failure), and timing, correlated to the same session and trace as related model and routing events—**aligned with the capture policy for model spans (FR-001)**.
- **FR-003**: The system MUST emit trace-oriented observability data for agent routing and decision points (e.g., which node or branch runs next) so operators can reconstruct control flow alongside model and tool activity.
- **FR-004**: The system MUST propagate a stable correlation identifier set from the start of a session (or request) through nested spans such that an operator can retrieve one hierarchical trace (or equivalent correlated view) per logical run. The authoritative **`session_id`** MUST be **generated by the server** when a research run begins. If the client supplies a session identifier, the system MUST persist it as **auxiliary metadata** only (documented field name such as `client_session_id`) on traces and structured logs where applicable; the client value MUST NOT overwrite or substitute for the canonical `session_id`.
- **FR-005**: The system MUST emit application logs as structured JSON records on the **full research-run path**: API or job entry, graph execution, and tool invocation layers MUST bind and emit `session_id`, `agent_id`, and trace correlation (`trace_id` or equivalent) on log events whenever a session/trace context is active for that run and the respective identifier is defined (see User Story 2 for unknown-field behavior).
- **FR-006**: The system MUST log every tool invocation executed via the integrated agent-to-registry path to the tool registry usage API (or successor contract), including identifiers and outcome information required by the existing registry specification.
- **FR-007**: The system MUST NOT log secrets, raw credentials, or full unredacted payloads where redaction policies exist; sensitive fields MUST be omitted or masked consistently across traces and logs.
- **FR-008**: When exporting traces or structured logs to an external observability backend, the system MUST NOT block or materially delay agent execution. Failed export batches MAY be dropped after at most one optional in-process retry; the system MUST NOT retain unbounded in-memory queues solely for observability export. The same non-blocking rule applies to registry usage logging HTTP calls: failures MUST NOT block tool completion or graph progression.

### Key Entities

- **Trace context**: Session-scoped and request-scoped identifiers that link spans and log lines (includes trace root id and parent/child relationships as exposed by the observability pipeline). **Canonical `session_id`** is always server-issued; an optional **client-supplied hint** is stored separately for cross-system lookup (see FR-004).
- **Span / trace event**: A single unit of work (model call, tool run, routing step) with start/end, attributes, and correlation to parent context. **Model spans** (FR-001) and **tool spans** (FR-002) carry truncated redacted excerpts of their respective inputs/outputs plus metadata, not full bodies.
- **Structured log record**: A JSON object with standard fields (`session_id`, `agent_id`, `trace_id` or equivalent) plus event-specific attributes and, when provided by the client, an auxiliary client session field (documented name, e.g. `client_session_id`) distinct from `session_id`.
- **Tool usage record**: A registry-persisted record of a tool invocation with timing, outcome, and correlation fields supported by the registry API.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In acceptance testing, 100% of sampled completed research runs yield a single trace hierarchy (or equivalent correlated trace collection) that includes at least one model event, one tool event (when a tool was invoked), and one agent routing or decision event, all sharing trace correlation with the session.
- **SC-002**: In acceptance testing, 100% of sampled structured application log records emitted **from API or job entry through graph and tool execution** include `session_id`, `agent_id`, and trace correlation fields whenever those values are defined for the context; fields are verifiably consistent with the active trace for that run.
- **SC-003**: In acceptance testing, with the registry API reachable, 100% of sampled tool invocations that go through the integrated stack produce a corresponding tool usage record in the registry within the same session window, with correct success or failure indication.
- **SC-004**: Operators can complete a documented “find root span for session X” drill for a seeded failing run in under five minutes using only trace and log tools (no ad-hoc code changes), measured in a scripted runbook test.

## Assumptions

- The product already targets a trace export path compatible with the organization’s chosen LLM observability stack; the user’s input names Langfuse as the integration target for planning and implementation, while this specification states outcomes in product-neutral terms except where field names (`session_id`, `agent_id`, `trace_id`) are explicit requirements. **`session_id` is always server-generated**; client-provided values are optional hints recorded under a separate documented key (FR-004).
- JSON logging refers to structured logs suitable for centralized log systems; the exact logger library is an implementation choice as long as output shape and fields meet FR-005. Correlation fields apply across the **full run path** (entry, graph, tools), not only inside graph nodes.
- Tool registry usage logging reuses existing API semantics from prior features; extensions to the API, if any, are small and backward compatible.
- Redaction and retention of trace and log payloads follow existing security guidelines; this feature does not redefine data classification but must respect it (FR-007).
- Degraded observability (export failures) must not block user-visible research results: **best-effort drop** for external trace/log export and for registry usage logging (FR-008), with no unbounded buffering.
