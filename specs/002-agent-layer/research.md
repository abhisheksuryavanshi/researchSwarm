# Research: Agent Layer (LangGraph State Machine)

**Feature**: Agent Layer — LangGraph orchestration engine
**Date**: 2026-03-31

## Research Tasks

### 1. LangGraph StateGraph API — Version and Patterns

**Unknown**: Which LangGraph version and API surface to target for the state machine?

**Decision**: Target `langgraph>=1.1` (latest stable: 1.1.3, released March 2026).

**Rationale**: LangGraph 1.1 introduces type-safe streaming with `version="v2"` and `GraphOutput` objects. The `StateGraph` class is the canonical entry point. Nodes are async functions `(state) -> partial_state_update`. Edges are either fixed (`add_edge`) or conditional (`add_conditional_edges`). The API is stable and well-documented.

**Alternatives considered**:
- LangGraph 0.x: Outdated, pre-1.0 API surface has breaking changes
- Custom state machine (no framework): Rejected — LangGraph provides checkpointing, visualization, and conditional routing out of the box. Building from scratch would violate DRY and delay delivery.
- CrewAI / AutoGen: Rejected — these are higher-level frameworks that abstract away graph construction. We need fine-grained control over state flow, loop-back conditions, and per-node tool binding, which LangGraph provides natively.

### 2. State Schema Design — TypedDict vs Pydantic vs Dataclass

**Unknown**: Which schema mechanism to use for the graph state?

**Decision**: Use `TypedDict` with `Annotated` reducers.

**Rationale**: LangGraph natively supports `TypedDict`, `dataclass`, and Pydantic `BaseModel` for state schemas. `TypedDict` is the recommended and most performant option. Pydantic adds runtime validation overhead on every state transition (every node invocation), which is unnecessary since our nodes already validate their own outputs. `dataclass` would work but doesn't support `Annotated` reducers as cleanly. `TypedDict` with `Annotated[list, operator.add]` gives us accumulator semantics (appending to `raw_findings`, `sources`, `accumulated_context`) without custom code.

**Alternatives considered**:
- Pydantic BaseModel: Higher overhead per state transition, not recommended by LangGraph docs for performance-sensitive graphs
- dataclass: Viable but less idiomatic for LangGraph; TypedDict is the documented default
- Plain dict: No type safety, no IDE support, rejected

### 3. Conditional Edge — Critic-to-Researcher Loop-Back

**Unknown**: How to implement the quality gate and loop-back pattern?

**Decision**: Use `add_conditional_edges` from the Critic node with a routing function that inspects `state["critique_pass"]` and `state["iteration_count"]`.

**Rationale**: LangGraph's `add_conditional_edges(source, routing_fn)` accepts a function that reads state and returns the name of the next node. The routing function checks two conditions: (1) did the Critic pass the quality gate? (2) has the iteration count exceeded `max_iterations`? If critique fails and iterations remain, route back to `"researcher"`. Otherwise, route to `"synthesizer"`. Type-hinting the return as `Literal["researcher", "synthesizer"]` enables proper graph visualization.

```python
def route_after_critic(state: ResearchState) -> Literal["researcher", "synthesizer"]:
    if not state["critique_pass"] and state["iteration_count"] < state["max_iterations"]:
        return "researcher"
    return "synthesizer"
```

**Alternatives considered**:
- Fixed max_iterations=1 (no loop): Defeats the purpose of the Critic agent
- Unbounded loop: Risk of infinite LLM calls and cost explosion; rejected per Principle VI
- Human-in-the-loop at Critic: Desirable for future phases but adds complexity for v1; `max_iterations` bound is sufficient safety

### 4. LLM Provider Integration

**Unknown**: Which LLM provider and how to integrate?

**Decision**: Use `langchain-google-genai` with Gemini 2.0 Flash as default. Support provider switching via `litellm`.

**Rationale**: The spec states "Google GenAI by default (generous free tier for Gemini 2.0 Flash)." `langchain-google-genai` provides `ChatGoogleGenerativeAI` which is a LangChain-compatible chat model. For multi-provider support (OpenAI, Anthropic), `litellm` provides a unified interface. However, for v1 we start with direct `langchain-google-genai` integration and add `litellm` in a future iteration to keep the dependency surface small.

