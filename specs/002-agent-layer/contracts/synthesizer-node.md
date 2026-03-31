# Contract: Synthesizer Node

**Entity**: `agents.nodes.synthesizer.synthesizer_node`
**Type**: LangGraph node function (async)

## Signature

```python
async def synthesizer_node(state: ResearchState) -> dict:
```

## Responsibilities

- Produce the final research output from the accumulated analysis
- Synthesize findings into a coherent, well-structured document
- Include source citations
- Respect output format constraints if specified

## Input State (reads)

| Field | Usage |
|-------|-------|
| `query` | Original question — frames the synthesis |
| `analysis` | Analyst's structured analysis (primary input) |
| `raw_findings` | Raw data for additional detail/citations |
| `sources` | Source list for citations |
| `critique` | Final critique for context on quality |
| `critique_pass` | Whether the research met quality standards |
| `constraints` | Output format preferences if specified |
| `accumulated_context` | Prior session context |
| `trace_id` | For structured logging |
| `session_id` | For log correlation |

## Output State (writes)

| Field | Type | Description |
|-------|------|-------------|
| `synthesis` | `str` | Final research output (markdown) |
| `token_usage` | `dict[str, int]` | `{"synthesizer": <tokens_used>}` |
| `messages` | `list[AnyMessage]` | LLM messages from this invocation |
| `errors` | `list[str]` | Error messages if LLM call fails (may be empty) |

## Behavioral Contract

1. MUST produce `synthesis` as a non-empty markdown string
2. MUST NOT gather new data or invoke tools
3. MUST NOT critique or validate claims
4. MUST cite sources from the `sources` list
5. When `critique_pass` is `False` (budget exhausted), MUST note limitations in the synthesis
6. MUST respect output format constraints from `constraints` dict (e.g., `{"format": "bullet_points"}`)
7. MUST include `trace_id` and `session_id` in all log entries

## Test Expectations

1. Given analysis and sources, synthesizer produces non-empty markdown
2. `synthesis` includes references to at least 1 source from `sources`
3. `token_usage` includes key `"synthesizer"` with positive integer value
4. When `critique_pass=False`, synthesis includes a limitations note
5. Synthesizer does not modify `raw_findings`, `analysis`, or `sources`
