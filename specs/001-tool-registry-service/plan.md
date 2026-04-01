# Implementation Plan: Tool Registry Service

**Branch**: `001-tool-registry-service` | **Date**: 2026-03-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-tool-registry-service/spec.md`

## Summary

Build a standalone FastAPI service backed by MySQL that serves as the
central tool catalog for the Research Swarm system. Agents discover tools at
runtime by querying this registry via capability tags or listing the full
catalog (so the LLM can select the right tool). The service provides
endpoints for registration, search/listing, LangChain-compatible binding,
proxied health checks, and usage statistics. It ships with 7 seeded tools.
Deployed on AWS (RDS MySQL, EC2), with Docker Compose for local
development.

## Technical Context

**Language/Version**: Python 3.9+
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0+ (async), aiomysql,
httpx, structlog, Pydantic v2, Alembic, uvicorn
**Storage**: MySQL 8.0 (local Docker / AWS RDS)
**Testing**: pytest, pytest-asyncio, httpx (TestClient)
**Target Platform**: AWS EC2 (production), Docker Compose (local dev)
**Project Type**: Web service (microservice)
**LLM Providers**: Google GenAI (default/testing free tier), OpenAI, Anthropic
via LiteLLM abstraction (used by agents in Phase 2+, not by the registry).
**Performance Goals**: Search < 100ms, bind < 200ms, registration < 500ms
**Constraints**: < 200ms p95 for search, health check proxy timeout 500ms
**Scale/Scope**: ~50-200 registered tools, single-instance deployment in v1
**Infrastructure**: AWS RDS MySQL 8.0, EC2 t3.micro/small,
ElastiCache Redis (Phase 5). Docker Compose for local dev parity.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| I | Dynamic Tool Architecture | PASS | This IS the registry service. Schema validation via Pydantic, health checks via `/tools/{id}/health`, usage tracking via `tool_usage_logs` table. Agents receive the full tool catalog and the LLM selects the right tool. |
| II | Layered Independence | PASS | Registry is part of the Research Engine layer. Zero dependencies on the Conversational Layer. Independently deployable as a Docker container. Own test suite. |
| III | Agent Autonomy with Bounded Scope | PASS | Registry is infrastructure, not an agent. It serves agents but does not perform agent duties. Clear input/output contracts on every endpoint. |
| IV | Test-First with Contract Testing | PASS | Contract tests planned for all 5 endpoints (request/response schema validation). Unit tests for CRUD, search ranking, embedding. Integration tests for seed → search → bind flow. |
| V | Observability as Infrastructure | PASS | structlog with JSON renderer. Every request gets `trace_id` from header or auto-generated UUID. Tool invocation logging to `tool_usage_logs`. No silent failures — all exceptions logged before re-raise. |
| VI | Performance Under Budget | PASS | Search < 100ms target (simple SQL queries on ~50-200 tools). Bind < 200ms. Health check proxy timeout 500ms. All budgets from constitution respected. |
| VII | Session Continuity | N/A | Registry is stateless per-request. Session continuity is the responsibility of the Conversational Layer and agent orchestration. The registry supports session-scoped logging via `session_id` in usage logs. |

**Gate result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-tool-registry-service/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research decisions
├── data-model.md        # Entity schemas and relationships
├── quickstart.md        # Development setup guide
├── contracts/           # API endpoint contracts
│   ├── register.md
│   ├── search.md
│   ├── bind.md
│   ├── health.md
│   └── stats.md
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
registry/
├── __init__.py
├── app.py                    # FastAPI application factory, lifespan, middleware
├── config.py                 # Settings via pydantic-settings (DB URL, provider, API keys)
├── models.py                 # SQLAlchemy ORM models (Tool, ToolCapability, ToolUsageLog)
├── schemas.py                # Pydantic request/response schemas
├── database.py               # Async engine, session factory, Base
├── search.py                 # Capability-tag filtering and tool listing
├── seed.py                   # Idempotent seed script for 7 tools
├── routers/
│   ├── __init__.py
│   ├── register.py           # POST /tools/register
│   ├── search.py             # GET /tools/search
│   ├── bind.py               # GET /tools/{id}/bind
│   ├── health.py             # GET /tools/{id}/health
│   └── stats.py              # GET /tools/stats
└── middleware/
    ├── __init__.py
    └── logging.py            # structlog request middleware (trace_id, timing)

alembic/
├── alembic.ini
├── env.py
└── versions/
    └── 001_initial_schema.py # tools, capabilities, logs

tests/
├── conftest.py               # Async fixtures, test DB, TestClient
├── contract/
│   ├── test_register_contract.py
│   ├── test_search_contract.py
│   ├── test_bind_contract.py
│   ├── test_health_contract.py
│   └── test_stats_contract.py
├── unit/
│   ├── test_models.py
│   ├── test_schemas.py
│   ├── test_search_logic.py
│   └── test_seed.py
└── integration/
    ├── test_register_search_bind_flow.py
    └── test_seed_idempotency.py
```

**Structure Decision**: Single-service layout under `registry/` at the
repository root, matching the project structure defined in README.md. Tests
are at the repo root under `tests/` organized by type (contract, unit,
integration). Alembic migrations live alongside the service. This is not a
web app with frontend — it's a backend microservice only.

## Complexity Tracking

> No constitution violations — table left empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Simplification Decisions

| Original Design | Simplified To | Rationale |
|----------------|---------------|-----------|
| Vector embeddings for semantic search | Capability-tag SQL filtering + full catalog listing | At ~20-50 tools, all definitions fit in a single LLM prompt. The LLM selects tools better than cosine similarity. Removes embedding provider dependencies. |