**Alternatives considered**:
- OpenAI directly: No free tier, requires API key from day 1
- litellm as sole provider: Adds indirection; for v1, direct Google GenAI is simpler
- langchain-openai + Cursor API key: Works but couples to Cursor; not portable

**Revised Decision**: Start with `langchain-google-genai` only. Add litellm when second provider is needed.

### 5. Tool Discovery and Binding at Runtime

**Unknown**: How do agents discover and invoke tools from the registry?

**Decision**: Build a thin `RegistryClient` (httpx-based) that wraps `GET /tools/search` and `GET /tools/{id}/bind`. The Researcher node calls `registry_client.search(capability=...)` to get available tools, then `registry_client.bind(tool_id)` to get a LangChain-compatible tool definition. Tool invocation is done via httpx to the tool's endpoint.

**Rationale**: Principle I mandates runtime discovery — no hardcoded tool lists. The existing registry already returns LangChain-compatible bind responses (`ToolBindResponse`). The Researcher is the only agent that invokes tools (Principle III — other agents must not gather data). The client is a simple async wrapper, not a full SDK.

**Alternatives considered**:
- Embed tool definitions in agent config: Violates Principle I
- Use LangChain's ToolNode: Possible but adds LangChain runtime dependency; our tools are HTTP endpoints, not Python functions
- Direct DB queries from agents: Violates layered independence (agents should not know about MySQL)

### 6. Observability Stack

**Unknown**: How to implement tracing and structured logging for agent nodes?

**Decision**: Use `structlog` (already a dependency) for structured JSON logging. Add `langfuse` for LLM call tracing. Every node function receives `trace_id` and `session_id` from state and includes them in all log entries.

**Rationale**: Principle V requires tracing via Langfuse, structured logging via structlog, and correlation IDs on every entry. Langfuse provides a Python SDK with LangChain callback integration (`LangfuseCallbackHandler`), which automatically traces LLM calls, token usage, and latency. structlog is already configured in `registry/middleware/logging.py`.

**Alternatives considered**:
- LangSmith: Proprietary to LangChain Inc., requires paid plan for production. Langfuse is open-source and self-hostable.
- OpenTelemetry directly: More general-purpose but doesn't have LLM-specific features (token tracking, prompt visualization). Langfuse is purpose-built for LLM observability.
- No tracing in v1: Violates Principle V — observability is infrastructure, not an afterthought.

### 7. Error Handling and Retry Strategy

**Unknown**: How to handle LLM failures, tool invocation failures, and partial state corruption?

**Decision**: Each node wraps its LLM call in a try/except with structured error logging. LLM calls use a 30-second timeout. Failed tool invocations log the error, report to the registry (usage stats), and attempt an alternative tool from the same capability category (Principle: graceful degradation). If all tools fail, the node writes an error message to its state field and the graph continues — the Critic will catch the gap.

**Rationale**: Constitution requires no silent failures and graceful degradation. LangGraph's `retry_policy` parameter on `add_node` can handle transient failures with exponential backoff. For semantic failures (bad LLM output), the Critic loop provides a natural recovery mechanism.

**Alternatives considered**:
- Fail-fast on any error: Too brittle; a single tool failure shouldn't abort the entire research
- Unlimited retries: Cost risk; bounded retries with backoff is standard
- Checkpoint and resume: LangGraph supports this via `MemorySaver`/`PostgresSaver`, but adds persistence complexity for v1. In-memory execution is sufficient for single-instance v1.

### 8. Package Structure — Separation from Registry

**Unknown**: Where does the agent code live relative to the existing registry package?

**Decision**: New `agents/` top-level package alongside `registry/`. Added to `pyproject.toml` package discovery. Agents depend on registry only via HTTP API (not Python imports).

**Rationale**: Principle II (Layered Independence) requires the research engine to be independently deployable. The `agents/` package communicates with `registry/` only through HTTP. In production, they can run in separate containers. In development, they share the same repo for convenience but have no code-level coupling.

**Alternatives considered**:
- `registry/agents/` sub-package: Violates Principle II — agents become coupled to the registry package
- Separate git repo: Premature for v1; monorepo with package boundaries is sufficient
- `src/agents/`: The project doesn't use a `src/` layout; `agents/` at root follows the `registry/` convention

