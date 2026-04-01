# Tasks: Conversational session layer (005)

**Input**: Design documents from `/Users/abhisheksuryavanshi/Desktop/project/researchSwarm/specs/005-conversational-session-layer/`  
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/session-api.md](./contracts/session-api.md), [quickstart.md](./quickstart.md)

**Tests**: Included per Research Swarm Constitution (Principle IV — test-first / contract tests) and [plan.md](./plan.md) testing strategy.

**Organization**: Phases follow user story priority (US1 P1 → US2 P2 → US3 P2 → US4 P3), after shared setup and foundation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no ordering dependency within the same phase)
- **[Story]**: `[US1]` … `[US4]` for user-story phases only

---

## Phase 1: Setup (Shared)

**Purpose**: Package wiring and dependencies for `conversation/`.

- [X] T001 Add `conversation*` to `[tool.setuptools.packages.find] include` and add runtime dep `redis>=5` in `pyproject.toml`; use **existing** `aiomysql` + SQLAlchemy async (registry stack) for MySQL—do **not** add a separate PostgreSQL driver per [plan.md](./plan.md) Technical Context
- [X] T002 [P] Create package skeleton `conversation/__init__.py`, `conversation/persistence/__init__.py`, `conversation/api/__init__.py`
- [X] T003 [P] Implement `ConversationSettings` (Redis URL, **MySQL URL aligned with registry** `database_url` or a dedicated `conversation_database_url` defaulting to the same pattern, intent confidence thresholds, lock TTLs) in `conversation/config.py` using `pydantic-settings`

---

## Phase 2: Foundational (Blocking)

**Purpose**: Durable schema, stores, merge baseline, authz denial shape, engine continuation — **required before user stories**.

**⚠️ CRITICAL**: No user story phase work until this phase completes.

- [X] T004 Add Alembic revision creating `session`, `session_turn`, `research_snapshot` tables per [data-model.md](./data-model.md) in `alembic/versions/` (**MySQL-compatible** types: `JSON` for blobs, `CHAR(36)` or binary UUID as agreed, partial unique index for idempotency per MySQL version)
- [X] T005 [P] Define SQLAlchemy 2.0 async table/metadata objects for conversation tables in `conversation/persistence/mysql_models.py` (import into registry `Base` / shared metadata **or** a `ConversationBase` registered with the same engine—document the chosen pattern)
- [X] T006 Implement `MysqlSessionStore` (create session, get by id+owner, append turn, latest snapshot, idempotency fetch) in `conversation/persistence/mysql_store.py`
- [X] T007 [P] Implement `RedisSessionStore` (working-set JSON cache, `SET NX` turn lock with TTL, optional per-session inbox LIST) in `conversation/persistence/redis_store.py`
- [X] T008 Add Pydantic DTOs (`SessionRecord`, `TurnRequest`, `TurnResult`, `IntentResult`, API error bodies) in `conversation/models.py`
- [X] T009 Implement owner checks and **FR-016** ambiguous denial helpers (same payload for unknown vs wrong owner) in `conversation/authz.py`
- [X] T010 Implement baseline `build_engine_input(snapshot, user_message, trace_id)` merging transcript fields into a `dict` compatible with `ResearchState` in `conversation/merge.py`
- [X] T011 Add continuation entrypoint on the engine that **preserves caller-supplied canonical `session_id`** (no re-mint) and validates inputs in `agents/graph.py`
- [X] T012 [P] Add `validate_continuation_input` (or extend validation) for follow-up turns in `agents/state.py` alongside existing `validate_graph_input`

**Checkpoint**: Stores + engine continuation API ready — user story implementation can begin.

---

## Phase 3: User Story 1 — Durable multi-turn research dialogue (Priority: P1) 🎯 MVP

**Goal**: Ordered turns, persisted transcript + snapshots, resume after restart; same `session_id` across turns (spec **FR-001**, **FR-002**, **FR-006**, **SC-001**, **SC-004**).

