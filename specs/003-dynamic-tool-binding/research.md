# Research: Dynamic Tool Binding

**Feature**: Dynamic Tool Binding — ToolDiscoveryTool meta-tool
**Date**: 2026-03-31

## Research Tasks

### 1. LangChain StructuredTool — Dynamic Construction from JSON Schema

**Unknown**: How to construct a LangChain `StructuredTool` at runtime from a JSON Schema (args_schema) received from the registry bind endpoint?

**Decision**: Use `langchain_core.tools.StructuredTool.from_function()` with a dynamically generated Pydantic model built from the JSON Schema via `pydantic.create_model()`. The generated model serves as the `args_schema` parameter. The coroutine passed to `from_function()` wraps an httpx call to the tool's endpoint.

**Rationale**: `StructuredTool.from_function()` is the canonical LangChain API for creating tools from callables. It accepts an `args_schema` parameter (Pydantic BaseModel) for input validation. Since our bind response provides a JSON Schema, we convert it to a Pydantic model at construction time using `pydantic.create_model()` with field definitions derived from the schema's `properties` and `required` fields. This gives us runtime input validation before the HTTP call. For tools with empty or missing schemas, we fall back to a generic model with `query: str` and optional `constraints: dict`.

**Alternatives considered**:
- `Tool()` (simple string-in/string-out): No structured input validation, no args_schema support
- Manual httpx call without LangChain wrapping: Works but doesn't conform to the LangChain tool interface — agents can't invoke it through standard tool-calling
- Pre-register all tools as Python functions: Violates Principle I (dynamic discovery) — tools must be constructed at runtime

### 2. Fallback Strategy — Sequential with LLM-Ranked Order

**Unknown**: What fallback ordering strategy to use when the primary tool fails?

**Decision**: Try tools in LLM-ranked order (the order returned by `ToolSelectionResponse.selected_tool_ids`), capped at 3 total attempts. If the LLM selected fewer than 3 tools, use remaining search results sorted by `avg_latency_ms` ascending (lowest latency = most reliable) to fill the fallback slots.

**Rationale**: The LLM has already ranked tools by relevance to the query. Trying them in order maximizes the chance of getting the best result. The 3-attempt cap (clarification decision) ensures we don't exhaust the graph timeout on fallbacks. If the LLM only selected 1 tool, we need 2 fallback candidates from the search results — sorting by latency is a reasonable proxy for reliability (fast tools tend to be more stable).

**Alternatives considered**:
- Random fallback order: No semantic ranking, suboptimal
- Reverse LLM order (try worst first): Counter-intuitive, wastes the primary attempt
- Parallel invocation of all candidates: Higher resource cost, complicates error handling, and the first response might not be the best
- No fallback (fail immediately): Violates Constitution's graceful degradation requirement

### 3. ToolDiscoveryTool Input Contract — Explicit Capability String

**Unknown**: How does the calling agent specify what capability it needs?

**Decision**: The `ToolDiscoveryInput` schema requires an explicit `capability` string field (a registry capability tag like `"sec_filings"` or `"web_search"`). The agent determines the tag; the meta-tool does not use the LLM to infer it.

**Rationale**: Clarification decision — the Researcher's LLM already selects capabilities as part of its prompt. Adding a second LLM call in the meta-tool for tag inference would duplicate work and add latency. The meta-tool is a focused executor, not a query interpreter. The `capability` field maps directly to `GET /tools/search?capability=X`.

**Alternatives considered**:
- LLM inference in meta-tool: Extra LLM call per invocation (~1-3s latency), duplicates the agent's existing capability analysis
- Keyword extraction heuristic: Fragile, won't match registry tags reliably
- Both (optional inference fallback): Adds complexity for a scenario that shouldn't occur — agents always know what capability they need

### 4. Payload Mapping Strategy — Schema-Aware with Fallback

**Unknown**: How to map the agent's query/constraints/gaps into the tool's args_schema?

**Decision**: Reuse the existing `_build_tool_payload()` logic from `agents/nodes/researcher.py`. Extract it into `agents/tools/discovery.py` as a public function. This function inspects the tool's `args_schema.properties`, maps known field names (query, constraints, gaps) to matching keys, and fills required fields with type-aware fallbacks.

