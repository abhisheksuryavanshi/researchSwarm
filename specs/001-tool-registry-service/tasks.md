# Tasks: Tool Registry Service

**Input**: Design documents from `/specs/001-tool-registry-service/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included. Constitution Principle IV mandates TDD. SC-005 requires contract tests on all endpoint schemas.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Project Initialization)

**Purpose**: Create project skeleton, dependency management, and local infrastructure.

- [X] T001 Create project directory structure per plan.md: `registry/`, `registry/routers/`, `registry/middleware/`, `alembic/`, `alembic/versions/`, `tests/`, `tests/contract/`, `tests/unit/`, `tests/integration/`
- [X] T002 [P] Initialize Python project with `pyproject.toml`: define project metadata, dependencies (fastapi, sqlalchemy[asyncio], aiomysql, httpx, structlog, pydantic, pydantic-settings, alembic, uvicorn), and dev dependencies (pytest, pytest-asyncio, httpx, ruff, black, coverage)
- [X] T003 [P] Create `docker-compose.yml` with MySQL 8.0 service (`mysql:8.0`, port 3306, volume for persistence, `researchswarm` database)
- [X] T004 [P] Create `.env.example` with all config vars: `DATABASE_URL`, `LOG_LEVEL`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Implement pydantic-settings config in `registry/config.py`: `Settings` class with `database_url`, `log_level`; loaded from env vars with sensible defaults
- [X] T006 [P] Set up async SQLAlchemy engine and session factory in `registry/database.py`: `create_async_engine` with `aiomysql`, `async_sessionmaker`, `Base` declarative base, `get_db` dependency for FastAPI
- [X] T007 [P] Implement structlog JSON logging config and request middleware in `registry/middleware/logging.py`: configure structlog with JSON renderer, FastAPI middleware that binds `trace_id` (from `X-Trace-ID` header or auto-generated UUID), `session_id` (from `X-Session-ID` header), request timing
- [X] T008 Create SQLAlchemy ORM models in `registry/models.py`: `Tool` (all fields from data-model.md), `ToolCapability` (FK to Tool with CASCADE, unique constraint), `ToolUsageLog` (FK to Tool, all audit fields); use `mapped_column` style from SQLAlchemy 2.0+
- [X] T009 [P] Create Pydantic v2 request/response schemas in `registry/schemas.py`: `ToolCreateRequest`, `ToolUpdateRequest`, `ToolResponse`, `ToolSearchResult`, `ToolSearchResponse`, `ToolBindResponse`, `ToolHealthResponse`, `ToolStatsResponse`, `UsageLogCreateRequest`; all with validation rules from data-model.md (tool_id regex, semver, URL validation, capability tag regex)
- [X] T010 Set up Alembic with async config in `alembic/env.py` and `alembic.ini`; create initial migration `alembic/versions/001_initial_schema.py`: create `tools`, `tool_capabilities`, `tool_usage_logs` tables with all indexes from data-model.md
- [X] T011 ~~REMOVED~~ (Embedding provider — removed in simplification. Vector search replaced by capability-tag filtering.)
- [X] T012 Create FastAPI application factory with lifespan in `registry/app.py`: create app, include all routers, attach structlog middleware, init shared httpx.AsyncClient for health proxying, global exception handler returning structured JSON errors

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 — Tool Registration (Priority: P1)

**Goal**: Operators can register, update, and soft-delete tools via the API. Tools are validated, persisted, and embedded for semantic search.

**Independent Test**: POST a tool payload → 201; PUT to update → 200; DELETE to deprecate → 200; GET by ID to verify.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T013 [P] [US1] Contract test for `POST /tools/register` in `tests/contract/test_register_contract.py`: test 201 with valid payload (verify all response fields match contract/register.md), test 422 with missing required fields, test 422 with invalid tool_id regex, test 409 with duplicate tool_id
- [X] T014 [P] [US1] Contract test for `PUT /tools/{id}` in `tests/contract/test_update_contract.py`: test 200 with valid update (verify updated_at changes), test 200 with description change, test 404 for nonexistent tool, test 422 with invalid fields, test partial update preserves unchanged fields
- [X] T015 [P] [US1] Contract test for `DELETE /tools/{id}` in `tests/contract/test_delete_contract.py`: test 200 sets status to 'deprecated', test 404 for nonexistent tool, test deprecated tool excluded from search results, test status restorable via PUT

### Implementation for User Story 1

- [X] T016 [US1] Implement `POST /tools/register` in `registry/routers/register.py`: validate request via `ToolCreateRequest` schema, check for duplicate tool_id (409), persist Tool + ToolCapability rows in a transaction, return `ToolResponse` with 201
- [X] T017 [US1] Implement `PUT /tools/{id}` in `registry/routers/register.py`: validate request via `ToolUpdateRequest`, fetch existing tool (404 if missing), update capabilities (delete old + insert new), update tool row, return `ToolResponse` with 200
- [X] T018 [US1] Implement `DELETE /tools/{id}` (soft delete) in `registry/routers/register.py`: fetch tool (404 if missing), set `status = 'deprecated'`, set `updated_at`, return `ToolResponse` with 200
- [X] T019 [P] [US1] Unit tests for Pydantic schema validation in `tests/unit/test_schemas.py`: test tool_id regex (valid/invalid patterns), semver validation, URL validation, capability tag regex, JSON Schema validation for input/output_schema fields
- [X] T020 [P] [US1] Unit tests for ORM models in `tests/unit/test_models.py`: test Tool model field defaults (status='active', method='POST'), test ToolCapability unique constraint, test ToolUsageLog field types, test timestamp auto-generation

**Checkpoint**: Tool CRUD is fully functional. Can register, update, and deprecate tools.

---

## Phase 4: User Story 2 — Tool Search & Listing (Priority: P1)

**Goal**: Agents discover tools by capability tags or retrieve the full tool catalog for LLM-based selection.

**Independent Test**: Seed 5+ tools, search by capability → filtered results; list all → full catalog returned.

### Tests for User Story 2

- [X] T021 [P] [US2] Contract test for `GET /tools/search` in `tests/contract/test_search_contract.py`: test capability filter returns matching tools, test no-filter returns all active tools, test empty results return `[]` not error, test deprecated tools excluded, test limit parameter

### Implementation for User Story 2

- [X] T022 [US2] Implement search logic in `registry/search.py`: `search_tools(db, capability, limit)` — if capability: filter by JOIN on tool_capabilities; exclude deprecated/unhealthy status; return results ordered by created_at
- [X] T023 [US2] Implement `GET /tools/search` router in `registry/routers/search.py`: parse query params (capability, limit=10), call search logic, return `ToolSearchResponse`
- [X] T024 [P] [US2] Unit tests for search logic in `tests/unit/test_search_logic.py`: test capability filtering (exact match), test status exclusion, test limit

**Checkpoint**: Core discovery loop complete — tools can be registered and found via search.

---

## Phase 5: User Story 3 — Runtime Tool Binding (Priority: P2)

**Goal**: After discovering a tool, agents get a LangChain-compatible definition for runtime binding.

**Independent Test**: Register a tool, call `/tools/{id}/bind`, verify response matches StructuredTool schema (name, description, args_schema, endpoint, method, return_schema).

### Tests for User Story 3

- [X] T025 [P] [US3] Contract test for `GET /tools/{id}/bind` in `tests/contract/test_bind_contract.py`: test 200 with valid tool (verify all fields per contracts/bind.md — name, description, args_schema as JSON Schema, endpoint, method, version, return_schema), test 404 for nonexistent tool

### Implementation for User Story 3

- [X] T026 [US3] Implement `GET /tools/{id}/bind` router in `registry/routers/bind.py`: fetch tool by ID (404 if missing), construct `ToolBindResponse` mapping input_schema → args_schema, output_schema → return_schema, return 200

**Checkpoint**: Full discover-bind loop works: search → select → bind → agent gets tool definition.

---

## Phase 6: User Story 6 — Registry Seeding (Priority: P2)

**Goal**: Seed registry with 7 tools covering distinct capability domains so agents have tools available from first startup.

**Independent Test**: Run seed script on empty DB → 7 tools registered. Run again → no duplicates (idempotent).

### Tests for User Story 6

- [X] T027 [P] [US6] Unit tests for seed script in `tests/unit/test_seed.py`: test seed creates exactly 7 tools with valid metadata, test idempotency (running twice yields same count), test all seeded tools have non-empty capabilities, test all seeded tools have valid input/output schemas

### Implementation for User Story 6

- [X] T028 [US6] Implement idempotent seed script in `registry/seed.py`: define 7 tool fixtures (SerpAPI, ArXiv, GitHub, Wikipedia, Calculator, URL Scraper, SEC Filing Parser) per research.md RT-008 with full metadata + schemas + capability tags; use `INSERT ... ON CONFLICT (tool_id) DO NOTHING` for idempotency; runnable as `python -m registry.seed`

**Checkpoint**: Registry has demo data. Search and bind can be exercised end-to-end.

---

## Phase 7: User Story 4 — Health Checks (Priority: P3)

**Goal**: Operators can check tool health. Registry proxies health check to the tool's endpoint and classifies result.

**Independent Test**: Register tool with mock health endpoint, call `/tools/{id}/health` → healthy/degraded/unhealthy status based on mock response.

### Tests for User Story 4

- [X] T029 [P] [US4] Contract test for `GET /tools/{id}/health` in `tests/contract/test_health_contract.py`: test healthy response (mock <500ms 200 OK), test degraded response (mock >500ms), test unhealthy response (mock connection refused), test unknown status when no health_check configured, test 404 for nonexistent tool, test tool status updated in DB after check

### Implementation for User Story 4

- [X] T030 [US4] Implement `GET /tools/{id}/health` router in `registry/routers/health.py`: fetch tool (404 if missing), if no health_check → return status "unknown", construct full health URL, call via shared `httpx.AsyncClient` with 500ms timeout, classify response (<500ms 2xx → healthy, >500ms → degraded, error → unhealthy), update tool.status in DB, return `ToolHealthResponse`

**Checkpoint**: Health monitoring works. Unhealthy tools can be detected and excluded from search.

---

## Phase 8: User Story 5 — Usage Statistics (Priority: P3)

**Goal**: Operators view per-tool usage aggregates: invocation count, latency percentiles, error rate.

**Independent Test**: Insert test usage log rows, call `/tools/stats` → verify aggregated metrics match expected values.

### Tests for User Story 5

- [X] T031 [P] [US5] Contract test for `GET /tools/stats` in `tests/contract/test_stats_contract.py`: test per-tool aggregates (invocation_count, success_count, error_count, error_rate, avg/p50/p95 latency, last_invoked_at), test zeroed metrics for tool with no invocations, test tool_id filter, test since timestamp filter

### Implementation for User Story 5

- [X] T032 [US5] Implement `GET /tools/stats` router in `registry/routers/stats.py`: aggregate query on `tool_usage_logs` grouped by tool_id — COUNT, SUM(success), AVG(latency_ms), percentile_cont(0.5/0.95) for latency, MAX(invoked_at); LEFT JOIN with tools for name and status; optional tool_id and since filters; return `ToolStatsResponse`

**Checkpoint**: All 7 API endpoints functional. Full feature is operational.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Integration tests, end-to-end validation, cleanup.

- [X] T033 Integration test: register → search → bind flow in `tests/integration/test_register_search_bind_flow.py`: register 3 tools with different capabilities, search by capability → verify correct filter, search by query → verify semantic ranking, bind top result → verify LangChain-compatible response
- [X] T034 Integration test: seed idempotency in `tests/integration/test_seed_idempotency.py`: run seed script, verify 7 tools, run seed again, verify still 7 tools, verify all searchable and bindable
- [X] T035 Verify all structured logs include `trace_id` and `session_id` fields: add assertions in integration tests that log output contains expected context vars (SC-006)
- [X] T036 Run `quickstart.md` validation: execute each step in quickstart.md against a fresh Docker Compose environment (start mysql, migrate, seed, start service, curl each endpoint)
- [X] T037 Code cleanup: ensure all public functions have type annotations, remove any TODO comments, verify ruff + black pass with zero warnings

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 Registration (Phase 3)**: Depends on Foundational. First user story — no other story dependencies.
- **US2 Search (Phase 4)**: Depends on Foundational. Benefits from US1 (needs registered tools to search) but can use test fixtures independently.
- **US3 Binding (Phase 5)**: Depends on Foundational. Benefits from US1 (needs a registered tool to bind).
- **US6 Seeding (Phase 6)**: Depends on US1 (uses registration path internally).
- **US4 Health (Phase 7)**: Depends on Foundational. Benefits from US1 (needs a registered tool).
- **US5 Stats (Phase 8)**: Depends on Foundational. Benefits from US1 (needs usage log entries).
- **Polish (Phase 9)**: Depends on all user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — no dependencies on other stories
- **US2 (P1)**: Can start after Foundational — independently testable with fixtures
- **US3 (P2)**: Can start after Foundational — independently testable with fixtures
- **US6 (P2)**: Depends on US1 (registration endpoint must work for seeding)
- **US4 (P3)**: Can start after Foundational — independently testable with fixtures
- **US5 (P3)**: Can start after Foundational — independently testable with fixtures

### Within Each User Story

- Contract tests MUST be written and FAIL before implementation
- Implementation follows: router → service logic → edge cases
- Story complete when contract tests pass and integration verified

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T002, T003, T004)
- All Foundational tasks marked [P] can run in parallel (T006, T007, T009)
- Once Foundational completes: US1 and US2 can start in parallel (both P1)
- Contract tests within a phase marked [P] can run in parallel
- US3, US4, US5 can start in parallel after Foundational (with test fixtures)

---

## Implementation Strategy

### MVP First (User Story 1 + 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: US1 — Tool Registration
4. Complete Phase 4: US2 — Semantic Search
5. **STOP and VALIDATE**: Register a tool, search for it, verify the core loop works
6. Deploy / demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 (Registration) → Can register and manage tools (MVP write path!)
3. US2 (Search) → Can discover tools (MVP read path!) → **Core loop complete**
4. US3 (Binding) → Agents can get LangChain definitions → **Ready for Phase 2 agents**
5. US6 (Seeding) → Demo-ready with 7 tools
6. US4 (Health) + US5 (Stats) → Operational maturity
7. Polish → Production-ready

### Suggested MVP Scope

**Phases 1-4** (Setup + Foundational + US1 + US2) deliver the core value:
tools can be registered and discovered. This is the minimum needed before
Phase 2 of the overall project (Agent Implementation) can begin.
