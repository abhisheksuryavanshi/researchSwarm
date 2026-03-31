# Contract: Critic Node

**Entity**: `agents.nodes.critic.critic_node`
**Type**: LangGraph node function (async)

## Signature

```python
async def critic_node(state: ResearchState) -> dict:
```

## Responsibilities

- Evaluate the quality and completeness of the analysis and raw findings
- Use `with_structured_output(CritiqueResponse)` to produce typed output with `critique`, `critique_pass`, and `gaps`
- Identify specific gaps, unsupported claims, and areas needing more research
- Set `critique_pass` to gate the loop-back decision
- Make independent LLM calls — do NOT read `messages` for prompt construction

## Input State (reads)

| Field | Usage |
|-------|-------|
| `query` | Original question — basis for completeness assessment |
| `raw_findings` | Check if findings cover the query adequately |
| `analysis` | The Analyst's output to critique |
| `sources` | Verify source diversity and quality |
| `constraints` | Check if constraints were respected |
| `iteration_count` | Awareness of how many iterations have occurred |
| `max_iterations` | Awareness of remaining budget |
| `trace_id` | For structured logging |
| `session_id` | For log correlation |

## Output State (writes)

| Field | Type | Description |
|-------|------|-------------|
| `critique` | `str` | Structured quality assessment text |
| `critique_pass` | `bool` | `True` if findings meet quality threshold |
| `gaps` | `list[str]` | Specific gaps to address on loop-back |
| `token_usage` | `dict[str, int]` | `{"critic": <tokens_used>}` |
| `messages` | `list[AnyMessage]` | LLM messages from this invocation |
| `errors` | `list[str]` | Error messages if LLM call fails (may be empty) |

## Behavioral Contract

1. MUST evaluate quality objectively based on query coverage, source diversity, and claim support
2. MUST NOT gather new data or invoke tools
3. MUST NOT synthesize or produce final output
4. MUST set `critique_pass` to `True` only if quality threshold is met
5. When `critique_pass` is `False`, MUST populate `gaps` with >= 1 specific, actionable gap
6. When `iteration_count >= max_iterations - 1`, SHOULD be more lenient (this is the last chance)
7. MUST include `trace_id` and `session_id` in all log entries

## Routing Contract

The graph uses `route_after_critic(state)` to decide the next node:

```python
def route_after_critic(state: ResearchState) -> Literal["researcher", "synthesizer"]:
    if not state["critique_pass"] and state["iteration_count"] < state["max_iterations"]:
        return "researcher"
    return "synthesizer"
```

| Condition | Route |
|-----------|-------|
| `critique_pass=True` | → Synthesizer |
| `critique_pass=False` AND `iteration_count < max_iterations` | → Researcher (loop-back) |
| `critique_pass=False` AND `iteration_count >= max_iterations` | → Synthesizer (budget exhausted) |

## Test Expectations

1. Given a thorough analysis, critic sets `critique_pass=True` and `gaps=[]`
2. Given a weak analysis, critic sets `critique_pass=False` and `gaps` is non-empty
3. `critique` field is always a non-empty string
4. `gaps` entries are actionable strings (not empty strings)
5. `route_after_critic` returns `"researcher"` when critique fails with iterations remaining
6. `route_after_critic` returns `"synthesizer"` when critique passes
7. `route_after_critic` returns `"synthesizer"` when iterations exhausted regardless of critique_pass
