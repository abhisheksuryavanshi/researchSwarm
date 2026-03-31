# Tasks: Agent Layer (LangGraph State Machine)

**Input**: Design documents from `/specs/002-agent-layer/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — Constitution Principle IV mandates test-first with contract testing. Spec SC-005 requires contract tests for each agent node.

**Organization**: Tasks are grouped by user story from spec.md to enable independent implementation and testing. US4 (State Schema) and US6 (Configuration) are placed in Phase 2 (Foundational) since they are blocking prerequisites for all other stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Agent package: `agents/` at repository root (alongside existing `registry/`)
- Tests: `tests/` at repository root (extending existing test structure)

---

## Phase 1: Setup (Package Structure & Dependencies)

**Purpose**: Create the `agents/` package skeleton, install dependencies, and configure tooling

- [X] T001 Create agents package directory tree with all `__init__.py` files: `agents/__init__.py`, `agents/nodes/__init__.py`, `agents/tools/__init__.py`, `agents/prompts/__init__.py`
- [X] T002 Add agent layer dependencies to `pyproject.toml`: `langgraph>=0.6.10,<0.7` (current PyPI; spec target ≥1.1 when published), `langchain-core>=0.3`, `langchain>=0.3`, `langchain-google-genai>=2.0`, `langfuse>=2.0`
- [X] T003 Update `pyproject.toml` package discovery to include agents: `include = ["registry*", "agents*"]`
- [X] T004 [P] Update `.env.example` with agent layer environment variables: `GOOGLE_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `MAX_ITERATIONS`, `GRAPH_TIMEOUT_SECONDS`, `LANGFUSE_ENABLED`, `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`

---

## Phase 2: Foundational — US4 State Schema + US6 Configuration (Priority: P1)

**Purpose**: Core infrastructure that ALL agent nodes depend on — MUST complete before any node implementation

**⚠️ CRITICAL**: No agent node work can begin until this phase is complete

**Goal (US4)**: Define the `ResearchState` TypedDict with `constraints` dict, `accumulated_context`, and all Annotated reducers
**Goal (US6)**: Define `AgentConfig` via pydantic-settings with all defaults and validation

**Independent Test (US4)**: Validate state schema types, reducer behavior, and input validation
**Independent Test (US6)**: Verify config defaults, env var loading, bounds checking

### Tests for Foundational Phase

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T005 [P] [US4] Contract test for ResearchState schema in `tests/contract/test_state_schema_contract.py` — validate required input fields (query, trace_id, session_id), optional fields with defaults, reducer behavior for _dedupe_sources (dedup by URL), _merge_token_usage (sum per-agent keys), operator.add (raw_findings, errors, accumulated_context), max_iterations bounds [1,5], empty query rejection
- [X] T006 [P] [US6] Unit test for AgentConfig in `tests/unit/test_agent_config.py` — validate all defaults (model=gemini-2.0-flash, temperature=0.1, timeout=30, max_retries=3, max_iterations=3, graph_timeout=60), env var override, MAX_ITERATIONS=6 raises ValidationError, GRAPH_TIMEOUT_SECONDS loading
- [X] T007 [P] Unit test for custom reducers in `tests/unit/test_reducers.py` — _dedupe_sources with overlapping URLs returns unique set, _merge_token_usage sums same keys and preserves disjoint keys, empty inputs return empty
- [X] T008 [P] Unit test for response models in `tests/unit/test_response_models.py` — validate ToolSelectionResponse (1-3 tool_ids, reasoning non-empty), CritiqueResponse (critique non-empty, gaps list), AnalysisResponse, SynthesisResponse
- [X] T009 [P] Unit test for RegistryClient in `tests/unit/test_registry_client.py` — mock httpx calls for search(capability), bind(tool_id), invoke(endpoint, method, payload), log_usage(); verify error handling on connection failure

### Implementation for Foundational Phase

