# Feature Specification: Operator Web UI

**Feature Branch**: `006-operator-web-ui`  
**Created**: 2026-04-03  
**Status**: Clarified  
**Input**: User description: "Add an operator-facing web UI for researchSwarm: thin client over existing HTTP APIs only. No authentication—work is keyed by session_id. If the client does not provide a session_id, create one (POST /v1/sessions or equivalent), persist it in the browser (e.g. localStorage), and reuse it for turns. Registry remains source of truth for tools; no tool business logic in the browser."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Conversational Session (Priority: P1)

An operator opens the web UI and starts a conversation with the research assistant. If no session exists in the browser, the system automatically creates one and displays its identifier. The operator types a question or research query; the assistant's reply appears in a chat thread showing the response text, detected intent, confidence, and trace identifier. The operator can continue the conversation across multiple turns, and all prior turns remain visible. The operator can also start a fresh session at any time.

**Why this priority**: The chat interface is the primary interaction surface—without it the UI has no core purpose. Every other feature is secondary to the ability to converse with the research assistant.

**Independent Test**: Can be fully tested by opening the UI, verifying a session is created, sending a message, and confirming the response renders with all expected metadata (assistant text, intent, degraded_mode flag, trace_id). Delivers standalone value as a usable research assistant interface.

**Acceptance Scenarios**:

1. **Given** the operator opens the UI for the first time (no session stored), **When** the page loads, **Then** a new session is created via the API, the session identifier is displayed, and it is persisted in the browser for reuse.
2. **Given** an active session exists, **When** the operator types a message and submits it, **Then** the message appears in the chat thread and the assistant's response is rendered as markdown with: assistant text, intent label, intent confidence, degraded_mode flag, trace_id, and (when present) route_mode and engine_entry.
3. **Given** an active session with prior turns, **When** the operator sends another message, **Then** all previous turns remain visible above the new exchange (client-side accumulation).
4. **Given** an active session, **When** the operator clicks "New Session", **Then** a new session is created, the chat history is cleared, the new session identifier is displayed, and the browser-stored identifier is updated.
5. **Given** the operator returns to the UI after closing the browser, **When** the page loads, **Then** the previously stored session identifier is loaded and the operator can continue sending turns (turn history may be empty since it is accumulated client-side; the operator can still send new messages).

---

### User Story 2 — Tool Catalog Browsing (Priority: P2)

An operator navigates to the tool catalog to see which tools are registered in the system. They can browse the full list, search by capability keyword, and view detailed information about any individual tool.

**Why this priority**: Understanding available tools is essential for operators to know what the system can do, but is secondary to the core chat functionality.

**Independent Test**: Can be tested by navigating to the tool catalog view, verifying tools are listed, searching by a capability, and clicking a tool to see its full details (description, schemas, endpoint, version). Delivers value as a standalone tool directory.

**Acceptance Scenarios**:

1. **Given** the operator navigates to the tool catalog, **When** the page loads, **Then** a list of registered tools is displayed showing each tool's name, description, capabilities, version, and status.
2. **Given** the tool catalog is displayed, **When** the operator enters a capability keyword in the search field, **Then** the list filters to show only tools matching that capability.
3. **Given** the tool catalog is displayed, **When** the operator selects a tool, **Then** a detail view shows the tool's full information including input schema, output schema, endpoint, method, version, and health-check URL.
4. **Given** no tools match the search filter, **When** results are empty, **Then** an empty-state message is displayed guiding the operator to clear the filter or try different keywords.

---

### User Story 3 — Tool Statistics & Health Monitoring (Priority: P3)

An operator views aggregated usage statistics for tools and can check the real-time health of any individual tool. This helps operators understand system utilisation and diagnose issues.

**Why this priority**: Operational insight is valuable but is a monitoring supplement to the primary chat and catalog features.

**Independent Test**: Can be tested by navigating to the stats view, confirming aggregate metrics render, and triggering a health check on a specific tool. Delivers value as a standalone operational dashboard.

**Acceptance Scenarios**:

