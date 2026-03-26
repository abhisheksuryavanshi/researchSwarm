# Contract: GET /tools/{tool_id}/health

## Request

**Method**: GET
**Path**: `/tools/{tool_id}/health`

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool_id` | string | The unique tool identifier. |

### Behavior

1. Look up the tool's `health_check` field.
2. If `health_check` is null, return `status: "unknown"` with a message
   indicating no health check is configured.
3. Construct the full health URL: if `health_check` is a relative path,
   combine with `endpoint` base URL. If absolute, use directly.
4. Send a GET request with a 500ms timeout.
5. Classify result:
   - Response received in < 500ms with 2xx status → `healthy`
   - Response received but > 500ms → `degraded`
   - Connection refused or timeout → `unhealthy`
6. Update the tool's `status` field in the database to match.

## Responses

### 200 OK (healthy)

```json
{
  "tool_id": "sec-filing-parser-v1",
  "status": "healthy",
  "latency_ms": 45.2,
  "checked_at": "2026-03-26T10:00:00Z",
  "endpoint_checked": "http://tools-service:8001/health"
}
```

### 200 OK (degraded)

```json
{
  "tool_id": "sec-filing-parser-v1",
  "status": "degraded",
  "latency_ms": 612.8,
  "checked_at": "2026-03-26T10:00:00Z",
  "endpoint_checked": "http://tools-service:8001/health",
  "message": "Health check responded but exceeded 500ms budget."
}
```

### 200 OK (unhealthy)

```json
{
  "tool_id": "sec-filing-parser-v1",
  "status": "unhealthy",
  "latency_ms": null,
  "checked_at": "2026-03-26T10:00:00Z",
  "endpoint_checked": "http://tools-service:8001/health",
  "error": "Connection refused"
}
```

### 200 OK (unknown — no health check configured)

```json
{
  "tool_id": "calculator-v1",
  "status": "unknown",
  "latency_ms": null,
  "checked_at": "2026-03-26T10:00:00Z",
  "endpoint_checked": null,
  "message": "No health check endpoint configured for this tool."
}
```

### 404 Not Found

```json
{
  "detail": "Tool 'nonexistent-tool' not found."
}
```
