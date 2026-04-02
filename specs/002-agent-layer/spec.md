# Feature Specification: Agent Layer

**Feature Branch**: `002-agent-layer`
**Created**: 2026-03-31
**Status**: Draft
**Input**: User description: "Implement the Agent layer — LangGraph state machine with four agents (Researcher, Analyst, Critic, Synthesizer), typed state schema with constraints dict and accumulated_context, and conditional graph with Critic-to-Researcher loop-back."

## Clarifications

### Session 2026-03-31

- Q: How does the Researcher select which tools to invoke from search results? → A: The Researcher uses the LLM to select the top 1-3 most relevant tools from search results based on query relevance, then invokes only those (not all matches).
- Q: What should happen when the LLM provider rate-limits requests mid-graph? → A: Retry with exponential backoff up to `llm_max_retries`, but also enforce a per-graph total timeout (60s). If cumulative wall time exceeds the budget, abort remaining nodes.
- Q: How should agent nodes parse structured output from the LLM? → A: Use LangChain's `with_structured_output()` on the chat model — pass a Pydantic model, get validated structured output automatically.
- Q: Can multiple research graph invocations run concurrently? → A: One at a time in v1. Single concurrent graph execution; callers queue or get a 429 if one is already running.
- Q: Should each agent node make independent LLM calls, or share conversation history via the `messages` field? → A: Independent calls. Each agent constructs its own prompt from state fields; `messages` is used as an append-only audit log, not shared context.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Research Query Execution (Priority: P1)

