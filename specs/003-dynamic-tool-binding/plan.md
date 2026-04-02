# Implementation Plan: Dynamic Tool Binding

**Branch**: `003-dynamic-tool-binding` | **Date**: 2026-03-31 | **Spec**: [spec.md](./spec.md)
**Input**: Build the Dynamic Tool Binding system — a ToolDiscoveryTool meta-tool that agents invoke at runtime to search the registry, select a matching tool, construct a LangChain-compatible callable, bind it, and invoke it with failure fallback strategies.

## Summary

Extract the Researcher's existing inline search → bind → invoke logic into a reusable `ToolDiscoveryTool` meta-tool. The meta-tool is a LangChain `StructuredTool` that encapsulates the full pipeline: search the registry by explicit capability tag, use the LLM to rank and select the best tool, construct an ephemeral `StructuredTool` from the bind response, invoke it with schema-aware payload mapping, and fall back to alternatives on failure (capped at 3 attempts). The Researcher node is then refactored to delegate to this meta-tool. Every invocation attempt is logged to the registry.

## Technical Context

**Language/Version**: Python 3.9+
**Primary Dependencies**: LangGraph >=1.1, langchain-core >=0.3, langchain-google-genai >=2.0 (Gemini 2.0 Flash default), httpx (registry client), langfuse >=2.0 (LLM tracing)
**Storage**: No new storage. Uses existing registry DB via HTTP API for tool lookups and usage logging.
**Testing**: pytest, pytest-asyncio (existing setup)
**Target Platform**: Linux server (EC2), same deployment as registry + agent layer
**Project Type**: Library extension (new module within `agents/tools/`, consumed by agent nodes)
**Performance Goals**: Discovery-to-invocation < 5s (excluding tool execution time). Dynamic tool binding < 200ms (Constitution VI).
**Constraints**: Max 3 fallback attempts per ToolDiscoveryTool invocation. 30s per-tool invocation timeout. Subordinate to 60s graph-level timeout.
**Scale/Scope**: ~20-50 tools in registry, single-instance deployment. Capability string provided by agent — no LLM inference for tag derivation.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| I | Dynamic Tool Architecture | PASS | The ToolDiscoveryTool is the core implementation of Principle I — runtime discovery via registry, no hardcoded tools. Bind responses include validated schemas. Usage tracking via `POST /tools/usage-log` on every attempt. |
| II | Layered Independence | PASS | New code lives in `agents/tools/` alongside existing `registry_client.py`. No registry Python imports — HTTP only. No conversational layer dependency. |
| III | Agent Autonomy with Bounded Scope | PASS | ToolDiscoveryTool is a utility consumed by agents — it does not blur agent boundaries. Researcher still gathers data; meta-tool is infrastructure. Refactored Researcher delegates tool mechanics but retains its role. |
| IV | Test-First with Contract Testing | PASS | Contract tests for ToolDiscoveryTool input/output schemas. Unit tests for DynamicTool construction, fallback logic, payload mapping. Integration test for full search→select→bind→invoke flow. Existing Researcher tests must remain green. |
| V | Observability as Infrastructure | PASS | ToolDiscoveryTool logs every invocation attempt (success/failure) to the registry. Structured logging with trace_id/session_id/agent_id on all operations. LLM tool selection traced via Langfuse callbacks. |
| VI | Performance Under Budget | PASS | Per-tool invocation timeout (30s) prevents single-tool hangs. 3-attempt cap bounds worst-case fallback cost. Dynamic tool binding target < 200ms. All within 60s graph budget. |
| VII | Session Continuity & Research Accumulation | PASS | Constraints forwarded from graph state to registry search and tool payload. session_id flows through to usage logs. No new state fields needed — reuses existing ResearchState. |

**Gate result**: ALL PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/003-dynamic-tool-binding/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── tool-discovery-tool.md
│   ├── dynamic-tool.md
│   └── researcher-refactor.md
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
agents/
├── tools/
│   ├── __init__.py              # Existing
│   ├── registry_client.py       # Existing — unchanged
│   └── discovery.py             # NEW: ToolDiscoveryTool, DynamicTool builder, fallback logic
├── nodes/
│   └── researcher.py            # MODIFIED: refactor to delegate to ToolDiscoveryTool
├── response_models.py           # MODIFIED: add ToolDiscoveryInput, ToolDiscoveryResult, InvocationAttempt
├── config.py                    # MODIFIED: add tool_invocation_timeout_seconds, max_tool_fallback_attempts
└── ...                          # Unchanged files

tests/
├── unit/
│   ├── test_tool_discovery.py       # NEW: ToolDiscoveryTool unit tests
│   ├── test_dynamic_tool_builder.py # NEW: DynamicTool construction tests
│   └── test_researcher_node.py      # EXISTING: must remain green after refactor
├── contract/
│   └── test_tool_discovery_contract.py  # NEW: input/output schema contract tests
└── integration/
    ├── test_tool_discovery_flow.py       # NEW: end-to-end search→select→bind→invoke
    └── test_research_graph_flow.py       # EXISTING: must remain green after refactor
```

**Structure Decision**: New `agents/tools/discovery.py` module alongside existing `registry_client.py`. This keeps tool-related infrastructure in one package while maintaining the established pattern. The ToolDiscoveryTool wraps RegistryClient — no duplication of HTTP logic.

## Complexity Tracking

> No Constitution violations. Table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