1. **Given** the operator navigates to the tool statistics view, **When** the page loads, **Then** aggregated statistics are displayed including total tools, total invocations, and per-tool metrics (invocation count, success/error counts, error rate, average/p50/p95 latency, last invoked timestamp).
2. **Given** the operator is viewing a tool's detail, **When** they trigger a health check, **Then** the system probes the tool's health endpoint and displays the result (healthy/degraded/unhealthy/unknown) with latency and any error message.
3. **Given** the stats view is displayed, **When** the operator filters by a specific tool or time range, **Then** statistics update to reflect only the filtered scope.

---

### User Story 4 — Error Resilience & Session Recovery (Priority: P4)

The operator encounters a situation where the backend API is unreachable or the stored session identifier is no longer valid. The UI handles these gracefully, informing the operator and offering recovery options.

**Why this priority**: Robustness is essential for operator trust but is a cross-cutting concern that supports the primary flows above.

**Independent Test**: Can be tested by simulating API unavailability (e.g., stopping the server) and verifying the UI shows a friendly error, and by using a fabricated session_id to confirm the UI detects it as invalid and offers to create a new session.

**Acceptance Scenarios**:

1. **Given** the backend API is unreachable, **When** any request fails due to a network error, **Then** a user-friendly error banner is displayed (not a raw technical error) with a suggestion to retry or check connectivity.
2. **Given** the operator has a stored session_id that the server no longer recognises, **When** a turn request returns a "session not found" error, **Then** the UI displays a message explaining the session has expired or is invalid and offers a prominent "Start New Session" action.
3. **Given** the server returns a degraded-mode response, **When** the operator views the turn result, **Then** a visible indicator shows that the system operated in degraded mode for that turn.
4. **Given** any API request results in a server error (5xx), **When** the error occurs, **Then** the UI displays a generic friendly error message and does not crash or show a blank screen.

---

### Edge Cases

- What happens when the operator submits an empty or whitespace-only message? → The send button is disabled; submission is prevented client-side.
- What happens when a turn request is in-flight and the operator tries to send another? → The input is disabled during the pending request to prevent duplicate submissions.
- What happens when localStorage is unavailable (private browsing in some browsers)? → The UI falls back to in-memory session storage for the current tab and informs the operator that session persistence across visits is unavailable.
- What happens when the tool catalog returns zero tools? → An empty-state screen is shown indicating no tools are currently registered.
- What happens when a health check times out? → The tool's health status is shown as "unknown" with a message indicating the check timed out.
- What happens when a stored session has expired (server returns 404 on a turn)? → Same recovery flow as a stale session: the UI informs the operator and offers "Start New Session".

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST automatically create a new session via the sessions API when no valid session identifier exists in the browser.
- **FR-002**: System MUST persist the active session identifier and its associated principal identifier in browser local storage and reuse them for subsequent visits.
- **FR-003**: System MUST allow the operator to send a text message and receive the assistant's response within a chat interface, rendering assistant messages as markdown (headings, lists, code blocks, links, inline formatting).
- **FR-004**: System MUST display the following metadata for each assistant turn: assistant text (markdown-rendered), intent, intent confidence, degraded_mode flag, trace_id, and—when present—route_mode and engine_entry.
- **FR-005**: System MUST accumulate and display all turns from the current browser session in chronological order (client-side history).
- **FR-006**: System MUST provide a "New Session" action that creates a fresh session, clears chat history, and updates the stored session identifier.
- **FR-007**: System MUST generate and send an `X-Trace-ID` header (UUID) with every API request for observability correlation.
- **FR-008**: System MUST send an `X-Session-ID` header containing the active session identifier on all session-related requests.
- **FR-009**: System MUST display a searchable list of registered tools retrieved from the tool search API, supporting filtering by capability keyword.
- **FR-010**: System MUST display a detail view for any selected tool showing its full metadata: description, capabilities, input/output schemas, endpoint, method, version, and health-check URL.
- **FR-011**: System MUST display aggregated tool usage statistics including per-tool invocation counts, success/error rates, latency percentiles, and last-invoked timestamps.
- **FR-012**: System MUST allow the operator to trigger a real-time health check for any individual tool and display the result.
- **FR-013**: System MUST display a friendly, human-readable error message when any API request fails due to network errors, server errors, or unexpected responses.
- **FR-014**: System MUST detect an invalid or expired session (404 from the turns API) and offer the operator the option to create a new session.
- **FR-015**: System MUST render in dark mode by default.
- **FR-016**: System MUST use semantic HTML elements, provide visible focus indicators, and support keyboard navigation for the chat input, message submission, and all interactive lists and buttons.
- **FR-017**: System MUST display appropriate loading/skeleton states while data is being fetched, and empty-state messages when no data is available.
- **FR-018**: System MUST prevent submission of empty or whitespace-only messages.
- **FR-019**: System MUST disable the chat input while a turn request is in-flight to prevent duplicate submissions.
- **FR-020**: System MUST be a read-only consumer of the tool registry; no tool registration, update, or deletion functionality is exposed in the UI.
- **FR-021**: The backend API MUST accept cross-origin requests from the web UI's origin so that browser-based fetch calls succeed without proxy workarounds.
- **FR-022**: System MUST maintain only one active session at a time; the "New Session" action replaces the current session. Past sessions are not listed or recoverable from the UI.

