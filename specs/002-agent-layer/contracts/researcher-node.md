# Contract: Researcher Node

**Entity**: `agents.nodes.researcher.researcher_node`
**Type**: LangGraph node function (async)

## Signature

```python
async def researcher_node(state: ResearchState) -> dict:
```

## Responsibilities

- Discover tools from the registry by capability tags derived from the query
- Use the LLM with `with_structured_output(ToolSelectionResponse)` to select the top 1-3 most relevant tools from search results
- Bind and invoke only the selected tools to gather raw data
- Accumulate findings and source references in state
- Increment `iteration_count` on each invocation
- On loop-back (iteration_count > 0): use `gaps` from Critic to refine search
- Make independent LLM calls — do NOT read `messages` for prompt construction

## Input State (reads)

| Field | Usage |
|-------|-------|
| `query` | The research question to investigate |
| `constraints` | Filters to apply (source types, date range, etc.) |
| `gaps` | On loop-back: specific gaps identified by Critic |
| `iteration_count` | Current iteration (0 on first pass) |
| `trace_id` | For structured logging |
| `session_id` | For usage log correlation |

## Output State (writes)

| Field | Type | Description |
|-------|------|-------------|
| `raw_findings` | `list[dict]` | New findings: `[{"tool_id": str, "data": Any, "timestamp": str}]` |
| `sources` | `list[dict]` | New sources: `[{"url": str, "title": str, "tool_id": str}]` |
| `iteration_count` | `int` | Incremented by 1 |
| `token_usage` | `dict[str, int]` | `{"researcher": <tokens_used>}` |
| `messages` | `list[AnyMessage]` | LLM messages from this invocation |
| `errors` | `list[str]` | Error messages from failed tool invocations (may be empty) |

## Behavioral Contract

1. MUST call `RegistryClient.search()` to discover tools — never use hardcoded tool lists
2. MUST use `with_structured_output(ToolSelectionResponse)` to select top 1-3 tools from search results
3. MUST call `RegistryClient.bind()` only for LLM-selected tools
3. MUST log every tool invocation to the registry (agent_id, latency, success/failure)
4. MUST NOT analyze or synthesize findings — only gather raw data
5. MUST increment `iteration_count` by exactly 1
6. On failure of a tool invocation, MUST attempt an alternative tool from the same capability before recording an error
7. MUST include `trace_id` and `session_id` in all log entries
8. MUST respect `constraints` when selecting and invoking tools

## Test Expectations

1. Given a mocked registry with 3 tools, researcher discovers and invokes at least 1
2. `raw_findings` list grows by >= 1 entry after invocation
3. `sources` list grows by >= 1 entry after invocation
4. `iteration_count` is incremented by exactly 1
5. On loop-back (gaps non-empty), researcher focuses queries on gaps
6. Tool invocation failure triggers alternative tool attempt
7. All outputs conform to the stated types