### 9. Researcher Tool Selection Strategy (Clarification)

**Unknown**: How does the Researcher select which tools to invoke from search results?

**Decision**: Use the LLM to select the top 1-3 most relevant tools from search results based on query relevance, then invoke only those.

**Rationale**: Invoking all matching tools maximizes coverage but wastes latency and cost. A single tool is too narrow. LLM-based selection leverages the model's understanding of the query to pick the best matches — balancing coverage with efficiency. The Researcher passes the search results (tool name, description, capabilities) to the LLM along with the query, and the LLM returns the selected tool IDs. This uses `with_structured_output()` with a Pydantic model for type-safe parsing.

**Alternatives considered**:
- Invoke all matching tools: Higher latency/cost, diminishing returns at ~20-50 tools
- First match only: Misses better tools listed later
- Scoring heuristic (latency, cost, error_rate): No semantic understanding of relevance

### 10. Structured Output Parsing (Clarification)

**Unknown**: How should agent nodes parse structured output from the LLM?

**Decision**: Use LangChain's `with_structured_output()` with Pydantic response models.

**Rationale**: `with_structured_output()` binds a Pydantic model to the chat model, providing automatic validation and retry on parse failure. This eliminates manual JSON parsing and matches the project's existing Pydantic usage in `registry/schemas.py`. Each agent that needs structured output (Critic: `CritiqueResponse`, Researcher: `ToolSelectionResponse`) defines a Pydantic model in `agents/response_models.py`.

**Alternatives considered**:
- JSON mode + manual Pydantic: More boilerplate, no automatic retry on malformed output
- Prompt engineering + json.loads(): Fragile, no schema validation, error-prone
- Raw text parsing: Not feasible for boolean/list fields like `critique_pass` and `gaps`

### 11. LLM Rate Limiting & Graph Timeout (Clarification)

**Unknown**: What should happen when the LLM provider rate-limits requests mid-graph?

**Decision**: Retry with exponential backoff up to `llm_max_retries`. Enforce a per-graph total timeout of 60s. If cumulative wall time exceeds the budget, abort remaining nodes.

**Rationale**: Rate-limiting (HTTP 429) is transient and recoverable with backoff. However, unbounded retries could blow past the 60s budget. The per-graph timeout (tracked via `asyncio.timeout()` or similar) acts as a hard ceiling. When triggered, the graph returns partial results with a timeout error in `errors` — the Synthesizer can still produce partial output.

**Alternatives considered**:
- Retry without graph timeout: Risk of 5+ minute hangs during sustained rate limiting
- Fail immediately on 429: Too aggressive; most rate limits clear within seconds

### 12. Concurrency Model (Clarification)

**Unknown**: Can multiple research graph invocations run concurrently?

**Decision**: Single concurrent execution in v1. Callers receive a 429 if a graph is already running.

**Rationale**: Single-instance deployment on t3.micro with one LLM API key makes concurrent execution impractical — rate limits would be shared, state isolation adds complexity, and there's no user-facing need for concurrency in v1. An `asyncio.Lock` or semaphore guards the entry point. This can be relaxed to bounded concurrency in a future version.

**Alternatives considered**:
- Unbounded concurrency: Rate-limit contention, resource exhaustion on t3.micro
- Bounded concurrency (semaphore): Viable for v2 but premature for single-instance v1

### 13. Agent LLM Call Independence (Clarification)

**Unknown**: Should agents share conversation history via the `messages` field?

**Decision**: Independent calls. Each agent constructs its own prompt from relevant state fields. `messages` is an append-only audit log.

**Rationale**: Sharing conversation history would leak context across agent boundaries, violating Principle III (Agent Autonomy). It would also inflate token usage — the Synthesizer would receive all prior prompts/responses in its context window. Independent calls ensure each agent sees only the state fields it needs. The `messages` field records all LLM interactions for debugging and tracing but is never read by agent nodes for prompt construction.

**Alternatives considered**:
- Shared history: Violates Principle III, inflates token cost by 3-4x on later nodes
- Selective sharing: Adds complexity deciding which pairs share; cleaner to keep all independent
