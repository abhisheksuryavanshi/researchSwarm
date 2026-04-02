# Implementation Plan: Agent Layer (LangGraph State Machine)

**Branch**: `002-agent-layer` | **Date**: 2026-03-31 | **Spec**: [spec.md](./spec.md)
**Input**: Implement the Agent layer — LangGraph state machine with four agents (Researcher, Analyst, Critic, Synthesizer), typed state schema with `constraints` dict and `accumulated_context`, and conditional graph with Critic-to-Researcher loop-back.

## Summary

Add a multi-agent research orchestration layer built on LangGraph's `StateGraph`. The graph contains four specialist nodes (Researcher, Analyst, Critic, Synthesizer) that collaborate through a typed shared state. A conditional edge from Critic routes back to Researcher when quality is insufficient, creating a refinement loop bounded by `max_iterations`. The state schema includes `constraints` and `accumulated_context` from day one per Constitution Principle VII. Agents discover and bind tools at runtime via the Tool Registry HTTP API (Principle I). Each agent makes independent LLM calls using `with_structured_output()` for type-safe parsing. A per-graph 60s timeout enforces the performance budget. Single concurrent execution in v1.

## Technical Context

**Language/Version**: Python 3.9+
**Primary Dependencies**: LangGraph >=1.1, langchain-core >=0.3, langchain-google-genai >=2.0 (Gemini 2.0 Flash default), httpx (registry client), langfuse >=2.0 (LLM tracing)
**Storage**: MySQL via existing registry DB (tool lookups); in-memory state for graph execution; future Redis for session persistence (not in this phase)
**Testing**: pytest, pytest-asyncio (existing setup)
**Target Platform**: Linux server (EC2 t3.micro/small), same deployment as registry
**Project Type**: Library (importable orchestration engine consumed by future Conversational Layer)
**Performance Goals**: End-to-end research query < 60s (Constitution VI); per-graph total timeout enforced; individual agent node < 15s
**Constraints**: Max 3 Critic loop-back iterations (configurable up to 5); every LLM call has 30s timeout + exponential backoff retry; single concurrent graph execution in v1
**Scale/Scope**: ~20-50 tools in registry, single-instance deployment, 1 concurrent research graph execution

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| I | Dynamic Tool Architecture | PASS | Researcher discovers tools via `GET /tools/search`, uses LLM to select top 1-3, binds via `GET /tools/{id}/bind`. No hardcoded tool lists. Failed tools trigger alternative tool attempt (FR-007). |
| II | Layered Independence | PASS | `agents/` package at repo root, separate from `registry/`. No imports from future conversational layer. Communication is HTTP-only. Independently testable and deployable. |
| III | Agent Autonomy with Bounded Scope | PASS | Four agents with explicit typed state fields. Each makes independent LLM calls (FR-008b). Researcher writes `raw_findings`; Analyst writes `analysis`; Critic writes `critique`/`critique_pass`; Synthesizer writes `synthesis`. No scope leakage. |
| IV | Test-First with Contract Testing | PASS | Contract tests validate state schema fields per agent. Unit tests for each node function. Integration test for full graph with loop-back. |
| V | Observability as Infrastructure | PASS | structlog with `trace_id`, `session_id`, `agent_id` on every log. Langfuse tracing for LLM calls via callback handler. No silent failures — errors accumulated in state. |
| VI | Performance Under Budget | PASS | 60s per-graph total timeout enforced (FR-015). 30s per-LLM-call timeout. Token tracking per-agent via `_merge_token_usage`. Budget overruns logged as warnings. |
| VII | Session Continuity & Research Accumulation | PASS | `constraints: dict` and `accumulated_context: list[str]` in state from day one. Sources deduplicated via `_dedupe_sources` reducer. `session_id` flows through all nodes. |

**Gate result**: ALL PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/002-agent-layer/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── state-schema.md
│   ├── researcher-node.md
│   ├── analyst-node.md
│   ├── critic-node.md
│   └── synthesizer-node.md
└── tasks.md             # Phase 2 output (not created by /speckit.plan)
```

### Source Code (repository root)

```text
agents/
├── __init__.py
├── state.py             # ResearchState TypedDict with Annotated reducers
├── graph.py             # StateGraph construction, conditional edges, graph timeout
├── config.py            # AgentConfig via pydantic-settings
├── tracing.py           # Langfuse + structlog integration
├── response_models.py   # Pydantic models for with_structured_output()
├── nodes/
│   ├── __init__.py
│   ├── researcher.py    # Researcher node: LLM tool selection, bind, invoke
│   ├── analyst.py       # Analyst node: structure and compare findings
│   ├── critic.py        # Critic node: quality gate, gaps, route_after_critic
│   └── synthesizer.py   # Synthesizer node: final output with citations
├── tools/
│   ├── __init__.py
│   └── registry_client.py  # httpx client for Tool Registry API
└── prompts/
    ├── __init__.py
    ├── researcher.py    # System/user prompt templates
    ├── analyst.py
    ├── critic.py
    └── synthesizer.py

registry/                # Existing — unchanged

tests/
├── conftest.py          # Extend with agent fixtures
├── contract/
│   ├── ...              # Existing registry contracts
│   ├── test_state_schema_contract.py
│   ├── test_researcher_contract.py
│   ├── test_analyst_contract.py
│   ├── test_critic_contract.py
│   └── test_synthesizer_contract.py
├── integration/
│   ├── ...              # Existing registry integration tests
│   └── test_research_graph_flow.py
└── unit/
    ├── ...              # Existing registry unit tests
    ├── test_researcher_node.py
    ├── test_analyst_node.py
    ├── test_critic_node.py
    ├── test_synthesizer_node.py
    ├── test_graph_construction.py
    └── test_response_models.py
```

**Structure Decision**: `agents/` at repo root alongside `registry/` — Layered Independence (Principle II). New `response_models.py` module holds Pydantic models used by `with_structured_output()` for type-safe LLM parsing (clarification decision).

## Complexity Tracking

> No Constitution violations. Table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
