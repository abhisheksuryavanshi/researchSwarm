# Feature Specification: Dynamic Tool Binding

**Feature Branch**: `003-dynamic-tool-binding`  
**Created**: 2026-03-31  
**Status**: Draft  
**Input**: User description: "Build the Dynamic Tool Binding system — a ToolDiscoveryTool meta-tool that agents invoke at runtime to search the registry, select a matching tool, construct a LangChain-compatible callable, bind it, and invoke it with failure fallback strategies."

## Clarifications

### Session 2026-03-31

- Q: Should there be a cap on how many fallback tools the ToolDiscoveryTool attempts before giving up? → A: Cap at 3 total attempts (primary + 2 fallbacks).
- Q: Is refactoring the Researcher node to delegate to the ToolDiscoveryTool in scope for this feature? → A: Yes, in scope — build the meta-tool AND refactor the Researcher to use it.
- Q: Does the calling agent provide an explicit capability string or does the meta-tool infer it via LLM? → A: Explicit capability string — the agent passes a registry capability tag directly. No extra LLM call for capability inference.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Agent Discovers and Invokes a Tool at Runtime (Priority: P1)

An agent (e.g., the Researcher) encounters a query requiring a capability it does not have hardcoded. Instead of failing or returning empty results, the agent invokes the `ToolDiscoveryTool` meta-tool with a natural language description of the capability it needs (e.g., "parse SEC filings"). The meta-tool searches the Tool Registry, uses the LLM to rank and select the best-matching tool, constructs a LangChain-compatible callable from the bind response, invokes it with the appropriate payload, and returns the results to the agent — all within a single tool call.

**Why this priority**: This is the end-to-end core flow. The entire feature exists to make this work. Without it, agents cannot dynamically use tools they were not pre-configured with.

**Independent Test**: Provide the ToolDiscoveryTool with a capability query against a mock registry containing 3 tools. Verify it searches, selects the most relevant tool, constructs a callable, invokes it, and returns the tool's output.

**Acceptance Scenarios**:

1. **Given** a registry containing tools with matching capabilities, **When** the ToolDiscoveryTool is invoked with a capability description, **Then** it returns the selected tool's output and metadata (tool_id, latency, source information).
2. **Given** a registry containing multiple tools for the same capability, **When** the ToolDiscoveryTool is invoked, **Then** it uses the LLM to rank and select the best-matching tool based on the agent's query context.
3. **Given** a successful tool invocation, **When** the result is returned, **Then** the ToolDiscoveryTool logs usage to the registry with agent_id, session_id, latency_ms, and success status.

---

### User Story 2 — Fallback on Tool Invocation Failure (Priority: P1)

An agent invokes the ToolDiscoveryTool, which selects and attempts to call a tool. The tool invocation fails (network error, timeout, invalid response). The meta-tool automatically identifies an alternative tool with the same capability from the search results and retries with that alternative. If all alternatives are exhausted, it returns a structured error with details of every attempt.

**Why this priority**: Tools are external services that can fail at any time. Without fallback, a single tool failure would block the entire research pipeline. The fallback mechanism is what makes dynamic tool binding production-ready.

**Independent Test**: Mock a registry with 3 tools for the same capability. Configure the first two to fail (timeout and HTTP 500). Verify the ToolDiscoveryTool tries each in LLM-ranked order and succeeds with the third tool.

**Acceptance Scenarios**:

1. **Given** the top-ranked tool fails during invocation, **When** alternative tools with the same capability exist, **Then** the ToolDiscoveryTool attempts the next-ranked alternative.
2. **Given** all tools for a capability fail (up to the 3-attempt cap), **When** no more attempts remain, **Then** the ToolDiscoveryTool returns a structured error listing each tool attempted, the failure reason, and the latency of each attempt.
3. **Given** a tool times out, **When** a per-tool invocation timeout is configured, **Then** the ToolDiscoveryTool aborts the call and proceeds to the fallback without waiting indefinitely.
4. **Given** a fallback succeeds, **When** usage is logged, **Then** both the failed attempt(s) and the successful attempt are logged individually with accurate latency and success status.

---

### User Story 3 — LangChain-Compatible Callable Construction (Priority: P1)

The ToolDiscoveryTool receives a bind response from the registry (name, description, args_schema, endpoint, method, return_schema) and constructs a fully functional LangChain `StructuredTool` from it. This constructed tool can be invoked like any native LangChain tool, with input validation against the args_schema and output conforming to the return_schema.

**Why this priority**: The core value proposition of dynamic binding is that discovered tools behave identically to hardcoded tools. If the constructed callable doesn't conform to the LangChain tool interface, it cannot participate in the agent's tool-calling loop.

**Independent Test**: Provide a bind response with a known args_schema and endpoint. Verify the constructed StructuredTool has the correct name, description, and args_schema, and that calling it sends the properly shaped HTTP request to the endpoint.

