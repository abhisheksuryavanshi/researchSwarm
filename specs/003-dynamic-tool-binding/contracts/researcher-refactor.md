# Contract: Researcher Node Refactor

**Entity**: `agents.nodes.researcher.researcher_node`
**Type**: LangGraph node function (async) — MODIFIED

## Change Summary

The Researcher node is refactored to delegate its inline search → bind → invoke logic to the `ToolDiscoveryTool`. The node's public contract (input state, output state, behavioral obligations) remains **identical** to the existing contract defined in `specs/002-agent-layer/contracts/researcher-node.md`. All existing tests must remain green.

## What Changes

| Aspect | Before (002) | After (003) |
|--------|-------------|-------------|
| Tool discovery | Inline: `registry.search()` → LLM selection → `registry.bind()` → `registry.invoke()` | Delegate to `ToolDiscoveryTool._arun()` |
| Payload construction | `_build_tool_payload()` in researcher.py | `build_tool_payload()` extracted to `agents/tools/discovery.py` |
| Fallback handling | Sequential invocation of LLM-selected tools | Handled by ToolDiscoveryTool's fallback loop (3-attempt cap) |
| Usage logging | Inline `registry.log_usage()` calls | Handled by ToolDiscoveryTool per-attempt |
| Error accumulation | Manual `errs.append()` | Read from `ToolDiscoveryResult.attempts` |

## What Does NOT Change

- Signature: `async def researcher_node(state: ResearchState, runtime: Runtime[GraphContext]) -> dict`
- Input state fields read: `query`, `constraints`, `gaps`, `iteration_count`, `trace_id`, `session_id`
- Output state fields written: `raw_findings`, `sources`, `iteration_count`, `token_usage`, `messages`, `errors`
- LLM call for tool selection (still uses `with_structured_output(ToolSelectionResponse)`)
- Prompt templates (system prompt, user prompt, refinement prompt)
- Observability (structured logging with trace_id/session_id/agent_id)
- The node's role: gather raw data only — no analysis or synthesis

## Behavioral Contract (unchanged from 002)

1. MUST call ToolDiscoveryTool (which internally searches the registry) — never use hardcoded tool lists
2. MUST use `with_structured_output(ToolSelectionResponse)` to select top 1-3 tools
3. MUST log every tool invocation to the registry (now delegated to ToolDiscoveryTool)
4. MUST NOT analyze or synthesize findings
5. MUST increment `iteration_count` by exactly 1
6. On tool failure, fallback is now handled by ToolDiscoveryTool (3-attempt cap)
7. MUST include `trace_id` and `session_id` in all log entries
8. MUST respect `constraints` when selecting and invoking tools

## Refactoring Approach

1. Extract `_build_tool_payload()` and `_fallback_for_type()` from `researcher.py` to `agents/tools/discovery.py`
2. Create `ToolDiscoveryTool` instance using graph context dependencies (registry, llm, config)
3. For each LLM-selected tool_id, invoke `ToolDiscoveryTool._arun()` with appropriate `ToolDiscoveryInput`
4. Map `ToolDiscoveryResult` fields back to the existing state output format:
   - `result.data` → `raw_findings` entry
   - `result.source` → `sources` entry
   - `result.attempts` errors → `errors` entries
5. Keep the LLM tool selection call in the Researcher (the ToolDiscoveryTool receives explicit capability, not raw query)

## Test Compatibility

All existing tests in `tests/unit/test_researcher_node.py` and `tests/integration/test_research_graph_flow.py` MUST pass without modification. The refactoring changes implementation, not behavior.

| Existing Test | Expected Result |
|---------------|----------------|
| `test_researcher_selects_binds_invokes` | PASS — mock_registry_client still called for search/bind/invoke |
| `test_researcher_refinement_with_gaps` | PASS — gaps still forwarded via ToolDiscoveryInput |
| `test_researcher_invoke_fallback` | PASS — fallback now handled by ToolDiscoveryTool |
| `test_researcher_registry_unreachable` | PASS — error still surfaced in output |
| `test_researcher_builds_payload_from_args_schema` | PASS — payload building extracted but logic identical |
| `test_full_research_flow_with_loop_back` | PASS — graph topology unchanged |
| `test_max_iterations_routes_to_synthesizer` | PASS — Critic routing unchanged |
| `test_graph_timeout` | PASS — graph timeout unchanged |
