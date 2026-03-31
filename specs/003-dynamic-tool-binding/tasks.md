---

## description: "Task list for Dynamic Tool Binding (ToolDiscoveryTool meta-tool)"

# Tasks: Dynamic Tool Binding

**Input**: Design documents from `/specs/003-dynamic-tool-binding/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — plan Constitution IV and quickstart.md require contract, unit, and integration tests for ToolDiscoveryTool and dynamic tool construction; existing Researcher/graph tests must stay green.

**Organization**: Phases follow spec user-story priorities (P1 → P2) with foundational work first; implementation order ensures `build_dynamic_tool` exists before the full `ToolDiscoveryTool` pipeline.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no ordering dependency within the same phase)
- **[Story]**: User story label ([US1]–[US5]) where required
- Paths use repository root: `agents/`, `tests/`, `.env.example`

## Path Conventions

Single project: `agents/`, `tests/` at repository root (per plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Environment and baseline configuration for new AgentConfig fields.

- [x] T001 Add `TOOL_INVOCATION_TIMEOUT_SECONDS` and `MAX_TOOL_FALLBACK_ATTEMPTS` to `.env.example` at repository root with comments matching `specs/003-dynamic-tool-binding/quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pydantic contracts, config, shared payload/dynamic-tool builders, and exports. **No user story work should start until this phase is complete.**

- [x] T002 Add `ToolDiscoveryInput`, `ToolDiscoveryResult`, and `InvocationAttempt` to `agents/response_models.py` per `specs/003-dynamic-tool-binding/data-model.md` (including `capability` pattern and non-empty `query` validators)
- [x] T003 Add `tool_invocation_timeout_seconds` and `max_tool_fallback_attempts` to `agents/config.py` with pydantic field validators (bounds per data-model.md)
- [x] T004 Move `build_tool_payload` and `fallback_for_type` from `agents/nodes/researcher.py` into `agents/tools/discovery.py` as public functions and update `agents/nodes/researcher.py` to import them (preserve behavior until refactor)
- [x] T005 Implement `build_dynamic_tool` and JSON Schema → Pydantic field mapping helpers in `agents/tools/discovery.py` per `specs/003-dynamic-tool-binding/contracts/dynamic-tool.md`
- [x] T006 Export `build_tool_payload`, `build_dynamic_tool`, and (after T009) `ToolDiscoveryTool` from `agents/tools/__init__.py`

**Checkpoint**: Models, config, payload mapping, and dynamic `StructuredTool` construction are available for the meta-tool pipeline.

---

## Phase 3: User Story 1 — Agent Discovers and Invokes a Tool at Runtime (Priority: P1) 🎯 MVP

**Goal**: End-to-end `ToolDiscoveryTool` search → LLM rank/select → bind → construct dynamic tool → invoke → usage log → structured success result.

**Independent Test**: Mock registry with multiple tools for one capability; verify selection, invocation, `ToolDiscoveryResult.success`, metadata, and `POST /tools/usage-log` on success.

### Tests for User Story 1

- [x] T007 [P] [US1] Add contract tests for `ToolDiscoveryInput`, `ToolDiscoveryResult`, and `InvocationAttempt` JSON/schema conformance in `tests/contract/test_tool_discovery_contract.py` per `specs/003-dynamic-tool-binding/contracts/tool-discovery-tool.md`
- [x] T008 [P] [US1] Add integration test for search → select → bind → invoke happy path with httpx mocks in `tests/integration/test_tool_discovery_flow.py`

### Implementation for User Story 1

- [x] T009 [US1] Implement `ToolDiscoveryTool` as `BaseTool` subclass with `args_schema = ToolDiscoveryInput` and async `_arun` pipeline in `agents/tools/discovery.py` per `specs/003-dynamic-tool-binding/contracts/tool-discovery-tool.md` (registry search by explicit capability, LLM `with_structured_output(ToolSelectionResponse)`, bind, `build_dynamic_tool`, invoke, `log_usage`, return JSON `ToolDiscoveryResult`)
- [x] T010 [US1] Implement registry unreachable, empty search results, and LLM selection failure → lowest `avg_latency_ms` fallback in `agents/tools/discovery.py` per spec edge cases and tool-discovery-tool contract

**Checkpoint**: Single successful dynamic invocation with logging; structured errors for search/LLM edge cases.

---

## Phase 4: User Story 2 — Fallback on Tool Invocation Failure (Priority: P1)

**Goal**: Sequential retries on LLM-ranked candidates (filled by latency ordering when needed), max 3 attempts, per-tool `asyncio.timeout`, per-attempt usage logs, structured failure when exhausted.

**Independent Test**: First two mocked tools fail (timeout / HTTP error); third succeeds; `attempts` length and `log_usage` call counts match spec.

### Tests for User Story 2

