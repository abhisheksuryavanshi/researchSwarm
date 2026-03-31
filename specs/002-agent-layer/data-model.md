# Data Model: Agent Layer (LangGraph State Machine)

**Feature**: Agent Layer — LangGraph orchestration engine
**Date**: 2026-03-31

## Overview

The Agent layer does not introduce new database tables. Its primary data structure is the **LangGraph state schema** — a `TypedDict` that flows through the graph and accumulates results from each agent node. The existing `ToolUsageLog` table in the registry captures tool invocations made by agents.

## Core Entity: ResearchState

The shared state schema that flows through the entire LangGraph graph. Every node reads from and writes to this structure.

```python
class ResearchState(TypedDict):
    # --- Input fields (set at graph invocation) ---
    query: str                                          # The research question
    constraints: dict[str, Any]                         # Source filters, entity focus, depth params
    accumulated_context: Annotated[list[str], operator.add]  # Cross-turn memory from prior sessions
    messages: Annotated[list[AnyMessage], add_messages]      # Append-only audit log (NOT shared between agents)
    trace_id: str                                       # Correlation ID for observability
    session_id: str                                     # Session ID for multi-turn continuity
    max_iterations: int                                 # Critic loop-back cap (default: 3)

    # --- Researcher output ---
    raw_findings: Annotated[list[dict[str, Any]], operator.add]  # Accumulated raw data from tools
    sources: Annotated[list[dict[str, str]], _dedupe_sources]    # Deduplicated source references

    # --- Analyst output ---
    analysis: str                                       # Structured comparison of findings

    # --- Critic output ---
    critique: str                                       # Quality assessment text
    critique_pass: bool                                 # Whether findings meet quality threshold
    gaps: list[str]                                     # Identified gaps for loop-back refinement

    # --- Synthesizer output ---
    synthesis: str                                      # Final research output

    # --- Internal bookkeeping ---
    iteration_count: int                                # Current loop-back iteration (0-indexed)
    token_usage: Annotated[dict[str, int], _merge_token_usage]  # Per-agent token tracking
    errors: Annotated[list[str], operator.add]          # Accumulated error messages
```

### Field Details

| Field | Type | Reducer | Set By | Description |
|-------|------|---------|--------|-------------|
| `query` | `str` | overwrite | caller | The user's research question |
| `constraints` | `dict[str, Any]` | overwrite | caller | Filters: `{"sources": ["arxiv"], "date_range": "2024-2026", "max_depth": 2}` |
| `accumulated_context` | `list[str]` | `operator.add` | caller / graph | Context from prior sessions; appended each turn |
| `messages` | `list[AnyMessage]` | `add_messages` | all nodes | LangChain message history for LLM context |
| `trace_id` | `str` | overwrite | caller | UUID for distributed tracing |
| `session_id` | `str` | overwrite | caller | Groups multi-turn interactions |
| `max_iterations` | `int` | overwrite | caller | Maximum Critic→Researcher loops (default 3) |
| `raw_findings` | `list[dict]` | `operator.add` | Researcher | Each entry: `{"tool_id": str, "data": Any, "timestamp": str}` |
| `sources` | `list[dict]` | `_dedupe_sources` | Researcher | Each entry: `{"url": str, "title": str, "tool_id": str}` |
| `analysis` | `str` | overwrite | Analyst | Markdown-formatted structured analysis |
| `critique` | `str` | overwrite | Critic | Quality assessment with specific issues |
| `critique_pass` | `bool` | overwrite | Critic | `True` if findings are sufficient |
| `gaps` | `list[str]` | overwrite | Critic | List of gaps to address on loop-back |
| `synthesis` | `str` | overwrite | Synthesizer | Final output in requested format |
| `iteration_count` | `int` | overwrite | Researcher | Incremented on each loop-back entry |
| `token_usage` | `dict[str, int]` | `_merge_token_usage` | all nodes | `{"researcher": 1500, "analyst": 800, ...}` |
| `errors` | `list[str]` | `operator.add` | any node | Error messages from failed operations |

### Custom Reducers

```python
def _dedupe_sources(existing: list[dict], new: list[dict]) -> list[dict]:
    """Merge source lists, deduplicating by URL."""
    seen = {s["url"] for s in existing}
    merged = list(existing)
    for s in new:
        if s["url"] not in seen:
            merged.append(s)
            seen.add(s["url"])
    return merged

def _merge_token_usage(existing: dict[str, int], new: dict[str, int]) -> dict[str, int]:
    """Sum token counts per agent."""
    merged = dict(existing)
    for k, v in new.items():
        merged[k] = merged.get(k, 0) + v
    return merged
```