**Acceptance Scenarios**:

1. **Given** a bind response with a valid args_schema, **When** the ToolDiscoveryTool constructs a callable, **Then** the resulting tool has a name, description, and args_schema matching the bind response.
2. **Given** a constructed tool, **When** it is invoked with a payload matching the args_schema, **Then** it makes an HTTP request to the tool's endpoint with the correct method and payload.
3. **Given** a constructed tool, **When** it is invoked with a payload that violates the args_schema, **Then** input validation raises an error before sending the HTTP request.

---

### User Story 4 — ToolDiscoveryTool as a LangChain Tool (Priority: P2)

The ToolDiscoveryTool itself is a LangChain-compatible tool that agents can invoke through the standard LangChain tool-calling interface. It accepts a structured input (capability description, query context, constraints) and returns structured output. This means any agent in the graph — not just the Researcher — can discover and use tools without custom orchestration code.

**Why this priority**: Making the meta-tool itself LangChain-compatible means agents can choose to discover tools through the standard tool-calling mechanism rather than requiring special-case code. However, the core search-bind-invoke flow (P1 stories) must work first.

**Independent Test**: Bind the ToolDiscoveryTool to a LangChain agent, invoke the agent with a query that triggers tool use. Verify the agent invokes the ToolDiscoveryTool through the standard tool-calling interface.

**Acceptance Scenarios**:

1. **Given** the ToolDiscoveryTool is registered as a LangChain tool, **When** an agent's LLM decides to call it, **Then** the tool is invoked through the standard tool-call interface with structured input.
2. **Given** the ToolDiscoveryTool completes execution, **When** it returns results, **Then** the output is a structured response that the LLM can parse and reason about.

---

### User Story 5 — Registry Search with Constraint Forwarding (Priority: P2)

When an agent invokes the ToolDiscoveryTool, it passes along the current research constraints (source filters, date ranges, entity focus) from the graph state. The meta-tool uses these constraints to filter and rank search results from the registry, and forwards relevant constraints to the selected tool's invocation payload.

**Why this priority**: Constraint forwarding ensures that the conversational layer's ability to steer research carries through to dynamically discovered tools. Without it, discovered tools would ignore the user's narrowing instructions.

**Independent Test**: Invoke the ToolDiscoveryTool with constraints `{"sources": ["arxiv"]}`. Verify the capability search is scoped accordingly and the selected tool receives the constraints in its payload.

**Acceptance Scenarios**:

1. **Given** constraints include a capability filter, **When** the ToolDiscoveryTool searches the registry, **Then** it passes the capability filter to the search endpoint.
2. **Given** constraints include domain-specific parameters, **When** a tool is invoked, **Then** the relevant constraints are mapped into the tool's input payload based on its args_schema.

---

### Edge Cases

- What happens when the registry is unreachable? The ToolDiscoveryTool returns a structured error indicating the registry connection failed, including the exception details. The calling agent adds this to the graph's `errors` list and continues with empty findings.
- What happens when no tools match the requested capability? The ToolDiscoveryTool returns a structured "no tools found" response with the capability that was searched. The agent can then fall back to its general-purpose behavior.
- What happens when the LLM fails to select a tool from the search results? The ToolDiscoveryTool falls back to selecting the top tool by registry ranking (lowest avg_latency_ms among active tools) and proceeds with invocation.
- What happens when a tool's args_schema is empty or missing? The ToolDiscoveryTool constructs a default payload containing the query, constraints, and gaps — the same fallback behavior currently used in the Researcher node.
- What happens when a tool returns an unexpected response format? The ToolDiscoveryTool wraps the response in a standardized output envelope with `tool_id`, `raw_data`, and `success` fields so the calling agent can process it uniformly.
- What happens when multiple agents try to discover tools concurrently within the same graph? Each ToolDiscoveryTool invocation is stateless and uses the shared registry client from the graph context. Concurrent calls are safe because the registry client supports async operations.
- What happens when a tool invocation exceeds the per-tool timeout but hasn't yet exhausted the graph-level timeout? The per-tool timeout fires, the ToolDiscoveryTool logs the failure, and attempts the next fallback tool. The graph-level timeout remains the ultimate safety net.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `ToolDiscoveryTool` meta-tool that encapsulates the full search → select → bind → invoke pipeline in a single callable.
- **FR-002**: The `ToolDiscoveryTool` MUST be a LangChain-compatible `StructuredTool` with a defined input schema (capability description, query context, constraints) and structured output.
- **FR-003**: The `ToolDiscoveryTool` MUST search the Tool Registry via `GET /tools/search` using an explicit capability string provided by the calling agent. The meta-tool does not infer capability tags — the agent is responsible for determining the appropriate tag.
- **FR-004**: The `ToolDiscoveryTool` MUST use the LLM to rank and select the best-matching tool(s) from search results when multiple candidates exist.
- **FR-005**: When the LLM is unavailable for tool selection, the system MUST fall back to selecting the top tool by registry ranking (lowest average latency among active tools).
- **FR-006**: The `ToolDiscoveryTool` MUST construct a LangChain-compatible `StructuredTool` from the bind response (`GET /tools/{id}/bind`), mapping name, description, args_schema, endpoint, and method.
- **FR-007**: Constructed tools MUST validate input payloads against the tool's args_schema before sending HTTP requests.
- **FR-008**: The `ToolDiscoveryTool` MUST invoke the constructed tool with a payload derived from the agent's query, constraints, and gaps, mapped to the tool's args_schema.
- **FR-009**: When a tool invocation fails, the system MUST automatically attempt the next-ranked alternative tool with the same capability, up to a maximum of 3 total attempts (primary + 2 fallbacks). The system stops on first success or after all 3 attempts are exhausted.
- **FR-010**: The system MUST enforce a configurable per-tool invocation timeout (default: 30 seconds) that aborts a single tool call and triggers fallback.
- **FR-011**: The `ToolDiscoveryTool` MUST log every tool invocation attempt (success or failure) to the registry via `POST /tools/usage-log` with agent_id, session_id, latency_ms, success, and error_message.
- **FR-012**: The `ToolDiscoveryTool` MUST return a structured response containing: tool_id of the tool that succeeded (or null), the tool's output data, a list of all attempts with tool_id/success/latency/error, and overall success status.
- **FR-013**: The `ToolDiscoveryTool` MUST forward research constraints from the graph state to both the registry search query and the tool invocation payload.
- **FR-014**: The `ToolDiscoveryTool` MUST handle tools with missing or empty args_schema by constructing a default payload (query + constraints + gaps).
- **FR-015**: The system MUST wrap all tool responses in a standardized output envelope with `tool_id`, `raw_data`, `success`, and `attempts` fields.
- **FR-016**: The Researcher node MUST be refactored to delegate its existing inline search → bind → invoke logic to the ToolDiscoveryTool, eliminating code duplication. All existing Researcher acceptance tests MUST continue to pass after the refactoring.

