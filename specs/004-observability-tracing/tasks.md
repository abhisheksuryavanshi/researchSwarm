# Tasks: Agent observability and tracing (004)

**Input**: Design documents from `/specs/004-observability-tracing/`  
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/correlation-and-logs.md](./contracts/correlation-and-logs.md)

**Tests**: Included per Research Swarm Constitution (Principle IV — test-first / contract tests) and [spec.md](./spec.md) acceptance scenarios.

**Organization**: Phases follow user story priority (US1 P1 → US2 P2 → US3 P2), after shared foundation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no ordering dependency within the same phase)
- **[Story]**: `[US1]` / `[US2]` / `[US3]` for user-story phases only

---

## Phase 1: Setup (Shared)

**Purpose**: Config knobs for truncation and observability (no new dependencies expected).

- [x] T001 [P] Add `trace_excerpt_max_chars: int` (default `2048`) and any related optional fields to `AgentConfig` in `agents/config.py` per [research.md](./research.md) R2

---

## Phase 2: Foundational (Blocking)

**Purpose**: Session/trace bootstrap, truncation helpers, structlog context binding — **required before any user story**.

**⚠️ CRITICAL**: No user story phase work until this phase completes.

- [x] T002 Implement `truncate_for_trace(text, max_chars)` and a single place for future redaction hooks in `agents/tracing.py` (export for use from nodes and tools)
- [x] T003 Add optional `client_session_id: str | None` to `ResearchState` in `agents/state.py` per [data-model.md](./data-model.md)
- [x] T004 Update `validate_graph_input` and `merge_graph_defaults` in `agents/state.py` so canonical `session_id` is **server-generated UUID** at run start; map caller-supplied legacy `session_id` intent to `client_session_id` only; keep `trace_id` UUID validation per [spec.md](./spec.md) FR-004
- [x] T005 At the start/end of `invoke_research_graph` in `agents/graph.py`, bind `structlog.contextvars` with `session_id`, `trace_id`, `client_session_id`, and a shell `agent_id` (e.g. `"graph"`) before `compiled.ainvoke`; clear or reset context in `finally` as appropriate
- [x] T006 [P] Update `tests/unit/test_observability.py` and `tests/conftest.py` for new session bootstrap rules (canonical vs `client_session_id`); add unit tests for `truncate_for_trace` edge cases (empty, over limit)

**Checkpoint**: Foundation ready — graph runs can emit consistent correlation context.

---

## Phase 3: User Story 1 — End-to-end trace (Priority: P1) 🎯 MVP

**Goal**: Langfuse trace hierarchy with model, tool, and routing spans; truncated payloads; shared correlation (spec **FR-001–FR-004**, **SC-001**).

**Independent Test**: Complete one research graph run with Langfuse enabled (or mocked client); trace shows model + tool + routing events under one root; payloads are truncated excerpts + metadata.

### Tests for User Story 1

- [x] T007 [P] [US1] Extend `tests/unit/test_observability.py` with mocked Langfuse / callback assertions for routing or root metadata when `langfuse_enabled=True`
- [x] T008 [US1] Extend `tests/integration/test_research_graph_flow.py` to assert successful run after session bootstrap change and capture correlation ids in logs or mocks

### Implementation for User Story 1

- [x] T009 [US1] Wire Langfuse root trace metadata (`session_id`, `trace_id`, `client_session_id`) in `agents/tracing.py` and/or `agents/graph.py` using Langfuse v4 patterns (handler + optional `Langfuse` client) per [research.md](./research.md) R1 and R6
- [x] T010 [P] [US1] Emit explicit trace span (or Langfuse observation) for critic routing decision in `agents/nodes/critic.py` covering `route_after_critic` outcomes (spec **FR-003**)
- [x] T011 [P] [US1] Ensure LLM `ainvoke` uses `get_tracer` callbacks and applies truncation to Langfuse-visible content in `agents/nodes/researcher.py`
- [x] T012 [P] [US1] Same LLM callback + truncation alignment in `agents/nodes/analyst.py`
- [x] T013 [P] [US1] Same LLM callback + truncation alignment in `agents/nodes/critic.py` (LLM portions distinct from T010 routing span)
- [x] T014 [P] [US1] Same LLM callback + truncation alignment in `agents/nodes/synthesizer.py`
- [x] T015 [P] [US1] Apply tool + nested LLM truncation for Langfuse in `agents/tools/discovery.py` (tool spans per **FR-002**)

**Checkpoint**: US1 trace story satisfied — MVP demo in Langfuse UI.

---

## Phase 4: User Story 2 — Structured logs full path (Priority: P2)

**Goal**: JSON structlog lines from graph entry through nodes/tools with `session_id`, `agent_id`, `trace_id` / `client_session_id` when defined (spec **FR-005**, **SC-002**).

**Independent Test**: `capture_logs` (or log sink) shows required keys on entry log, at least one node log, and tool path; client hint appears only as `client_session_id`.