**Rationale**: The Researcher already has a robust payload mapper (`_build_tool_payload`) with 7+ field matchers and type-aware fallback for required fields. Rewriting this in the ToolDiscoveryTool would duplicate logic. Extracting it as a shared function is cleaner and ensures consistent behavior before and after the Researcher refactoring. The mapper handles: query-like fields, constraint fields, gap fields, constraint key matching, defaults from schema, and required field fallbacks.

**Alternatives considered**:
- LLM-generated payloads: High latency, unreliable for strict schemas, extra cost
- Simple `{"query": query}` only: Would break tools that expect specific field names
- New payload mapper from scratch: Duplicates tested logic already in the codebase

### 5. ToolDiscoveryTool as a LangChain Tool — Self-Registration Pattern

**Unknown**: How should the ToolDiscoveryTool itself be a LangChain `StructuredTool`?

**Decision**: Create `ToolDiscoveryTool` as a subclass of `langchain_core.tools.BaseTool` (not `StructuredTool.from_function()`). Override `_arun()` with the async search→select→bind→invoke pipeline. Define `args_schema = ToolDiscoveryInput` (Pydantic model). This gives full control over async execution, error handling, and the invocation lifecycle.

**Rationale**: `BaseTool` subclassing is the recommended approach for tools with complex async behavior. `StructuredTool.from_function()` works for simple callables but doesn't provide clean lifecycle management (we need to hold references to the RegistryClient and LLM instance). A subclass can accept dependencies via `__init__` and implement `_arun()` for the full pipeline. The `args_schema` attribute makes it discoverable by LLM tool-calling.

**Alternatives considered**:
- `StructuredTool.from_function()` with closure: Works but closures over registry/LLM are less testable and harder to inspect
- Plain function (not a Tool): Agents can't discover it through standard tool-calling interface
- `@tool` decorator: Doesn't support async or dependency injection cleanly

### 6. Per-Tool Invocation Timeout

**Unknown**: How to implement per-tool invocation timeout that's separate from the graph timeout?

**Decision**: Use `asyncio.timeout(config.tool_invocation_timeout_seconds)` around each individual tool invocation (the httpx call). Default: 30 seconds. This timeout fires independently of the graph-level 60s timeout. When triggered, it raises `TimeoutError`, which the fallback loop catches and treats as a tool failure — triggering the next fallback attempt.

**Rationale**: `asyncio.timeout()` (Python 3.11+) is the standard library mechanism for async timeouts. It wraps the httpx call cleanly. The 30s default matches the existing `llm_timeout_seconds` in AgentConfig and gives ample time for most tool endpoints while preventing indefinite hangs. The graph-level timeout remains the ultimate safety net.

**Alternatives considered**:
- httpx timeout only: httpx has its own timeout, but it's configured at client creation time and can't be easily overridden per-call. `asyncio.timeout()` is more granular.
- No per-tool timeout (rely on graph timeout only): A single slow tool could consume the entire 60s budget, leaving no time for fallback
- Lower timeout (5s): Too aggressive for tools that legitimately take 10-20s (e.g., web scrapers)

### 7. Config Extension — New AgentConfig Fields

**Unknown**: What configuration fields should be added for the ToolDiscoveryTool?

**Decision**: Add two fields to `AgentConfig`:
- `tool_invocation_timeout_seconds: int = 30` — per-tool HTTP call timeout
- `max_tool_fallback_attempts: int = 3` — fallback attempt cap (including primary)

**Rationale**: Both values are referenced in the spec (FR-009, FR-010) and need to be configurable. Adding them to the existing `AgentConfig` (pydantic-settings) means they're automatically loadable from environment variables (`TOOL_INVOCATION_TIMEOUT_SECONDS`, `MAX_TOOL_FALLBACK_ATTEMPTS`). No new config class needed.

**Alternatives considered**:
- Separate `ToolConfig` class: Over-engineered for 2 fields; AgentConfig already handles tool-related config (`registry_base_url`)
- Hardcoded constants: Violates principle of configurability; production may need different values
- Constructor parameters only: Doesn't support env var loading