### Key Entities

- **ToolDiscoveryTool**: The meta-tool — a LangChain `StructuredTool` that agents invoke to dynamically discover and use registry tools. Accepts capability description, query context, and constraints as input.
- **ToolDiscoveryInput**: The structured input schema for the meta-tool — defines the fields an agent must provide: capability (explicit registry capability tag, required), query, constraints, gaps, agent_id, session_id.
- **ToolDiscoveryResult**: The structured output of the meta-tool — contains the winning tool_id, raw output data, overall success flag, and a list of all invocation attempts with per-attempt metrics.
- **DynamicTool**: An ephemeral LangChain `StructuredTool` constructed at runtime from a bind response. Lives only for the duration of a single ToolDiscoveryTool invocation.
- **InvocationAttempt**: A record of a single tool invocation attempt — tool_id, success, latency_ms, error_message (if any).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An agent can discover and successfully invoke a tool it was not pre-configured with, end-to-end, within 5 seconds (excluding the tool's own execution time).
- **SC-002**: When the first-choice tool fails, the system automatically tries an alternative and succeeds — verified with at least 2 fallback attempts in test.
- **SC-003**: Every tool invocation attempt (success and failure) is logged to the registry with complete metadata (agent_id, session_id, latency_ms, success, error_message).
- **SC-004**: Constructed dynamic tools conform to the LangChain `StructuredTool` interface — name, description, args_schema, and invoke method all function correctly.
- **SC-005**: The ToolDiscoveryTool itself conforms to the LangChain tool interface and can be bound to any agent in the graph without special-case code.
- **SC-006**: Research constraints from the graph state are correctly forwarded to both registry search and tool invocation payloads.
- **SC-007**: The per-tool invocation timeout fires correctly and triggers fallback rather than blocking the entire pipeline.

## Assumptions

- The Tool Registry Service (feature 001) is operational at `REGISTRY_BASE_URL` with the `GET /tools/search`, `GET /tools/{id}/bind`, and `POST /tools/usage-log` endpoints available.
- The existing `RegistryClient` (from feature 002) is reused for HTTP communication with the registry. The ToolDiscoveryTool wraps the client rather than reimplementing HTTP calls.
- LLM-based tool selection uses the same LLM instance already configured in the graph context (Gemini 2.0 Flash by default). No additional LLM configuration is needed.
- The Researcher node's existing inline search → bind → invoke logic will be refactored to delegate to the ToolDiscoveryTool as part of this feature (confirmed in-scope). All existing Researcher tests must remain green.
- Tool endpoints are HTTP-based services reachable from the agent's network. No authentication is required on tool endpoints in v1.
- The per-tool invocation timeout is separate from and subordinate to the per-graph total timeout (60s) established in feature 002.
- Dynamic tool construction happens in-memory and is ephemeral — constructed tools are not cached across graph invocations in v1.