### Key Entities

- **Session (browser-side)**: Represents an active conversation context. Attributes: session identifier, associated principal identifier, creation timestamp. Stored in browser local storage for cross-visit persistence.
- **Turn**: A single exchange in a conversation. Attributes: turn index, operator message, assistant response text (markdown), intent label, intent confidence, degraded-mode flag, trace identifier, optional route mode, optional engine entry. Accumulated client-side in chronological order.
- **Tool**: A registered capability in the research system. Attributes: tool identifier, name, description, capabilities list, input/output schemas, endpoint, method, version, status, health-check URL.
- **Tool Statistics**: Aggregated usage metrics for a tool. Attributes: invocation count, success/error counts, error rate, average/p50/p95 latency, last invoked timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can create a session and complete a round-trip conversation (send message → receive response) within 10 seconds of opening the UI for the first time.
- **SC-002**: The session identifier persists across browser restarts; returning operators resume on the same session without manual re-entry in 100% of supported browsers.
- **SC-003**: All turn responses display the full metadata set (assistant text, intent, confidence, degraded_mode, trace_id) with no missing fields visible to the operator.
- **SC-004**: The tool catalog loads and displays results within 3 seconds on a standard connection, with search filtering updating results within 1 second of input.
- **SC-005**: When the backend API is unreachable, 100% of error states produce a human-readable message (no raw error codes, stack traces, or blank screens).
- **SC-006**: An operator with a stale session identifier is presented with a recovery option (new session) within 2 seconds of the failed request, with no manual intervention required to reach a working state.
- **SC-007**: All interactive elements (buttons, inputs, links, list items) are reachable and operable via keyboard-only navigation.
- **SC-008**: The UI renders correctly in dark mode by default with consistent visual styling across all views (chat, catalog, stats).

## Assumptions

- The existing backend API server is running and accessible from the operator's browser. Adding CORS middleware to the backend is in scope for this feature (FR-021).
- The session API's Bearer token is a simple principal identifier (not a JWT or OAuth token); the UI will generate a stable opaque identifier per browser and use it as the Bearer value, effectively treating it as a device key rather than an authentication credential.
- Turn history is accumulated client-side only; there is no server-side API to retrieve past turns for a session. If the operator clears browser storage, previous turn history is lost.
- Tool registration, update, and deletion are out of scope for this UI; operators manage tools through other channels (API directly, CLI, or a future admin UI).
- The UI targets modern evergreen browsers (Chrome, Firefox, Safari, Edge — latest two versions); Internet Explorer is not supported.
- Mobile-optimised layouts are not required for v1; the UI is designed for desktop/laptop use by operators.
- The backend does not currently serve the frontend assets; the UI will be served separately (e.g., a dev server during development or a static file server in production). Build and deployment configuration is an implementation concern.
- The Idempotency-Key header on turn requests is optional and will not be implemented in v1 unless trivial.
- Only one session is active at a time; there is no multi-session list or session-switching UI in v1. Past sessions are effectively abandoned when a new session is created.
- Assistant messages may contain markdown formatting; the UI renders them as rich text.
