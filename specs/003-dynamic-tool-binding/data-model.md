# Data Model: Dynamic Tool Binding

**Feature**: Dynamic Tool Binding — ToolDiscoveryTool meta-tool
**Date**: 2026-03-31

## Overview

The Dynamic Tool Binding feature does not introduce new database tables. All new entities are **runtime data structures** — Pydantic models for input/output contracts and ephemeral LangChain tools constructed from registry bind responses. The existing `ToolUsageLog` table in the registry captures invocation metrics.

## Entity: ToolDiscoveryInput

The structured input schema for the `ToolDiscoveryTool` meta-tool. Defined as a Pydantic `BaseModel` and used as `args_schema` on the tool.

```python
class ToolDiscoveryInput(BaseModel):
    capability: str           # Registry capability tag (e.g., "sec_filings", "web_search")
    query: str                # The agent's research query
    constraints: dict = {}    # Research constraints from graph state
    gaps: list[str] = []      # Gaps identified by Critic for refinement
    agent_id: str = ""        # Calling agent identifier for usage logging
    session_id: str = ""      # Session ID for usage logging correlation
```

### Field Details

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `capability` | `str` | Yes | — | Explicit registry capability tag. Maps to `GET /tools/search?capability=X` |
| `query` | `str` | Yes | — | Research query for payload mapping and LLM tool selection context |
| `constraints` | `dict` | No | `{}` | Forwarded to registry search and tool invocation payload |
| `gaps` | `list[str]` | No | `[]` | Gaps from Critic, forwarded to tool payload for refinement |
| `agent_id` | `str` | No | `""` | Identifying agent for usage log entries |
| `session_id` | `str` | No | `""` | Session correlation for usage logs |

### Validation Rules

1. `capability` must be non-empty and match the registry's capability pattern (`^[a-z][a-z0-9_]*$`)
2. `query` must be non-empty

## Entity: ToolDiscoveryResult

The structured output of the `ToolDiscoveryTool`. Returned as a serialized JSON string from the tool's `_arun()` method.

```python
class ToolDiscoveryResult(BaseModel):
    success: bool                       # Whether any tool invocation succeeded
    tool_id: str | None = None          # tool_id of the successful tool (None if all failed)
    data: dict = {}                     # Raw output from the successful tool
    source: dict = {}                   # Source reference: {"url": str, "title": str, "tool_id": str}
    attempts: list[InvocationAttempt]   # All invocation attempts (success + failures)
    error: str | None = None            # Summary error message if all attempts failed
```

### Field Details

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | `True` if at least one tool was invoked successfully |
| `tool_id` | `str \| None` | The tool_id that produced the result, or `None` if all failed |
| `data` | `dict` | Raw output data from the successful tool invocation |
| `source` | `dict` | Source reference extracted from tool output: `url`, `title`, `tool_id` |
| `attempts` | `list[InvocationAttempt]` | Ordered list of all attempts — includes failed ones before the success |
| `error` | `str \| None` | Human-readable error if `success=False` (e.g., "all 3 tool attempts failed") |

## Entity: InvocationAttempt

A record of a single tool invocation attempt — success or failure.

```python
class InvocationAttempt(BaseModel):
    tool_id: str
    success: bool
    latency_ms: float
    error_message: str | None = None
```

### Field Details

| Field | Type | Description |
|-------|------|-------------|
| `tool_id` | `str` | Registry tool_id that was attempted |
| `success` | `bool` | Whether this specific attempt succeeded |
| `latency_ms` | `float` | Wall-clock time for the attempt in milliseconds |
| `error_message` | `str \| None` | Error details if `success=False` |

## Entity: ToolDiscoveryTool

Not a data model — a runtime `BaseTool` subclass. Holds references to infrastructure dependencies.

