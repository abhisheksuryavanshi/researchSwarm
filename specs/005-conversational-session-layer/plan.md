# Implementation Plan: Conversational session layer

**Branch**: `005-conversational-session-layer` | **Date**: 2026-04-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-conversational-session-layer/spec.md` — Conversation Coordinator, Redis + **MySQL** session store, intent classification (new / refinement / reformat / meta-question), selective engine re-invocation, accumulated research state across turns, constraint propagation into `ResearchState`; clarifications on degraded storage mode, per-session FIFO, single-owner sessions, low-confidence clarification-first routing, and ambiguous denial (FR-016).

## Summary

Introduce a **conversational layer** package that owns **session lifecycle**, **per-session FIFO turn processing**, **intent classification with confidence gating**, and **dual persistence** (**Redis** working set, **MySQL** authoritative history—same engine family as the registry, typically the **existing registry database** with new session tables). The **Conversation Coordinator** routes each turn to the minimum engine work (full LangGraph run vs lightweight paths) and **merges** durable snapshots and constraints into **`ResearchState`** before calling the existing research engine. The engine package (`agents/`) gains **no imports** from the conversational package; the conversational layer **calls** `agents.graph` (or a thin façade) as today’s constitution requires. **Observability** (Langfuse, structlog) continues to use canonical `session_id` across turns.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: LangGraph >=1.1, langchain-core >=0.3, langchain-google-genai >=2.0 (or equivalent LLM for classification), **redis** (async client), **SQLAlchemy 2.0+ async**, **aiomysql** (MySQL async driver, already used by the registry), httpx (registry unchanged), langfuse >=2.0, structlog >=24  
**Storage**: **Redis** — active session working set, per-session lock/queue metadata, optional cache of latest snapshot id; **MySQL** — session rows, turn log, durable state snapshots (JSON columns), idempotency records (same technology as the tool registry; shared DB URL or dedicated MySQL instance per deployment)  
**Testing**: pytest, pytest-asyncio; Testcontainers or docker-compose fixtures for Redis + MySQL in integration tests; contract tests for session API schemas and coordinator routing decisions  
**Target Platform**: Linux server / local dev (same as registry + agents)  
**Project Type**: Backend **library/service boundary** — new top-level package `conversation/` (name final per tasks) + tests; optional FastAPI router if this repo exposes HTTP for sessions  
**Performance Goals**: Constitution VI — follow-up without full re-research faster than initial query (SC-003); session read path targets **< 50ms** P95 from Redis working set under normal load (aligned with constitution §Performance); classification step bounded (e.g. **< 2s** P95 for small model / single LLM call)  
**Constraints**: FR-012/FR-016 degraded and security behavior; FR-013 FIFO + idempotency; no engine → conversational imports (Principle II); tracing/logging on coordinator path (Principle V)  
**Scale/Scope**: Single-owner sessions; multi-tenant optional via `tenant_id` column; collaborative sessions **out of scope** (FR-014)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| I | Dynamic Tool Architecture | **PASS** | Coordinator does not embed tool lists; engine continues registry-backed discovery unchanged. |
| II | Layered Independence | **PASS** | New `conversation/` package; `agents/` **must not** import `conversation/`; coordinator invokes engine via public API only. |
| III | Agent Autonomy with Bounded Scope | **PASS** | **Conversation Coordinator** classifies and routes only; research/analysis/synthesis remain in engine nodes. |
| IV | Test-First with Contract Testing | **PASS** | Contract tests for session/turn payloads, coordinator routing table, and `ResearchState` merge rules; integration tests for multi-turn flows. |
| V | Observability as Infrastructure | **PASS** | Coordinator spans/logs with `session_id`, `agent_id` (coordinator role), `trace_id`; no silent failures. |
| VI | Performance Under Budget | **PASS** | Selective re-invocation + SC-003 style budgets; classification timeout/retry policy documented in `research.md`. |
| VII | Session Continuity & Research Accumulation | **PASS** | Persist transcript + snapshots; merge `constraints` and `accumulated_context` into engine input; `ResearchState` fields already exist in `agents/state.py` — coordinator **populates** them on continuation turns. |

**Gate result**: **ALL PASS** — proceed.

**Note (storage wording)**: Constitution §Performance mentions **MySQL** for durable artifacts; **005** uses **MySQL** for the **session durable store** as well, so operators manage **one database engine** for registry and session tables (separate logical schema/tables as needed). Redis remains the hot-path working set.

## Project Structure

### Documentation (this feature)

```text
specs/005-conversational-session-layer/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── session-api.md   # HTTP/session-turn contracts (if API exposed)
└── tasks.md             # Phase 2 (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
conversation/
├── __init__.py
├── config.py                 # Redis URL, MySQL URL (registry-aligned), timeouts, confidence thresholds
├── coordinator.py            # Orchestrates: load session → classify → route → invoke engine or short-circuit
├── intent.py                 # IntentClassifier: structured output + confidence + FR-015 branch
├── models.py                 # Pydantic: Session, Turn, IntentResult, DegradedMode flags
├── persistence/
│   ├── mysql_models.py       # SQLAlchemy 2.0 async models for session tables (MySQL)
│   ├── redis_store.py        # Working set, locks, optional queue pointers
│   └── mysql_store.py        # Durable sessions, turns, snapshots, idempotency (MySQL)
├── routing.py                # RoutePlan: which engine subgraph / entrypoint to run
├── merge.py                  # Build dict for invoke_research_graph from session + new user text
└── api/
    └── routes.py             # Optional FastAPI: POST /sessions, /sessions/{id}/turns

agents/
├── graph.py                  # Ensure continuation entry accepts caller-supplied session_id + merged state (no accidental re-mint on follow-up)
├── state.py                  # ResearchState — already has constraints, accumulated_context; document merge semantics

tests/
├── contract/
│   └── test_session_contracts.py
├── integration/
│   └── test_conversation_multi_turn.py
└── unit/
    ├── test_intent_classifier.py
    ├── test_coordinator_routing.py
    └── test_session_fifo.py
```

**Structure Decision**: Add **`conversation/`** as the conversational layer root (constitution naming). Keep **`agents/`** as the research engine; **dependency direction** is `conversation` → `agents`, never the reverse.

## Complexity Tracking

No constitution **principle** violations. Session durability is **additive MySQL tables** (alongside existing registry tables in the same database or a dedicated MySQL database); documented in [research.md](./research.md).

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 & Phase 1 Outputs

| Artifact | Path |
|----------|------|
| Research decisions | [research.md](./research.md) |
| Session data model | [data-model.md](./data-model.md) |
| Session / turn API contract | [contracts/session-api.md](./contracts/session-api.md) |
| Developer quickstart | [quickstart.md](./quickstart.md) |

**Agent context**: Updated via `.specify/scripts/bash/update-agent-context.sh cursor-agent` after this plan.
