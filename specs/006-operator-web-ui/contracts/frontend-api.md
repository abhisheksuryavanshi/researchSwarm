# API Contract: Operator Web UI → Backend

**Feature**: `006-operator-web-ui` | **Date**: 2026-04-03

This document defines the HTTP API surface the web UI consumes. All endpoints already exist in the backend. The UI is a **read-only consumer** of the tool registry and a **read-write consumer** of the session API (create session, post turns). No new endpoints are introduced.

## Common Request Headers

Every request from the UI includes these headers:

| Header | Value | When |
|--------|-------|------|
| `X-Trace-ID` | UUID v4 (generated per request) | All requests |
| `X-Session-ID` | Active `session_id` from localStorage | Session-related requests |
| `Authorization` | `Bearer <principal_id>` | Session API requests only (`/v1/sessions*`) |
| `Content-Type` | `application/json` | Requests with a body |

## 1. Session API

### 1.1 Create Session

```
POST /v1/sessions
Authorization: Bearer <principal_id>
X-Trace-ID: <uuid>
```

**Request body**: None

**Success response** (`201`):
```json
{
  "session_id": "string",
  "status": "active",
  "expires_at": "2026-05-03T00:00:00Z"
}
```

**Error responses**:
- `401` — Missing or empty Bearer token
- `503` — Conversation coordinator not configured

**UI behavior**:
- Called automatically when no `session_id` exists in localStorage
- Called when operator clicks "New Session"
- On success: store `session_id` + `expires_at` in localStorage, display session ID
- On `503`: show ErrorBanner ("Backend not ready — conversation service is starting up")

---

### 1.2 Post Turn

```
POST /v1/sessions/{session_id}/turns
Authorization: Bearer <principal_id>
X-Trace-ID: <uuid>
X-Session-ID: <session_id>
Content-Type: application/json
```

**Request body**:
```json
{
  "message": "string (min 1 char)"
}
```

**Success response** (`200`):
```json
{
  "turn_index": 0,
  "assistant_message": "string (may contain markdown)",
  "intent": "new_query | refinement | reformat | meta_question | needs_clarification",
  "intent_confidence": 0.95,
  "degraded_mode": false,
  "trace_id": "string",
  "route_mode": "string | null",
  "engine_entry": "string | null"
}
```

**Error responses**:
- `404` `{"error": "session_not_found", "message": "..."}` — Session expired or invalid
- `409` `{"error": "idempotency_mismatch", "message": "..."}` — Idempotency-Key conflict (not used in v1)
- `503` `{"error": "session_degraded", "message": "...", "degraded_mode": true}` — Storage degraded

**UI behavior**:
- Disable input + send button while request is in-flight (FR-019)
- On success: append Turn to history, render assistant_message as markdown, show metadata
- On `404`: clear stored session, show "Session expired" message with "Start New Session" button
- On `503`: show ErrorBanner with degraded mode indicator; if response includes a body, still display it

---

## 2. Tool Registry API

No `Authorization` header required. All tool endpoints are read-only from the UI's perspective.

### 2.1 Search Tools

```
GET /tools/search?capability={keyword}&limit={1-50}
X-Trace-ID: <uuid>
```

**Query parameters**:
- `capability` (optional): Filter by capability tag
- `limit` (optional, default `10`, max `50`): Max results

**Success response** (`200`):
```json
{
  "results": [
    {
      "tool_id": "string",
      "name": "string",
      "description": "string",
      "capabilities": ["string"],
      "version": "1.0.0",
      "status": "active",
      "avg_latency_ms": 150.0
    }
  ],
  "total": 5,
  "capability_filter": "web_search | null"
}
```

**UI behavior**:
- Called on ToolsPage mount (no filter, default limit)
- Called on search input change (debounced ~300ms) with `capability` parameter
- On empty `results`: show EmptyState ("No tools found")

---

### 2.2 Get Tool Detail (Bind)

```
GET /tools/{tool_id}/bind
X-Trace-ID: <uuid>
```