- [x] T011 [P] [US2] Add unit tests for fallback ordering, 3-attempt cap, timeout behavior, and per-attempt logging in `tests/unit/test_tool_discovery.py`

### Implementation for User Story 2

- [x] T012 [US2] Wrap each dynamic tool invocation in `asyncio.timeout(config.tool_invocation_timeout_seconds)` and implement fallback loop up to `config.max_tool_fallback_attempts` in `agents/tools/discovery.py` per `specs/003-dynamic-tool-binding/research.md`
- [x] T013 [US2] On exhausted attempts, return `ToolDiscoveryResult` with populated `attempts`, `success=False`, and summary `error`; ensure failed and successful attempts are each logged via `RegistryClient.log_usage` in `agents/tools/discovery.py`

**Checkpoint**: Resilient invocation path matches US2 acceptance scenarios.

---

## Phase 5: User Story 3 — LangChain-Compatible Callable Construction (Priority: P1)

**Goal**: Ephemeral `StructuredTool` from bind response validates input, maps types from JSON Schema, calls `RegistryClient.invoke` with correct method/endpoint.

**Independent Test**: Known `args_schema` rejects invalid payloads before HTTP; valid payload hits mock `invoke` with expected JSON.

### Tests for User Story 3

- [x] T014 [P] [US3] Add unit tests for `build_dynamic_tool` (name/description/args_schema, empty schema → generic model, type mapping, invoke wiring) in `tests/unit/test_dynamic_tool_builder.py` per `specs/003-dynamic-tool-binding/contracts/dynamic-tool.md`

### Implementation for User Story 3

- [x] T015 [US3] Close any gaps in `agents/tools/discovery.py` so dynamic tools enforce args_schema validation before HTTP and use generic `query`/`constraints`/`gaps` payload fallback when schema is empty, per FR-007 and FR-014

**Checkpoint**: Dynamic tool behavior matches US3 and dynamic-tool contract.

---

## Phase 6: User Story 4 — ToolDiscoveryTool as a LangChain Tool (Priority: P2)

**Goal**: Meta-tool is bindable on any agent via standard tool-calling; structured JSON output for the LLM.

**Independent Test**: Agent (or minimal runnable) with `ToolDiscoveryTool` in tools list invokes it through normal tool calls.

### Tests for User Story 4

- [x] T016 [P] [US4] Add test that registers `ToolDiscoveryTool` on an LLM with tool-calling and asserts `tool_discovery` is invoked with structured args in `tests/integration/test_tool_discovery_tool_binding.py` (or extend `tests/integration/test_tool_discovery_flow.py` with a dedicated case)

### Implementation for User Story 4

- [x] T017 [US4] Add `tool_discovery: ToolDiscoveryTool` to `GraphContext` in `agents/context.py` and construct it in `agents/graph.py` inside `default_graph_context()` alongside existing `registry`, `llm`, and `agent_config`
- [x] T018 [US4] Ensure `ToolDiscoveryTool._arun` / `ainvoke` returns a JSON string of `ToolDiscoveryResult` suitable for LLM consumption per `specs/003-dynamic-tool-binding/spec.md` US4

**Checkpoint**: US4 acceptance scenarios satisfied.

---

## Phase 7: User Story 5 — Registry Search with Constraint Forwarding (Priority: P2)

**Goal**: Constraints from graph state flow into registry search and into tool payloads per FR-013.

**Independent Test**: `ToolDiscoveryInput.constraints` affects `GET /tools/search` parameters and merged tool payload fields.

### Implementation for User Story 5

- [x] T019 [US5] Extend `RegistryClient.search` in `agents/tools/registry_client.py` to forward supported constraint fields as query parameters (or agreed serialization) to `GET /tools/search` per registry API behavior
- [x] T020 [US5] Pass `ToolDiscoveryInput.constraints` into `registry.search` and through `build_tool_payload` / schema-aware mapping in `agents/tools/discovery.py` per `specs/003-dynamic-tool-binding/contracts/tool-discovery-tool.md` § Behavioral 10

**Checkpoint**: US5 acceptance scenarios satisfied.

---

## Phase 8: Researcher Refactor (FR-016)

**Goal**: Remove duplicated search/bind/invoke/logging from the Researcher; delegate to `ToolDiscoveryTool` while keeping the public node contract and all existing tests green.

**Independent Test**: `pytest tests/unit/test_researcher_node.py tests/integration/test_research_graph_flow.py` unchanged and passing.

- [x] T021 [US1] Refactor `agents/nodes/researcher.py` to use `ToolDiscoveryTool` from `runtime.context` (or construct from context deps) per `specs/003-dynamic-tool-binding/contracts/researcher-refactor.md` and FR-016; map `ToolDiscoveryResult` into `raw_findings`, `sources`, `errors`, and messages
- [x] T022 [US1] Run `pytest tests/unit/test_researcher_node.py tests/integration/test_research_graph_flow.py` and fix regressions until green without weakening assertions