- [X] T010 [P] [US4] Implement ResearchState TypedDict with Annotated reducers in `agents/state.py` — all 17 fields per data-model.md, custom reducers _dedupe_sources and _merge_token_usage, validate_graph_input() function per state-schema contract
- [X] T011 [P] [US6] Implement AgentConfig with pydantic-settings in `agents/config.py` — all fields from data-model.md including graph_timeout_seconds, field validators for max_iterations in [1,5], env_prefix support
- [X] T012 [P] Implement Pydantic response models in `agents/response_models.py` — ToolSelectionResponse, CritiqueResponse, AnalysisResponse, SynthesisResponse per data-model.md
- [X] T013 [P] Implement Langfuse + structlog tracing integration in `agents/tracing.py` — get_tracer() returning LangfuseCallbackHandler (when enabled), get_logger() returning bound structlog logger with trace_id/session_id/agent_id context binding
- [X] T014 Implement RegistryClient in `agents/tools/registry_client.py` — async httpx client with search(capability), bind(tool_id), invoke(endpoint, method, payload), log_usage(tool_id, agent_id, session_id, latency_ms, success) methods; timeout and error handling per research.md decision 5
- [X] T015 Extend test fixtures in `tests/conftest.py` — add mock_registry_client fixture (returns 3 tools on search, valid bind response), sample_research_state fixture (valid input state), mock_llm fixture (returns predictable structured output)

**Checkpoint**: State schema, config, response models, tracing, and registry client are ready — agent node implementation can begin. US4 and US6 acceptance scenarios testable.

---

## Phase 3: US3 — Dynamic Tool Discovery & Binding (Priority: P1) 🎯 MVP

**Goal**: Implement the Researcher agent that discovers tools from the registry, uses the LLM to select top 1-3, binds and invokes them, and accumulates findings

**Independent Test**: Mock registry (3 tools) and LLM, invoke researcher_node, verify LLM-based tool selection, raw_findings growth, sources growth, iteration_count increment, usage logging

### Tests for US3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T016 [P] [US3] Contract test for researcher node in `tests/contract/test_researcher_contract.py` — validate output types (raw_findings list[dict], sources list[dict], iteration_count int, token_usage dict), verify iteration_count increments by exactly 1, verify no analysis/synthesis/critique fields written, verify messages appended (audit log only)
- [X] T017 [P] [US3] Unit test for researcher node in `tests/unit/test_researcher_node.py` — mock registry+LLM, verify search called, verify with_structured_output(ToolSelectionResponse) used for tool selection (1-3 tools), verify selected tools are bound and invoked, verify raw_findings grows by >=1, verify sources grows by >=1, test loop-back with gaps (refine queries), test tool failure triggers alternative tool attempt, test registry unreachable adds to errors

### Implementation for US3

- [X] T018 [P] [US3] Create researcher prompt templates in `agents/prompts/researcher.py` — SYSTEM_PROMPT (role definition, tool selection guidance), USER_PROMPT (query + constraints + search results for tool selection), REFINEMENT_PROMPT (for loop-back iterations with gaps from Critic)
- [X] T019 [US3] Implement researcher_node function in `agents/nodes/researcher.py` — discover tools via RegistryClient.search(), use LLM with with_structured_output(ToolSelectionResponse) to select top 1-3 tools, bind via RegistryClient.bind(), invoke selected tools, accumulate raw_findings and sources, increment iteration_count, track token_usage, log invocations via RegistryClient.log_usage(), handle tool failure with alternative fallback per FR-005/FR-007, independent LLM calls (FR-008b)

**Checkpoint**: Researcher node works standalone — discovers, selects, binds, and invokes tools with LLM-based selection

---

## Phase 4: US2 — Critic Quality Gate & Loop-Back (Priority: P1)

**Goal**: Implement the Analyst and Critic agents, plus the `route_after_critic` routing function that drives the conditional Critic-to-Researcher loop-back

**Independent Test**: Provide pre-populated state, invoke analyst_node and critic_node, verify critique_pass gating and routing function behavior with various state combinations