```python
class ToolDiscoveryTool(BaseTool):
    name: str = "tool_discovery"
    description: str = "Search the tool registry for a capability, select the best tool, and invoke it"
    args_schema: type[BaseModel] = ToolDiscoveryInput

    # Runtime dependencies (set via __init__)
    registry: RegistryClient
    llm: BaseChatModel
    config: AgentConfig
```

### Dependencies

| Dependency | Type | Source | Purpose |
|------------|------|--------|---------|
| `registry` | `RegistryClient` | Graph context | HTTP calls to registry (search, bind, invoke, log_usage) |
| `llm` | `BaseChatModel` | Graph context | LLM-based tool ranking/selection from search results |
| `config` | `AgentConfig` | Graph context | Timeouts, fallback cap, registry URL |

## Entity: DynamicTool (Ephemeral)

An ephemeral `StructuredTool` constructed at runtime from a registry bind response. Lives only for the duration of a single `ToolDiscoveryTool._arun()` invocation.

```python
# Not stored — constructed via build_dynamic_tool()
dynamic_tool = StructuredTool.from_function(
    coroutine=_invoke_endpoint,    # httpx async call to tool endpoint
    name=bind_response["name"],
    description=bind_response["description"],
    args_schema=DynamicArgsModel,  # Pydantic model generated from bind_response["args_schema"]
)
```

### Construction Inputs (from ToolBindResponse)

| Field | Source | Usage |
|-------|--------|-------|
| `name` | `bind_response.name` | Tool name in LangChain interface |
| `description` | `bind_response.description` | Tool description for LLM context |
| `args_schema` | `bind_response.args_schema` → `pydantic.create_model()` | Input validation |
| `endpoint` | `bind_response.endpoint` | HTTP target for invocation |
| `method` | `bind_response.method` | HTTP method (POST/GET) |

### Lifecycle

1. **Created**: When `ToolDiscoveryTool._arun()` calls `build_dynamic_tool(bind_response)`
2. **Used**: Invoked with a payload derived from `build_tool_payload()`
3. **Discarded**: After invocation completes (success or failure) — not cached

## Updated Entity: AgentConfig

Two new configuration fields added to the existing `AgentConfig`:

| Field | Type | Default | Env Var | Description |
|-------|------|---------|---------|-------------|
| `tool_invocation_timeout_seconds` | `int` | `30` | `TOOL_INVOCATION_TIMEOUT_SECONDS` | Per-tool HTTP call timeout |
| `max_tool_fallback_attempts` | `int` | `3` | `MAX_TOOL_FALLBACK_ATTEMPTS` | Max tools to try (primary + fallbacks) |

### Validation Rules

1. `tool_invocation_timeout_seconds` must be >= 1
2. `max_tool_fallback_attempts` must be >= 1 and <= 10

## Relationship to Existing Entities

| Dynamic Tool Binding | Existing Entity | Relationship |
|----------------------|-----------------|--------------|
| `ToolDiscoveryInput.capability` | `ToolCapability.capability` | Maps to registry search filter |
| `ToolDiscoveryResult.tool_id` | `Tool.tool_id` | Identifies which registry tool succeeded |
| `InvocationAttempt` → `log_usage()` | `ToolUsageLog` | Each attempt writes a usage log entry |
| `DynamicTool` construction | `ToolBindResponse` | 1:1 mapping from bind response to LangChain tool |
| `ToolDiscoveryTool.registry` | `RegistryClient` | Shared instance from graph context |
| `ToolDiscoveryTool.llm` | `BaseChatModel` | Same LLM used for tool selection (existing `ToolSelectionResponse`) |

## State Impact

No changes to `ResearchState`. The ToolDiscoveryTool operates within the Researcher node's existing state contract:

- **Reads**: `query`, `constraints`, `gaps`, `trace_id`, `session_id`
- **Writes** (via Researcher): `raw_findings`, `sources`, `iteration_count`, `token_usage`, `errors`

The ToolDiscoveryTool returns a `ToolDiscoveryResult` to the Researcher, which maps it into the state fields.