**Checkpoint**: Researcher behavior preserved; FR-016 complete.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Output envelope, observability, tracing, and repo-wide validation.

- [x] T023 [P] Ensure tool outputs are wrapped in the standardized envelope (`tool_id`, raw data, `success`, `attempts` as required) per FR-015 in `agents/tools/discovery.py`
- [x] T024 [P] Add structured logging (operation names, capability, tool_ids, attempt outcomes) in `agents/tools/discovery.py` consistent with `agents/tracing.py` / `structlog` usage elsewhere
- [x] T025 Pass Langfuse (or graph) callbacks into LLM invocations used for tool selection inside `agents/tools/discovery.py`, aligned with `agents/nodes/researcher.py` patterns
- [x] T026 Execute the test commands in `specs/003-dynamic-tool-binding/quickstart.md` (full `pytest` and `ruff check` on touched packages) and fix any failures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** → no prerequisites
- **Phase 2** → after Phase 1 (config/env documented)
- **Phase 3 (US1)** → after Phase 2
- **Phase 4 (US2)** → after Phase 3 (core pipeline exists)
- **Phase 5 (US3)** → overlaps with Phase 2 for implementation; **tests (T014–T015)** after T005 and preferably after T009–T012 for realistic integration
- **Phase 6 (US4)** → after Phase 3 (meta-tool implemented)
- **Phase 7 (US5)** → after Phase 3; may combine with T019–T020 before or after Phase 6 depending on context wiring
- **Phase 8** → after Phases 3–4 (stable ToolDiscoveryTool with fallback); **after Phase 7** if Researcher must forward constraints through the meta-tool
- **Phase 9** → after Phase 8 preferred (full stack behavior)

### User Story Dependencies


| Story    | Depends on                                                                            |
| -------- | ------------------------------------------------------------------------------------- |
| US1 (P1) | Foundational                                                                          |
| US2 (P1) | US1 core (`ToolDiscoveryTool` skeleton + successful path)                             |
| US3 (P1) | Foundational (`build_dynamic_tool`); validation tasks after builder usage in pipeline |
| US4 (P2) | US1                                                                                   |
| US5 (P2) | US1; extends `RegistryClient` + meta-tool                                             |


### Parallel Opportunities

- **Phase 2**: T002 and T003 can proceed in parallel (different files)
- **US1 tests**: T007 and T008 in parallel
- **US2**: T011 parallel with prep work; implementation T012 → T013 sequential
- **US3**: T014 parallel with other test files; T015 follows T014 findings
- **US4**: T016 parallel with T017 once `ToolDiscoveryTool` exists
- **Phase 9**: T023 and T024 in parallel

---

## Parallel Example: User Story 1

```bash
# After Phase 2, run contract and integration test authoring together:
# T007 tests/contract/test_tool_discovery_contract.py
# T008 tests/integration/test_tool_discovery_flow.py
```

---

## Parallel Example: User Story 2

```bash
# T011 tests/unit/test_tool_discovery.py — design mocks while T012–T013 implement fallback loop
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1–2 (models, config, builders, researcher imports)
2. Complete Phase 3 (US1) — discover and invoke with logging
3. Complete Phase 4 (US2) — production-grade fallback and timeout
4. **Stop and validate** with `pytest tests/integration/test_tool_discovery_flow.py tests/unit/test_tool_discovery.py`
5. Add Phase 8 (Researcher) when meta-tool is stable

### Incremental Delivery

1. Foundational → dynamic tools exist
2. US1 + US2 → full meta-tool pipeline
3. US3 tests harden builder contracts
4. US4 → graph exposes meta-tool to any node
5. US5 → constraint forwarding
6. Researcher refactor → single integration surface
7. Polish → envelope, tracing, full suite

### Parallel Team Strategy

- Developer A: Phase 2 + US1 implementation (T009–T010)
- Developer B: Contract/integration tests T007–T008, then US3 tests T014
- Developer C: US2 tests T011 + implementation T012–T013
- After merge: US4–US5, then Phase 8, then Phase 9

---

## Notes

- Reuse `RegistryClient` in `agents/tools/registry_client.py` for all HTTP; do not import registry service Python modules from agents code (plan.md).
- Resolve any ambiguity between `contracts/researcher-refactor.md` step 3 (“per LLM-selected tool_id”) and `contracts/tool-discovery-tool.md` (meta-tool performs search + LLM selection) by following **spec FR-003–FR-005** and **tool-discovery-tool.md** as the runtime source of truth when implementing T021.
- All tasks use checklist format: `- [ ] Txxx [P] [USn] Description with file path`