## Entity: RegistryToolBinding

Not a database entity — a runtime data structure returned by `GET /tools/{id}/bind` from the existing registry.

```python
class RegistryToolBinding:
    name: str           # Tool name (e.g., "serpapi-search")
    description: str    # What the tool does
    args_schema: dict   # JSON Schema for input
    endpoint: str       # HTTP endpoint to invoke
    method: str         # HTTP method (POST, GET)
    version: str        # Tool version
    return_schema: dict # JSON Schema for output
```

This maps 1:1 to the existing `ToolBindResponse` Pydantic schema in `registry/schemas.py`.

## Entity: LLM Response Models (for `with_structured_output()`)

Pydantic models used with `ChatModel.with_structured_output()` for type-safe LLM parsing. Defined in `agents/response_models.py`.

```python
class ToolSelectionResponse(BaseModel):
    """Researcher uses this to select tools from search results."""
    selected_tool_ids: list[str]    # 1-3 tool IDs chosen by LLM
    reasoning: str                  # Why these tools were selected

class CritiqueResponse(BaseModel):
    """Critic uses this for structured quality assessment."""
    critique: str                   # Quality assessment text
    critique_pass: bool             # Whether quality threshold is met
    gaps: list[str]                 # Specific gaps to address on loop-back

class AnalysisResponse(BaseModel):
    """Analyst uses this for structured analysis output."""
    analysis: str                   # Markdown-formatted analysis

class SynthesisResponse(BaseModel):
    """Synthesizer uses this for the final output."""
    synthesis: str                  # Final markdown output with citations
```

## Entity: AgentConfig

Runtime configuration, not persisted. Loaded from environment variables via `pydantic-settings`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `llm_provider` | `str` | `"google"` | LLM provider key |
| `llm_model` | `str` | `"gemini-2.0-flash"` | Model identifier |
| `llm_temperature` | `float` | `0.1` | Sampling temperature for research tasks |
| `llm_timeout_seconds` | `int` | `30` | Per-call timeout |
| `llm_max_retries` | `int` | `3` | Retry count with exponential backoff |
| `max_iterations` | `int` | `3` | Default Critic loop-back cap |
| `graph_timeout_seconds` | `int` | `60` | Per-graph total timeout (aborts remaining nodes) |
| `registry_base_url` | `str` | `"http://localhost:8000"` | Tool Registry endpoint |
| `langfuse_enabled` | `bool` | `True` | Toggle Langfuse tracing |
| `langfuse_host` | `str` | `"http://localhost:3000"` | Langfuse server URL |

## State Transitions

```text
┌─────────────┐
│   START      │
└──────┬───────┘
       │ query, constraints, accumulated_context,
       │ trace_id, session_id, max_iterations
       ▼
┌─────────────┐    writes: raw_findings, sources,
│ Researcher   │◄──────────── iteration_count, token_usage
└──────┬───────┘
       │
       ▼
┌─────────────┐    writes: analysis, token_usage
│  Analyst     │
└──────┬───────┘
       │
       ▼
┌─────────────┐    writes: critique, critique_pass,
│   Critic     │    gaps, token_usage
└──────┬───────┘
       │
       ├── critique_pass=False AND iteration_count < max_iterations
       │   └──► back to Researcher (with gaps as refinement input)
       │
       └── critique_pass=True OR iteration_count >= max_iterations
           │
           ▼
    ┌─────────────┐    writes: synthesis, token_usage
    │ Synthesizer  │
    └──────┬───────┘
           │
           ▼
    ┌─────────────┐
    │     END      │
    └──────────────┘
```

## Validation Rules

1. `query` must be non-empty (validated at graph invocation)
2. `constraints` defaults to `{}` if not provided
3. `accumulated_context` defaults to `[]` if not provided
4. `max_iterations` must be >= 1 and <= 5 (enforced in config)
5. `iteration_count` starts at 0, incremented by Researcher on each entry
6. `critique_pass` defaults to `False`
7. `trace_id` must be a valid UUID string
8. `session_id` must be a non-empty string

## Relationship to Existing Entities

| Agent Layer | Registry Layer | Relationship |
|-------------|---------------|--------------|
| `ResearchState.sources[*].tool_id` | `Tool.tool_id` | Researcher records which tool provided each source |
| `RegistryClient.search()` | `GET /tools/search` | Runtime HTTP call, no foreign key |
| `RegistryClient.bind()` | `GET /tools/{id}/bind` | Runtime HTTP call, no foreign key |
| Tool invocation logging | `ToolUsageLog` | Researcher logs invocations via `POST` to registry (agent_id, session_id, latency, success) |