### Tests for US2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T020 [P] [US2] Contract test for analyst node in `tests/contract/test_analyst_contract.py` — validate output types (analysis str, token_usage dict), verify analysis is non-empty, verify raw_findings/sources not modified, verify no tool invocations, verify messages appended (audit only)
- [X] T021 [P] [US2] Contract test for critic node in `tests/contract/test_critic_contract.py` — validate output types (critique str, critique_pass bool, gaps list[str], token_usage dict), verify critique always non-empty, verify gaps are actionable when critique_pass=False, verify no tool invocations or synthesis
- [X] T022 [P] [US2] Unit test for analyst node in `tests/unit/test_analyst_node.py` — mock LLM with with_structured_output(AnalysisResponse), verify analysis from 3 findings, test with empty raw_findings (notes lack of data), test accumulated_context inclusion, verify independent LLM call (FR-008b)
- [X] T023 [P] [US2] Unit test for critic node in `tests/unit/test_critic_node.py` — mock LLM with with_structured_output(CritiqueResponse), test pass scenario (critique_pass=True, gaps=[]), test fail scenario (critique_pass=False, gaps non-empty), test route_after_critic returns "researcher" when fail+iterations remain, test route_after_critic returns "synthesizer" when pass, test route_after_critic returns "synthesizer" when iterations exhausted regardless of critique_pass

### Implementation for US2

- [X] T024 [P] [US2] Create analyst prompt templates in `agents/prompts/analyst.py` — SYSTEM_PROMPT (role: structure and compare, no data gathering), USER_PROMPT (query + raw_findings + sources + constraints + accumulated_context)
- [X] T025 [P] [US2] Create critic prompt templates in `agents/prompts/critic.py` — SYSTEM_PROMPT (role: validate claims, identify gaps, no synthesis), USER_PROMPT (query + analysis + raw_findings + sources + constraints + iteration_count + max_iterations)
- [X] T026 [US2] Implement analyst_node function in `agents/nodes/analyst.py` — read raw_findings/sources, call LLM with with_structured_output(AnalysisResponse), produce markdown analysis, track token_usage, include accumulated_context, independent LLM calls (FR-008b)
- [X] T027 [US2] Implement critic_node function and route_after_critic routing function in `agents/nodes/critic.py` — call LLM with with_structured_output(CritiqueResponse), set critique_pass/gaps, track token_usage; route_after_critic(state) -> Literal["researcher", "synthesizer"] per FR-004

**Checkpoint**: Analyst + Critic nodes work standalone. route_after_critic correctly drives loop-back decisions. US2 acceptance scenarios testable.

---

## Phase 5: US1 — Research Query Execution (Priority: P1)

**Goal**: Implement the Synthesizer node, assemble the complete StateGraph with all four agents and conditional edges, enforce graph-level timeout, and validate end-to-end execution

**Independent Test**: Build the graph, invoke with mocked LLM+registry, verify full flow executes including loop-back, synthesis is non-empty, token_usage aggregated, sources deduplicated

### Tests for US1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T028 [P] [US1] Contract test for synthesizer node in `tests/contract/test_synthesizer_contract.py` — validate output types (synthesis str, token_usage dict), verify synthesis is non-empty markdown, verify synthesis references >=1 source, verify limitations note when critique_pass=False, verify raw_findings/analysis/sources not modified
- [X] T029 [P] [US1] Unit test for synthesizer node in `tests/unit/test_synthesizer_node.py` — mock LLM with with_structured_output(SynthesisResponse), test synthesis from analysis+sources, test critique_pass=False includes limitations, test constraints format preferences, verify independent LLM call (FR-008b)
- [X] T030 [P] [US1] Unit test for graph construction in `tests/unit/test_graph_construction.py` — verify build_research_graph returns compiled graph, verify 4 nodes (researcher, analyst, critic, synthesizer), verify START→researcher edge, verify researcher→analyst, analyst→critic edges, verify critic has conditional edges to researcher and synthesizer, verify synthesizer→END edge
- [X] T031 [US1] Integration test for full research graph flow in `tests/integration/test_research_graph_flow.py` — mock LLM+registry, invoke graph with test query, verify output contains non-empty synthesis, test loop-back scenario (critic fails first then passes), test max_iterations exhaustion, verify token_usage aggregated across all agents, verify sources deduplicated across iterations, verify graph_timeout_seconds enforcement