**Independent Test**: Run turn 1 (research question), turn 2 (follow-up that depends on prior context); restart process (or reconnect to DB only); turn 3 still sees prior constraints/topic from **MySQL** snapshot + Redis repopulation.

### Tests for User Story 1

- [X] T013 [P] [US1] Add failing-then-green integration test for two-turn continuity and id ordering in `tests/integration/test_conversation_multi_turn.py`
- [X] T014 [P] [US1] Add unit tests for `conversation/merge.py` snapshot + message merge in `tests/unit/test_merge_baseline.py`

### Implementation for User Story 1

- [X] T015 [US1] Implement `ConversationCoordinator` core loop: acquire Redis FIFO lock, load/create session, build engine input via `merge.py`, call continuation entrypoint in `agents/graph.py`, persist turn + snapshot in `conversation/coordinator.py`
- [X] T016 [US1] Ensure **MySQL** remains source of truth on Redis miss: repopulate working set from latest snapshot in `conversation/coordinator.py` and `conversation/persistence/redis_store.py`

**Checkpoint**: MVP — durable multi-turn dialogue with full graph each turn acceptable before US2 routing optimization.

---

## Phase 4: User Story 2 — Intent-aware routing (Priority: P2)

**Goal**: Classify `new_query` / `refinement` / `reformat` / `meta_question` with confidence; **FR-015** clarification path; route to minimum work (spec **FR-004**, **FR-005**, **FR-015**, **SC-002**).

**Independent Test**: Gold utterances per category drive expected `RoutePlan` and clarification when confidence below threshold; no silent mis-route.

### Tests for User Story 2

- [X] T017 [P] [US2] Add contract tests for turn response JSON shapes, **FR-016** denial equality, and idempotency behavior in `tests/contract/test_session_contracts.py`
- [X] T018 [P] [US2] Add unit tests with mocked LLM for classifier output parsing in `tests/unit/test_intent_classifier.py`
- [X] T019 [P] [US2] Add unit tests for routing table from `(intent, session_has_snapshot)` in `tests/unit/test_coordinator_routing.py`

### Implementation for User Story 2

- [X] T020 [P] [US2] Implement structured `IntentClassifier` (Pydantic-parsed LLM JSON + confidence + rationale) in `conversation/intent.py`
- [X] T021 [P] [US2] Implement `plan_route(intent, confidence, session_state) -> RoutePlan` in `conversation/routing.py`
- [X] T022 [US2] Integrate classifier + clarification-only branch + route dispatch before engine invoke in `conversation/coordinator.py`

**Checkpoint**: Coordinator varies behavior by intent; low confidence asks clarifying question.

---

## Phase 5: User Story 3 — Constraints carry forward (Priority: P2)

**Goal**: User-stated constraints persist in session + engine state; conflict precedence (**FR-007**, **FR-008**, **FR-010**, spec User Story 3).

**Independent Test**: Turn 1 sets constraint; turn 2 does not repeat it but output still honors it; turn 3 overrides and new rule wins per documented precedence.

### Tests for User Story 3

- [X] T023 [P] [US3] Add unit tests for constraint merge and override precedence in `tests/unit/test_merge_constraints.py`

### Implementation for User Story 3

- [X] T024 [US3] Extend `conversation/merge.py` to merge `constraints` dict with last-wins / per-key-family precedence and surface effective set for tests (spec **FR-010**)
- [X] T025 [US3] Populate constraints from structured classifier output (or dedicated extraction step) on each turn in `conversation/coordinator.py`

**Checkpoint**: Constraints visible in engine input and testable on follow-up turns.

---

## Phase 6: User Story 4 — Selective re-invocation (Priority: P3)

**Goal**: `reformat` / `meta` / light refinement paths avoid full graph when safe (spec User Story 4, **FR-005**, **SC-003**).

**Independent Test**: Under test doubles, `reformat` route does not invoke full researcher path; `new_query` still invokes full graph.

### Tests for User Story 4

