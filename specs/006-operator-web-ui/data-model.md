# Data Model: Operator Web UI

**Feature**: `006-operator-web-ui` | **Date**: 2026-04-03

All data in this feature lives in the **browser** (localStorage + React state). There are no new server-side tables or storage. The models below are TypeScript interfaces that mirror the server's Pydantic response schemas.

## Client-Side Persisted State (localStorage)

### StoredSession

Persisted in localStorage under the key `researchswarm:session`.

| Field | Type | Description |
|-------|------|-------------|
| `sessionId` | `string` | Active session identifier from `POST /v1/sessions` response |
| `principalId` | `string` | UUID v4 generated on first visit; used as Bearer token |
| `createdAt` | `string` (ISO-8601) | When the session was created |
| `expiresAt` | `string` (ISO-8601) | Server-provided expiry timestamp |

**Lifecycle**:
- Created when no stored session exists (first visit or after "New Session")
- Updated when "New Session" replaces the current session
- Cleared if the server returns 404 on a turn (expired/invalid)
- Falls back to in-memory `Map` when localStorage is unavailable

## Client-Side In-Memory State (React)

### Turn

Accumulated in an array within the chat page component. Lost on page refresh or "New Session".

| Field | Type | Description |
|-------|------|-------------|
| `turnIndex` | `number` | Ordinal from server response |
| `userMessage` | `string` | The operator's input text |
| `assistantMessage` | `string` | Markdown-formatted assistant response |
| `intent` | `string` | Classified intent (`new_query`, `refinement`, `reformat`, `meta_question`, `needs_clarification`) |
| `intentConfidence` | `number` | `0.0`–`1.0` confidence score |
| `degradedMode` | `boolean` | Whether the server operated in degraded mode |
| `traceId` | `string` | Server-generated trace identifier |
| `routeMode` | `string \| null` | Optional routing mode label |
| `engineEntry` | `string \| null` | Optional engine entry point label |
| `timestamp` | `string` (ISO-8601) | Client-side timestamp of when the turn was sent |

**Lifecycle**:
- Appended after each successful `POST /v1/sessions/{id}/turns` response
- User message added optimistically; assistant fields populated on response
- Entire array cleared on "New Session"

### ToolSearchResult

Fetched from `GET /tools/search` and held in tool catalog page state.

| Field | Type | Description |
|-------|------|-------------|
| `toolId` | `string` | Unique tool identifier |
| `name` | `string` | Human-readable tool name |
| `description` | `string` | Tool description |
| `capabilities` | `string[]` | Capability tags |
| `version` | `string` | Semver version |
| `status` | `string` | `active`, `degraded`, `deprecated` |
| `avgLatencyMs` | `number` | Average invocation latency |

### ToolDetail

Fetched from `GET /tools/{id}/bind` and displayed in the tool detail view.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Tool name (equals `tool_id` in current impl) |
| `description` | `string` | Tool description |
| `argsSchema` | `Record<string, unknown>` | JSON Schema for tool input |
| `endpoint` | `string` | Tool invocation URL |
| `method` | `string` | HTTP method |
| `version` | `string` | Semver version |
| `returnSchema` | `Record<string, unknown>` | JSON Schema for tool output |

### ToolHealthResult

Fetched from `GET /tools/{id}/health` on demand.

| Field | Type | Description |
|-------|------|-------------|
| `toolId` | `string` | Tool identifier |
| `status` | `string` | `healthy`, `degraded`, `unhealthy`, `unknown` |
| `latencyMs` | `number \| null` | Health check latency |
| `checkedAt` | `string` (ISO-8601) | When the check ran |
| `endpointChecked` | `string \| null` | Which URL was probed |
| `message` | `string \| null` | Status message |
| `error` | `string \| null` | Error details if unhealthy |

### ToolStatsItem

Fetched from `GET /tools/stats`.

| Field | Type | Description |
|-------|------|-------------|
| `toolId` | `string` | Tool identifier |
| `name` | `string` | Tool name |
| `invocationCount` | `number` | Total invocations |
| `successCount` | `number` | Successful invocations |
| `errorCount` | `number` | Failed invocations |
| `errorRate` | `number` | Error ratio (0.0–1.0) |
| `avgLatencyMs` | `number` | Average latency |
| `p50LatencyMs` | `number` | Median latency |
| `p95LatencyMs` | `number` | 95th percentile latency |
| `lastInvokedAt` | `string \| null` (ISO-8601) | Last invocation timestamp |
| `status` | `string` | Tool status |

### ToolStatsResponse

Wrapper for the stats endpoint response.

| Field | Type | Description |
|-------|------|-------------|
| `stats` | `ToolStatsItem[]` | Per-tool stats |
| `totalTools` | `number` | Total registered tools |
| `totalInvocations` | `number` | Total invocations across all tools |
| `since` | `string \| null` | Filter start time (if applied) |

## State Relationships

```text
localStorage
  └── StoredSession (1)
        ├── principalId → used as Bearer token on all session requests
        └── sessionId → used in POST /v1/sessions/{sessionId}/turns

React State (per page)
  ├── ChatPage
  │     └── turns: Turn[]  (accumulated, cleared on New Session)
  ├── ToolsPage
  │     ├── tools: ToolSearchResult[]  (fetched on mount, re-fetched on search)
  │     └── selectedTool: ToolDetail | null  (fetched on selection)
  └── StatsPage
        └── stats: ToolStatsResponse  (fetched on mount, re-fetched on filter)
```

## Error State Types

### ApiError

Normalised error representation used across all API calls.

| Field | Type | Description |
|-------|------|-------------|
| `type` | `'network' \| 'session_not_found' \| 'session_degraded' \| 'server_error' \| 'validation_error' \| 'unknown'` | Categorised error type |
| `message` | `string` | Human-readable message for display |
| `status` | `number \| null` | HTTP status code (null for network errors) |
| `detail` | `string \| null` | Raw server error detail (for logging, not display) |