### Implementation for US1

- [X] T032 [P] [US1] Create synthesizer prompt templates in `agents/prompts/synthesizer.py` — SYSTEM_PROMPT (role: synthesize, cite sources, note limitations), USER_PROMPT (query + analysis + raw_findings + sources + critique + critique_pass + constraints + accumulated_context)
- [X] T033 [US1] Implement synthesizer_node function in `agents/nodes/synthesizer.py` — call LLM with with_structured_output(SynthesisResponse), produce final markdown with citations, note limitations when critique_pass=False (FR-009), track token_usage, independent LLM calls (FR-008b)
- [X] T034 [US1] Implement build_research_graph function in `agents/graph.py` — create StateGraph(ResearchState), add_node for all 4 agents, add_edge START→researcher, researcher→analyst, analyst→critic, add_conditional_edges critic→route_after_critic, add_edge synthesizer→END, enforce graph_timeout_seconds via asyncio.timeout, single-flight guard (`GraphBusyError` if busy), compile and return
- [X] T035 [US1] Add graph entry point in `agents/__init__.py` — export build_research_graph, ResearchState, AgentConfig for external consumers

**Checkpoint**: Complete pipeline functional — full graph executes with all four agents, Critic loop-back, graph timeout, and single-execution guard. US1 acceptance scenarios testable.

---

## Phase 6: US5 — Agent Observability (Priority: P2)

**Goal**: Ensure all agent nodes emit structured logs with correlation IDs, LLM calls are traced via Langfuse, and no exceptions are silently swallowed

**Independent Test**: Invoke a node, capture structlog output, verify trace_id/session_id/agent_id on every entry. Verify Langfuse callback attached to LLM calls.

### Tests for US5

- [X] T036 [P] [US5] Unit test for observability in `tests/unit/test_observability.py` — capture structlog output from a node execution, verify every log entry contains trace_id + session_id + agent_id, verify Langfuse callback is passed to LLM calls when langfuse_enabled=True, verify token_usage warning logged when exceeding threshold, verify tool invocation failures logged with full context before adding to errors

### Implementation for US5

- [X] T037 [US5] Audit and enhance structlog usage in all agent nodes `agents/nodes/*.py` — verify every log call binds trace_id, session_id, agent_id; add entry/exit logging per node; add token_usage warning threshold check; ensure all exceptions logged before adding to errors
- [X] T038 [US5] Wire Langfuse callback into LLM calls across all nodes in `agents/nodes/*.py` — pass get_tracer() callback to with_structured_output() calls; verify latency and token tracking per agent

**Checkpoint**: All observability requirements met. SC-004 (correlation IDs) and SC-006 (token tracking) validated.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and validation across all agent components

- [X] T039 [P] Update `README.md` with Agent Layer section — architecture diagram, dependency on registry, quickstart reference, graph visualization
- [X] T040 [P] Run quickstart.md validation — verify all code snippets in `specs/002-agent-layer/quickstart.md` are accurate against implementation
- [X] T041 Run full test suite and verify all tests pass — `pytest tests/ -v`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) — BLOCKS all agent node work
- **US3 (Phase 3)**: Depends on Foundational (Phase 2) — can start immediately after
- **US2 (Phase 4)**: Depends on Foundational (Phase 2) — **can run in parallel with US3**
- **US1 (Phase 5)**: Depends on US3 + US2 (all four nodes must exist for graph assembly)
- **US5 (Phase 6)**: Depends on US1 (nodes must exist to audit/enhance)
- **Polish (Phase 7)**: Depends on US5 (Phase 6)

