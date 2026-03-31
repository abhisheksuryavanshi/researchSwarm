# Contract: ResearchState Schema

**Entity**: `agents.state.ResearchState`
**Type**: LangGraph TypedDict state schema

## Schema Definition

```python
from typing import Any, Annotated, TypedDict, Literal
from operator import add
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class ResearchState(TypedDict):
    query: str
    constraints: dict[str, Any]
    accumulated_context: Annotated[list[str], add]
    messages: Annotated[list[AnyMessage], add_messages]
    trace_id: str
    session_id: str
    max_iterations: int
    raw_findings: Annotated[list[dict[str, Any]], add]
    sources: Annotated[list[dict[str, str]], _dedupe_sources]
    analysis: str
    critique: str
    critique_pass: bool
    gaps: list[str]
    synthesis: str
    iteration_count: int
    token_usage: Annotated[dict[str, int], _merge_token_usage]
    errors: Annotated[list[str], add]
```

## Input Contract (Graph Invocation)

Callers MUST provide:

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `query` | `str` | YES | — |
| `constraints` | `dict[str, Any]` | NO | `{}` |
| `accumulated_context` | `list[str]` | NO | `[]` |
| `trace_id` | `str` | YES | — |
| `session_id` | `str` | YES | — |
| `max_iterations` | `int` | NO | `3` |

All other fields are initialized by the graph or by agent nodes.

## Output Contract (Graph Result)

On successful completion, the graph returns a state containing:

| Field | Guarantee |
|-------|-----------|
| `synthesis` | Non-empty string; the final research output |
| `raw_findings` | List of >= 1 finding dicts (unless no tools returned data) |
| `sources` | Deduplicated list of source references |
| `analysis` | Non-empty structured analysis text |
| `critique` | Non-empty critique text from the final Critic pass |
| `critique_pass` | `True` if Critic approved, `False` if max_iterations was reached |
| `iteration_count` | Integer >= 1, <= max_iterations |
| `token_usage` | Dict with keys for each agent that executed |
| `errors` | List of error strings (may be empty) |

## Reducer Contracts

| Field | Reducer | Behavior |
|-------|---------|----------|
| `raw_findings` | `operator.add` | Appends new findings to existing list |
| `sources` | `_dedupe_sources` | Merges, deduplicates by URL |
| `accumulated_context` | `operator.add` | Appends new context strings |
| `messages` | `add_messages` | Appends messages, handles ID-based updates |
| `token_usage` | `_merge_token_usage` | Sums per-agent token counts |
| `errors` | `operator.add` | Appends error strings |
| All other fields | default (overwrite) | Latest value wins |

## Validation Contract

```python
def validate_graph_input(state: dict) -> None:
    """Raises ValueError if input state is invalid."""
    assert isinstance(state.get("query"), str) and len(state["query"]) > 0
    assert isinstance(state.get("trace_id"), str) and len(state["trace_id"]) > 0
    assert isinstance(state.get("session_id"), str) and len(state["session_id"]) > 0
    if "max_iterations" in state:
        assert 1 <= state["max_iterations"] <= 5
    if "constraints" in state:
        assert isinstance(state["constraints"], dict)
```

## Test Expectations

1. A valid input dict with `query`, `trace_id`, `session_id` must be accepted
2. Missing `query` must raise ValueError
3. `max_iterations` outside [1, 5] must raise ValueError
4. Reducer `_dedupe_sources` must not duplicate URLs
5. Reducer `_merge_token_usage` must sum values for same keys
6. Graph output must contain non-empty `synthesis` when `critique_pass` is True