**Success response** (`200`):
```json
{
  "name": "string",
  "description": "string",
  "args_schema": { "...JSON Schema..." },
  "endpoint": "https://...",
  "method": "POST",
  "version": "1.0.0",
  "return_schema": { "...JSON Schema..." }
}
```

**Error responses**:
- `404` `{"detail": "..."}` — Tool not found

**UI behavior**:
- Called when operator selects a tool from the catalog
- Display schemas as formatted JSON with syntax highlighting
- On `404`: show ErrorBanner ("Tool not found — it may have been removed")

---

### 2.3 Tool Health Check

```
GET /tools/{tool_id}/health
X-Trace-ID: <uuid>
```

**Success response** (`200`):
```json
{
  "tool_id": "string",
  "status": "healthy | degraded | unhealthy | unknown",
  "latency_ms": 45.0,
  "checked_at": "2026-04-03T12:00:00Z",
  "endpoint_checked": "https://...",
  "message": "string | null",
  "error": "string | null"
}
```

**Error responses**:
- `404` `{"detail": "..."}` — Tool not found

**UI behavior**:
- Triggered by operator action (button click) in tool detail view
- Show loading spinner during health probe
- Display status badge (green/yellow/red/grey) with latency and timestamp
- On `404`: show ErrorBanner

---

### 2.4 Tool Statistics

```
GET /tools/stats?tool_id={id}&since={iso-datetime}
X-Trace-ID: <uuid>
```

**Query parameters**:
- `tool_id` (optional): Filter to a single tool
- `since` (optional): ISO-8601 datetime to filter stats from

**Success response** (`200`):
```json
{
  "stats": [
    {
      "tool_id": "string",
      "name": "string",
      "invocation_count": 100,
      "success_count": 95,
      "error_count": 5,
      "error_rate": 0.05,
      "avg_latency_ms": 200.0,
      "p50_latency_ms": 180.0,
      "p95_latency_ms": 450.0,
      "last_invoked_at": "2026-04-03T11:00:00Z",
      "status": "active"
    }
  ],
  "total_tools": 10,
  "total_invocations": 5000,
  "since": "2026-04-01T00:00:00Z | null"
}
```

**UI behavior**:
- Called on StatsPage mount (no filters)
- Re-fetched when operator applies tool or time-range filter
- Display aggregate summary (total tools, total invocations) at top
- Display per-tool metrics in a sortable table

---

## 3. Error Mapping

The API client (`lib/api/client.ts`) maps server responses to normalised `ApiError` types:

| Condition | `ApiError.type` | User-facing message |
|-----------|-----------------|---------------------|
| Network failure (fetch throws TypeError) | `network` | "Unable to reach the server. Check your connection and try again." |
| HTTP 404 with `error: "session_not_found"` | `session_not_found` | "Your session has expired or is no longer valid." |
| HTTP 503 with `error: "session_degraded"` | `session_degraded` | "The system is temporarily operating in degraded mode. Your request may still complete." |
| HTTP 5xx | `server_error` | "Something went wrong on the server. Please try again in a moment." |
| HTTP 422 | `validation_error` | "Invalid request. Please check your input." |
| Any other error | `unknown` | "An unexpected error occurred." |

## 4. CORS Contract (Backend Change)

**File**: `registry/app.py`

**Change**: Add `CORSMiddleware` with configurable origins.

**Environment variable**: `CORS_ORIGINS` (comma-separated list of allowed origins)
**Default**: `http://localhost:5173` (Vite dev server)

**Expected CORS headers on responses**:
- `Access-Control-Allow-Origin`: Matches request origin if in allowed list
- `Access-Control-Allow-Methods`: `GET, POST, PUT, DELETE, OPTIONS`
- `Access-Control-Allow-Headers`: `Authorization, Content-Type, X-Trace-ID, X-Session-ID, Idempotency-Key`
- `Access-Control-Allow-Credentials`: `true`

**Contract test**: `tests/contract/test_cors_contract.py` verifies these headers are present on preflight (`OPTIONS`) and actual requests.