### User Story Dependencies

```text
Phase 1: Setup
    │
    ▼
Phase 2: Foundational (US4 + US6)
    │
    ├──► Phase 3: US3 Tool Discovery (Researcher) ──┐
    │                                                 │
    └──► Phase 4: US2 Critic Loop-Back ──────────────┤  (can run in parallel)
         (Analyst + Critic + routing)                 │
                                                      │
                                                      ▼
                                           Phase 5: US1 Full Pipeline
                                           (Synthesizer + Graph)
                                                      │
                                                      ▼
                                           Phase 6: US5 Observability
                                                      │
                                                      ▼
                                           Phase 7: Polish
```

### Within Each User Story

- Contract test MUST be written and FAIL before implementation
- Unit test MUST be written and FAIL before implementation
- Prompt templates before node implementation (templates are data, no dependencies)
- Node implementation depends on prompts + foundational infrastructure

### Parallel Opportunities

- T001-T004 (Setup): T004 can run in parallel with T001-T003
- T005-T009 (Foundational tests): ALL can run in parallel
- T010-T013 (Foundational impl): ALL can run in parallel; T014 depends on T011 (config)
- **Phase 3 (US3) and Phase 4 (US2) can run in parallel** — Researcher and Analyst+Critic are independent agents in separate files
- Within Phase 4: T020-T023 (tests) all parallel; T024-T025 (prompts) parallel; T026 and T027 sequential (analyst before critic for testing)
- Within Phase 5: T028-T030 (tests) all parallel; T032 (prompts) parallel with tests

---

## Parallel Example: US3 + US2 (After Foundational)

```bash
# After Phase 2 completes, launch both stories in parallel:

# US3: Researcher (Developer A)
Task: "Contract test for researcher in tests/contract/test_researcher_contract.py"
Task: "Unit test for researcher in tests/unit/test_researcher_node.py"
Task: "Prompt templates in agents/prompts/researcher.py"
Task: "Implement researcher_node in agents/nodes/researcher.py"

# US2: Analyst + Critic (Developer B)
Task: "Contract test for analyst in tests/contract/test_analyst_contract.py"
Task: "Contract test for critic in tests/contract/test_critic_contract.py"
Task: "Unit test for analyst in tests/unit/test_analyst_node.py"
Task: "Unit test for critic in tests/unit/test_critic_node.py"
Task: "Prompt templates in agents/prompts/analyst.py"
Task: "Prompt templates in agents/prompts/critic.py"
Task: "Implement analyst_node in agents/nodes/analyst.py"
Task: "Implement critic_node + route_after_critic in agents/nodes/critic.py"

# Both complete → Phase 5: US1 Graph Assembly
```

---

## Implementation Strategy

### MVP First (Foundational + Researcher + Stubs)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all nodes)
3. Complete Phase 3: US3 Researcher
4. Stub analyst/critic/synthesizer in Phase 5, wire graph
5. **STOP and VALIDATE**: Test Researcher → stub pipeline end-to-end
6. Fill in US2 and complete US1

### Recommended: Full Pipeline

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (US4 + US6)
3. Complete Phases 3 + 4 in parallel (US3 + US2)
4. Complete Phase 5: US1 (Synthesizer + Graph Assembly)
5. Complete Phase 6: US5 (Observability)
6. Complete Phase 7: Polish
7. Full pipeline works end-to-end after Phase 5

### Parallel Team Strategy

With two developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US3 (Researcher)
   - Developer B: US2 (Analyst + Critic + routing)
3. Both complete → Team assembles graph in Phase 5 (US1)
4. Then US5 (Observability) + Polish

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US4 and US6 are in Phase 2 (Foundational) since they are blocking prerequisites for all stories
- Constitution Principle IV mandates: write tests first, verify they fail, then implement
- Clarification decisions integrated: LLM tool selection (ToolSelectionResponse), with_structured_output(), independent LLM calls, graph timeout, single execution lock
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