A caller invokes the research graph with a query (e.g., "What are the latest
advances in transformer architectures?"), a trace_id, and a session_id. The
graph executes the full pipeline: Researcher gathers raw findings via the
Tool Registry, Analyst structures them, Critic evaluates quality, and
Synthesizer produces the final output. The caller receives a state containing
a non-empty synthesis, accumulated sources, and token usage metrics.

**Why this priority**: This is the end-to-end core flow. Nothing else matters
if the pipeline doesn't execute.

**Independent Test**: Invoke the compiled graph with a test query (mocked LLM
and registry), verify the output state contains non-empty synthesis, sources,
analysis, and critique fields.

**Acceptance Scenarios**:

1. **Given** a compiled research graph and a valid input state (query,
   trace_id, session_id), **When** the graph is invoked, **Then** the
   output state contains a non-empty `synthesis` field.
2. **Given** a graph invocation, **When** all agents execute successfully,
   **Then** `token_usage` contains keys for all four agents with positive
   values.
3. **Given** a graph invocation, **When** the Researcher gathers findings,
   **Then** `sources` is a deduplicated list of source references.

---

### User Story 2 — Critic Quality Gate & Loop-Back (Priority: P1)

The Critic agent evaluates the quality of the analysis and raw findings. If
quality is insufficient (`critique_pass=False`), the graph routes back to
the Researcher with specific `gaps` to address. The loop continues until
the Critic passes or `max_iterations` is reached.

**Why this priority**: The loop-back mechanism is the defining architectural
feature that differentiates this from a linear pipeline. Without it, the
Critic serves no purpose.

**Independent Test**: Invoke the graph with a mocked LLM that returns
`critique_pass=False` on the first iteration and `True` on the second.
Verify `iteration_count=2` and `critique_pass=True` in the output.

**Acceptance Scenarios**:

1. **Given** the Critic returns `critique_pass=False` on iteration 1,
   **When** `iteration_count < max_iterations`, **Then** the graph routes
   back to the Researcher.
2. **Given** the Critic returns `critique_pass=False` on all iterations,
   **When** `iteration_count >= max_iterations`, **Then** the graph
   proceeds to the Synthesizer (budget exhaustion).
3. **Given** the Critic returns `critique_pass=True`, **When** at any
   iteration, **Then** the graph proceeds directly to the Synthesizer.
4. **Given** a loop-back to the Researcher, **When** the Researcher
   re-executes, **Then** it uses `gaps` from the Critic to refine its
   search queries.

---

### User Story 3 — Dynamic Tool Discovery & Binding (Priority: P1)

The Researcher agent discovers tools at runtime by querying the Tool
Registry's search endpoint with capability tags derived from the query. It
then uses the LLM to select the top 1-3 most relevant tools from the search
results based on query relevance, binds the selected tools to get
LangChain-compatible definitions, and invokes them to gather data. No tool
is hardcoded in the agent.

**Why this priority**: Constitution Principle I mandates dynamic tool
architecture. The Researcher is the only agent that interacts with tools.

**Independent Test**: Mock the Tool Registry to return 3 tools, invoke the
Researcher node, verify it calls search, binds at least 1 tool, invokes it,
and logs the invocation to the registry.

**Acceptance Scenarios**:

1. **Given** a registry with tools matching the query's capabilities,
   **When** the Researcher executes, **Then** it discovers tools via
   `GET /tools/search` and binds them via `GET /tools/{id}/bind`.
2. **Given** a tool invocation that fails, **When** another tool with the
   same capability exists, **Then** the Researcher attempts the alternative
   tool before recording an error.
3. **Given** each tool invocation, **When** it completes (success or
   failure), **Then** the Researcher logs usage to the registry with
   `agent_id`, `session_id`, `latency_ms`, and `success`.

---

### User Story 4 — State Schema with Constraints & Accumulated Context (Priority: P1)

The graph state schema (`ResearchState`) is a TypedDict with Annotated
reducers. It includes `constraints` (a dict for source filters, entity
focus, and depth parameters) and `accumulated_context` (a list of strings
from prior sessions). These fields enable the future Conversational Layer
to steer agent behavior without engine-side refactoring.

**Why this priority**: Constitution Principle VII mandates these fields from
day one. The state schema is the contract between all agents — it must be
correct before any node is implemented.

**Independent Test**: Validate the state schema type annotations, test
each custom reducer (_dedupe_sources, _merge_token_usage) with sample
data, and verify input validation rejects invalid states.

**Acceptance Scenarios**:

1. **Given** a state with `constraints={"sources": ["arxiv"]}`, **When**
   the Researcher executes, **Then** it passes constraints to tool search.
2. **Given** a state with `accumulated_context=["prior findings..."]`,
   **When** the Analyst executes, **Then** it includes accumulated context
   in its analysis.
3. **Given** sources from two iterations with overlapping URLs, **When**
   the `_dedupe_sources` reducer merges them, **Then** no duplicate URLs
   exist in the result.
4. **Given** token usage from two agents, **When** the `_merge_token_usage`
   reducer merges them, **Then** counts are summed per agent key.

---

### User Story 5 — Agent Observability (Priority: P2)

Every agent node emits structured JSON logs via `structlog` with
`trace_id`, `session_id`, and `agent_id` on every entry. LLM calls are
traced via Langfuse with token usage, latency, and prompt details. No
exceptions are silently swallowed.

**Why this priority**: Constitution Principle V mandates observability as
infrastructure, not an afterthought. However, the pipeline functions
without it, so it's P2 rather than P1.

**Independent Test**: Invoke a node with a test state, capture structlog
output, verify all entries contain `trace_id`, `session_id`, and
`agent_id`. Verify Langfuse callback is attached to LLM calls.

**Acceptance Scenarios**:

1. **Given** any agent node execution, **When** it logs, **Then** every
   log entry includes `trace_id`, `session_id`, and `agent_id`.
2. **Given** an LLM call in any agent, **When** Langfuse is enabled,
   **Then** the call is traced with token usage and latency.
3. **Given** a tool invocation failure, **When** it occurs, **Then** the
   error is logged with full context before being added to `errors`.
4. **Given** `token_usage` exceeds a warning threshold, **When** a node
   completes, **Then** a warning is logged.

---

### User Story 6 — Agent Configuration (Priority: P2)

The agent layer reads configuration from environment variables via
pydantic-settings. Configuration includes LLM provider, model, temperature,
timeouts, retry policy, max_iterations, registry URL, and Langfuse settings.
All fields have sensible defaults.

**Why this priority**: Configuration is infrastructure. The pipeline can
function with hardcoded defaults during development, but must be
configurable for production.

**Independent Test**: Set environment variables, instantiate AgentConfig,
verify all fields are loaded correctly. Test defaults when no env vars set.

**Acceptance Scenarios**:

1. **Given** `GOOGLE_API_KEY` and `LLM_MODEL` environment variables,
   **When** AgentConfig is loaded, **Then** the LLM is initialized with
   those values.
2. **Given** no environment variables set, **When** AgentConfig is loaded,
   **Then** all fields use documented defaults (model=gemini-3.1-flash-live-preview,
   temperature=0.1, timeout=30s, max_iterations=3).
3. **Given** `MAX_ITERATIONS=6` (exceeds bound), **When** AgentConfig is
   loaded, **Then** a validation error is raised.

---

### Edge Cases

- What happens when the Tool Registry is unreachable? The RegistryClient
  raises a connection error. The Researcher logs the error, adds it to
  `errors`, and continues with empty findings. The Critic will flag the
  gap.
- What happens when the LLM returns malformed output? Agents use LangChain's
  `with_structured_output()` which automatically validates against a Pydantic
  model. On parse failure, the call is retried up to `llm_max_retries` times
  with exponential backoff. If all retries fail, an error is added to
  `errors` and the node continues with a fallback default.
- What happens when the LLM provider rate-limits (429)? Retry with
  exponential backoff up to `llm_max_retries`. A per-graph total timeout
  of 60s is enforced — if cumulative wall time exceeds the budget, remaining
  nodes are aborted and the Synthesizer produces a partial output noting
  the timeout.
- What happens when `max_iterations=1` and the Critic fails? The graph
  proceeds to the Synthesizer. The synthesis includes a limitations note.
- What happens when all tools fail for the Researcher? `raw_findings` is
  empty. The Analyst produces analysis noting lack of data. The Critic
  flags the gap. If on the last iteration, the Synthesizer notes the
  limitation.
- What happens when `constraints` contains an unknown key? Ignored silently
  by agents. Only documented keys (`sources`, `date_range`, `max_depth`,
  `entity_focus`, `format`) are acted upon.
- What happens if the same query is run twice in the same session? Each
  invocation is independent. `accumulated_context` carries prior findings
  only if the caller explicitly passes them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST implement a LangGraph `StateGraph` with four
  nodes: Researcher, Analyst, Critic, Synthesizer.
- **FR-002**: System MUST use a `TypedDict` state schema (`ResearchState`)
  with `Annotated` reducers for accumulator fields (`raw_findings`,
  `sources`, `accumulated_context`, `messages`, `token_usage`, `errors`).
- **FR-003**: System MUST include `constraints: dict[str, Any]` and
  `accumulated_context: list[str]` fields in the state schema from day one.
- **FR-004**: System MUST implement a conditional edge from the Critic node
  that routes to the Researcher when `critique_pass=False` and
  `iteration_count < max_iterations`, and to the Synthesizer otherwise.
- **FR-005**: The Researcher MUST discover tools at runtime via the Tool
  Registry HTTP API, use the LLM to select the top 1-3 most relevant tools
  from search results, then bind and invoke only the selected tools. No
  hardcoded tool lists.
- **FR-006**: The Researcher MUST log every tool invocation to the registry
  with `agent_id`, `session_id`, `latency_ms`, and `success`.
- **FR-007**: The Researcher MUST attempt an alternative tool from the same
  capability category when a tool invocation fails.
- **FR-008**: Each agent MUST write only to its designated state fields per
  the contracts (no scope leakage across agent boundaries).
- **FR-008a**: Agents requiring structured output (Critic: critique_pass +
  gaps; Researcher: tool selection) MUST use LangChain's
  `with_structured_output()` with Pydantic response models for type-safe
  LLM output parsing.
- **FR-008b**: Each agent MUST make independent LLM calls, constructing its
  own prompt from relevant state fields. Agents MUST NOT read earlier
  agents' prompts/responses from `messages`. The `messages` field serves
  as an append-only audit log.
- **FR-009**: The Synthesizer MUST include a limitations note when
  `critique_pass=False` (budget exhaustion).
- **FR-010**: The graph MUST validate input state at invocation (non-empty
  query, valid trace_id, max_iterations in [1,5]).
- **FR-011**: System MUST use structured JSON logging via `structlog` with
  `trace_id`, `session_id`, and `agent_id` on every log entry.
- **FR-012**: System MUST trace LLM calls via Langfuse with token usage
  and latency.
- **FR-013**: System MUST track `token_usage` per agent, per session,
  merged via the `_merge_token_usage` reducer.
- **FR-014**: System MUST load configuration from environment variables via
  pydantic-settings with documented defaults.
- **FR-015**: System MUST enforce a per-graph total timeout (default 60s).
  If cumulative wall time exceeds the budget, remaining nodes are aborted
  and the graph returns partial results with a timeout error in `errors`.

### Key Entities

- **ResearchState**: The TypedDict state schema — 17 fields with reducers
  for accumulator semantics. The contract between all agents.
- **AgentConfig**: Runtime configuration loaded from environment variables.
  LLM provider, model, timeouts, max_iterations, registry URL, Langfuse.
- **RegistryClient**: Async HTTP client wrapping the Tool Registry API.
  Methods: search, bind, invoke, log_usage.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: End-to-end graph execution completes in < 60 seconds with
  mocked tools (real LLM).
- **SC-002**: Critic loop-back executes correctly: iteration_count
  increments, gaps are passed to Researcher, max_iterations is respected.
- **SC-003**: `_dedupe_sources` reducer produces zero duplicate URLs across
  multiple iterations.
- **SC-004**: All structured logs include `trace_id`, `session_id`, and
  `agent_id` fields.
- **SC-005**: Contract tests validate input/output state schema for each
  agent node.
- **SC-006**: `token_usage` is tracked and summed correctly across all
  agents in the final state.
- **SC-007**: Graph visualization (draw_ascii) shows the expected topology
  including the Critic→Researcher conditional edge.

## Assumptions

- The Tool Registry Service (feature 001) is implemented and running at
  `REGISTRY_BASE_URL` (default `http://localhost:8000`).
- LLM provider is Google GenAI (`gemini-3.1-flash-live-preview`) by default. Quota / tier
  sufficient for development and testing.
- Agent layer runs in-process (no separate container in v1). Deployed
  alongside the registry on the same EC2 instance.
- No authentication on the registry or agent layer — internal network only.
- In-memory graph execution (no checkpointing/persistence in v1). State
  is ephemeral per invocation.
- Single concurrent graph execution in v1. If a graph is already running,
  subsequent callers receive a 429 (busy) response.
- The Conversational Layer (future feature) will consume the agent layer
  as a library. The agent layer MUST NOT depend on conversational code.