### Tests for User Story 2

- [x] T016 [P] [US2] Add `tests/contract/test_observability_log_shape.py` asserting JSON log records include correlation keys defined in [contracts/correlation-and-logs.md](./contracts/correlation-and-logs.md) for a minimal graph invocation

### Implementation for User Story 2

- [x] T017 [P] [US2] Update `registry/middleware/logging.py` to bind `client_session_id` from `X-Session-ID` explicitly (and keep `trace_id` from `X-Trace-ID`); document that canonical `session_id` for a research run is issued by the graph entrypoint, not the registry edge
- [x] T018 [US2] Add explicit `invoke_research_graph` start/complete structured events in `agents/graph.py` with bound contextvars; audit `agents/nodes/researcher.py`, `agents/nodes/analyst.py`, `agents/nodes/critic.py`, `agents/nodes/synthesizer.py`, and `agents/tools/discovery.py` for entry/exit or error logs using `get_logger` / context-bound structlog so no node omits correlation when context is active

**Checkpoint**: US2 log filtering story satisfied end-to-end.

---

## Phase 5: User Story 3 — Tool usage in registry (Priority: P2)

**Goal**: Every integrated tool invocation logs canonical `session_id` and outcomes via `POST /tools/usage-log` without blocking (spec **FR-006**, **FR-008**, **SC-003**).

**Independent Test**: Mock `httpx` registry client captures usage POST body with canonical `session_id`, `agent_id`, latency, success/failure for success and failure paths.

### Tests for User Story 3

- [x] T019 [P] [US3] Extend `tests/unit/test_tool_discovery.py` or add `tests/unit/test_registry_usage_context.py` to assert `log_usage` payloads use canonical `session_id` from run state, not `client_session_id` alone

### Implementation for User Story 3

- [x] T020 [US3] Review and adjust `RegistryClient.log_usage` in `agents/tools/registry_client.py` docstring and call signature usage so all callers pass canonical `session_id` from graph state; keep non-blocking exception handling per **FR-008**
- [x] T021 [P] [US3] Audit `agents/tools/discovery.py` (and any other tool invoke sites) so each attempt records usage with correct `agent_id`, canonical `session_id`, and per-attempt success/failure

**Checkpoint**: US3 registry usage story satisfied.

---

## Phase 6: Polish & Cross-Cutting

**Purpose**: Docs, global test fixes, quality gates.

- [x] T022 [P] Update all remaining test modules that construct graph input (`tests/integration/test_research_graph_flow.py`, `tests/unit/test_tool_discovery.py`, `tests/unit/test_researcher_node.py`, etc.) to comply with new `session_id` / `client_session_id` bootstrap rules
- [x] T023 [P] Refresh `specs/004-observability-tracing/quickstart.md` with final env vars, header names, and verification steps matching implementation
- [x] T024 Run `pytest` and `ruff check .` from repository root; fix any regressions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** → **Phase 2** → **Phases 3–5** (US1 → US2 → US3 recommended order; US2/US3 can overlap after Phase 2 if US1 callbacks are stable)
- **Phase 6** after all desired user stories complete

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|--------|
| US1 (P1) | Phase 2 | Core Langfuse + truncation |
| US2 (P2) | Phase 2; soft-dep on US1 | Can proceed in parallel once contextvars + bootstrap exist |
| US3 (P2) | Phase 2; aligns with US1 tool paths | Usage logs should use same canonical `session_id` as traces/logs |

### Parallel Opportunities

- **Phase 1**: T001 alone or with doc tasks
- **Phase 2**: T006 parallel with T002–T005 after interfaces stable (or T006 after T004–T005)
- **US1**: T007 ∥ T010–T015 (different files); T009 before T010–T015 if it defines shared helper API
- **US2**: T016 ∥ T017
- **US3**: T019 ∥ T021 after T020 contract clear
- **Phase 6**: T022 ∥ T023

### Parallel Example: User Story 1 (implementation)

```bash
# After T009 lands, in parallel:
# T010 agents/nodes/critic.py (routing span)
# T011 agents/nodes/researcher.py
# T012 agents/nodes/analyst.py
# T013 agents/nodes/critic.py (LLM spans)
# T014 agents/nodes/synthesizer.py
# T015 agents/tools/discovery.py
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phase 1–2 (T001–T006)
2. Complete Phase 3 (T007–T015) — first vertical trace in Langfuse
3. **STOP and VALIDATE** against **SC-001**

### Incremental Delivery

1. Add Phase 4 (US2) — operators can grep JSON logs by session/trace
2. Add Phase 5 (US3) — registry usage matches canonical session
3. Phase 6 — repo-wide green tests and quickstart

---

## Notes

- Langfuse export failures MUST remain non-blocking (**FR-008**); do not add unbounded queues.
- Truncation defaults live on `AgentConfig` (T001); use them from T002 onward.
- Total tasks: **24** (T001–T024)
