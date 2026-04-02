# Implementation Plan: Agent observability and tracing

**Branch**: `004-observability-tracing` | **Date**: 2026-04-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-observability-tracing/spec.md` — Langfuse trace integration for LLM calls, tool invocations, and agent decisions with correlation IDs; structlog JSON logging with `session_id` / `agent_id` / `trace_id`; tool usage logging to the registry; clarifications on best-effort export, truncated trace payloads, full-path logging, and server-issued `session_id` with optional `client_session_id`.

## Summary

Harden and complete observability across the **research run path** to match spec **FR-001–FR-008**: Langfuse spans for LLM, tools, and **routing decisions** with shared trace/session correlation; **structlog** JSON logs with bound context from **API or job entry** through graph and tools; **truncated, redacted** payloads in external traces (not full bodies); **server-generated canonical `session_id`** with optional **`client_session_id`** metadata; registry **`POST /tools/usage-log`** remains **non-blocking** (already best-effort) and aligned with spec **FR-008**. Implementation builds on existing `agents/tracing.py`, node-level Langfuse callbacks, `RegistryClient.log_usage`, and registry `RequestLoggingMiddleware`.

## Technical Context

**Language/Version**: Python 3.9+  
**Primary Dependencies**: LangGraph >=1.1, langchain-core >=0.3, langchain-google-genai >=2.0, httpx, **langfuse >=2.0** (CallbackHandler + optional Langfuse client for custom spans), **structlog >=24**  
**Storage**: No new storage. Registry MySQL for usage logs (existing). Langfuse (self-hosted or cloud) for trace export.  
**Testing**: pytest, pytest-asyncio; `structlog.testing.capture_logs`; integration tests against graph with Langfuse disabled or mocked.  
**Target Platform**: Linux server / local dev (same as registry + agents).  
**Project Type**: Backend library (`agents/`) + optional alignment of registry HTTP middleware (`registry/`).  
**Performance Goals**: Observability MUST NOT materially delay runs (spec **FR-008** / best-effort drop). Trace payload truncation limits outbound size and Langfuse ingestion cost.  
**Constraints**: No unbounded buffering for failed exports; at most one in-process retry; truncation limits configurable with safe defaults (see `research.md`).  
**Scale/Scope**: Single-flight graph today; correlation per run; no cross-session sampling requirement in spec.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| I | Dynamic Tool Architecture | **PASS** | Usage logging via registry API; tools discovered at runtime unchanged. |
| II | Layered Independence | **PASS** | Observability code lives in `agents/` and `registry/` with existing boundaries; no engine → conversational imports. |
| III | Agent Autonomy with Bounded Scope | **PASS** | Tracing/logging are cross-cutting; no agent responsibility blur. |
| IV | Test-First with Contract Testing | **PASS** | Extend `tests/unit/test_observability.py`, add/extend integration checks for log fields and span hooks; document log field contract under `contracts/`. |
| V | Observability as Infrastructure | **PASS** | This feature directly implements Principle V; adds routing spans + truncation policy + full-path structlog + canonical session rules per clarified spec. |
| VI | Performance Under Budget | **PASS** | Non-blocking export and truncation prevent dominating the 60s graph budget; failures logged, not swallowed silently (existing patterns + **FR-007**). |
| VII | Session Continuity & Research Accumulation | **PASS** | Canonical `session_id` server-issued; `client_session_id` preserved for cross-turn/client correlation without colliding internal IDs. |

**Gate result**: **ALL PASS** — proceed.

## Project Structure

### Documentation (this feature)

```text
specs/004-observability-tracing/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── correlation-and-logs.md
└── tasks.md             # Phase 2 (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
agents/
├── tracing.py              # Langfuse handler, structlog helpers, truncation/redaction helpers, optional Langfuse client spans
├── graph.py                # invoke_research_graph: bind contextvars, root trace metadata, bootstrap session_id / client_session_id
├── state.py                # ResearchState: optional client_session_id; validate_graph_input / merge_graph_defaults alignment
├── config.py               # Observability knobs: excerpt limits, optional langfuse flush behavior
├── nodes/
│   ├── researcher.py       # Ensure callbacks + routing span or log events
│   ├── analyst.py
│   ├── critic.py           # route_after_critic: observable routing decision
│   └── synthesizer.py
└── tools/
    ├── registry_client.py  # log_usage: already non-blocking; ensure correlation fields passed
    └── discovery.py        # Tool spans + usage per attempt (already partially instrumented)

registry/
└── middleware/
    └── logging.py          # Optional: bind client_session_id from header; document canonical session for routes that start runs

tests/
├── unit/
│   └── test_observability.py   # Correlation, truncation helpers, session bootstrap
└── integration/
    └── test_research_graph_flow.py  # Log/trace assertions where feasible
```

**Structure Decision**: Single Python package layout under `agents/` as today; registry middleware only if a FastAPI route in this repo becomes the **authoritative** run entrypoint—otherwise graph bootstrap in `invoke_research_graph` (or a thin API wrapper added later) owns canonical `session_id`.

## Complexity Tracking

No Constitution violations. Table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 & Phase 1 Outputs

| Artifact | Path |
|----------|------|
| Research decisions | [research.md](./research.md) |
| Observability data model | [data-model.md](./data-model.md) |
| Correlation & log contracts | [contracts/correlation-and-logs.md](./contracts/correlation-and-logs.md) |
| Operator quickstart | [quickstart.md](./quickstart.md) |

**Agent context**: Updated via `.specify/scripts/bash/update-agent-context.sh cursor-agent` after this plan.