- [X] T026 [P] [US4] Add integration or unit tests asserting route-to-engine mapping in `tests/integration/test_conversation_routing_paths.py`
- [X] T027 [P] [US4] Add FIFO ordering tests with concurrent turn submissions in `tests/unit/test_session_fifo.py`

### Implementation for User Story 4

- [X] T028 [US4] Implement `light_reformat` / `light_meta` execution paths (synthesizer-only subgraph or dedicated small graph) in `agents/graph.py` and wire from `conversation/routing.py`
- [X] T029 [US4] Log/record `route_mode` and engine entrypoint for observability and QA signals in `conversation/coordinator.py`

**Checkpoint**: Selective re-invocation demonstrably cheaper for reformat path under benchmarks.

---

## Phase 7: Polish & Cross-Cutting

**Purpose**: HTTP API, degraded mode, observability, docs validation.

- [X] T030 [P] Implement FastAPI routes `POST /v1/sessions` and `POST /v1/sessions/{session_id}/turns` per [contracts/session-api.md](./contracts/session-api.md) in `conversation/api/routes.py`
- [X] T031 Mount or document ASGI inclusion of `conversation/api/routes.py` router in `registry/app.py` (or separate app entry module if preferred — keep single documented entry)
- [X] T032 [P] Implement **FR-012** degraded read-only vs fail-closed paths when Redis/**MySQL** unavailable in `conversation/coordinator.py` and `conversation/persistence/redis_store.py`
- [X] T033 [P] Bind structlog + Langfuse span metadata for coordinator with `agent_id=conversation_coordinator` in `conversation/coordinator.py` per Constitution Principle V
- [X] T034 Execute manual/automated smoke steps from [quickstart.md](./quickstart.md) and fix gaps; record any env vars in `conversation/config.py` docstrings

**Checkpoint**: Feature aligns with spec clarifications and quickstart.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** → **Phase 2** → **Phase 3–6** (user stories) → **Phase 7**
- **Phase 2** blocks all user stories.

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|--------|
| **US1** | Foundational | No other story required |
| **US2** | US1 | Coordinator loop + persistence must exist |
| **US3** | US1 (merge baseline) | Can start after T010; full integration needs US2 for classifier-fed constraints (T025 after T022) |
| **US4** | US2 | Routing table + coordinator dispatch must exist |

Recommended sequence: **US1 → US2 → US3 → US4**.

### Parallel Opportunities

- **Phase 1**: T002, T003 parallel after T001
- **Phase 2**: T005, T007, T012 parallel once T004 direction is set; T006 after T005
- **US1 tests**: T013, T014 parallel
- **US2 tests**: T017, T018, T019 parallel
- **US2 impl**: T020, T021 parallel before T022
- **Phase 7**: T030, T032, T033 parallel after coordinator stable

---

## Parallel Example: User Story 2

```bash
# Tests together:
tests/contract/test_session_contracts.py   # T017
tests/unit/test_intent_classifier.py       # T018
tests/unit/test_coordinator_routing.py     # T019

# Classifier + routing modules together before coordinator integration:
conversation/intent.py    # T020
conversation/routing.py   # T021
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1–2 (foundation)
2. Complete Phase 3 (US1)
3. **STOP and validate** integration test T013 / manual quickstart subset

### Incremental Delivery

1. Add US2 (intent + clarification)
2. Add US3 (constraints precedence)
3. Add US4 (selective re-invocation + FIFO tests)
4. Polish: HTTP + degraded + observability

### Parallel Team Strategy

After Phase 2: one developer on US1 path; another prepares US2 tests (T017–T019) and stubs against coordinator interface — merge when T015 lands.

---

## Notes

- **Dependency direction**: `conversation/` may import `agents/`; never the reverse (Constitution II).
- **Task total**: **34** tasks (T001–T034).
- **Per story (implementation + tests)**: US1: 4 impl/test tasks (T013–T016); US2: 6 (T017–T022); US3: 3 (T023–T025); US4: 4 (T026–T029); Setup 3; Foundation 9; Polish 5.
