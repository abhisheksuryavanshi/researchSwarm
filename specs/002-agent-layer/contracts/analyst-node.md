# Contract: Analyst Node

**Entity**: `agents.nodes.analyst.analyst_node`
**Type**: LangGraph node function (async)

## Signature

```python
async def analyst_node(state: ResearchState) -> dict:
```

## Responsibilities

- Read raw findings from the Researcher and structure them into a coherent analysis
- Compare and contrast information from different sources
- Identify patterns, contradictions, and key themes
- Produce a markdown-formatted analysis document

## Input State (reads)

| Field | Usage |
|-------|-------|
| `query` | Original question — drives analysis framing |
| `raw_findings` | All accumulated findings to analyze |
| `sources` | Source metadata for attribution |
| `constraints` | Analysis scope boundaries |
| `accumulated_context` | Prior session context for continuity |
| `trace_id` | For structured logging |
| `session_id` | For log correlation |

## Output State (writes)

| Field | Type | Description |
|-------|------|-------------|
| `analysis` | `str` | Markdown-formatted structured analysis |
| `token_usage` | `dict[str, int]` | `{"analyst": <tokens_used>}` |
| `messages` | `list[AnyMessage]` | LLM messages from this invocation |
| `errors` | `list[str]` | Error messages if LLM call fails (may be empty) |

## Behavioral Contract

1. MUST read from `raw_findings` and `sources` — never gather new data
2. MUST NOT invoke any tools from the registry
3. MUST produce `analysis` as a non-empty markdown string
4. MUST attribute claims to specific sources where possible
5. MUST respect `constraints` for scope boundaries
6. MUST include `trace_id` and `session_id` in all log entries
7. Analysis MUST reference `accumulated_context` when available to maintain session continuity

## Test Expectations

1. Given raw_findings with 3 entries, analyst produces non-empty analysis
2. `analysis` field is a string with length > 0
3. `token_usage` includes key `"analyst"` with positive integer value
4. Analyst does not modify `raw_findings` or `sources`
5. Given empty `raw_findings`, analyst produces analysis noting lack of data
