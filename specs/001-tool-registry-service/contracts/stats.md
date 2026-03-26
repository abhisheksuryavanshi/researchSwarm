# Contract: GET /tools/stats

## Request

**Method**: GET
**Path**: `/tools/stats`

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tool_id` | string | No | Filter stats for a specific tool. |
| `since` | string (ISO datetime) | No | Only include invocations after this timestamp. |

## Responses

### 200 OK

```json
{
  "stats": [
    {
      "tool_id": "sec-filing-parser-v1",
      "name": "SEC Filing Parser",
      "invocation_count": 47,
      "success_count": 43,
      "error_count": 4,
      "error_rate": 0.085,
      "avg_latency_ms": 2312.5,
      "p50_latency_ms": 2100.0,
      "p95_latency_ms": 3800.0,
      "last_invoked_at": "2026-03-26T09:45:00Z",
      "status": "active"
    },
    {
      "tool_id": "serp-web-search-v1",
      "name": "SerpAPI Web Search",
      "invocation_count": 156,
      "success_count": 152,
      "error_count": 4,
      "error_rate": 0.026,
      "avg_latency_ms": 890.3,
      "p50_latency_ms": 750.0,
      "p95_latency_ms": 1500.0,
      "last_invoked_at": "2026-03-26T09:58:00Z",
      "status": "active"
    }
  ],
  "total_tools": 7,
  "total_invocations": 412,
  "since": null
}
```

### 200 OK (no invocations)

```json
{
  "stats": [
    {
      "tool_id": "github-search-v1",
      "name": "GitHub Repository Search",
      "invocation_count": 0,
      "success_count": 0,
      "error_count": 0,
      "error_rate": 0.0,
      "avg_latency_ms": 0.0,
      "p50_latency_ms": 0.0,
      "p95_latency_ms": 0.0,
      "last_invoked_at": null,
      "status": "active"
    }
  ],
  "total_tools": 7,
  "total_invocations": 0,
  "since": null
}
```

### Stats Fields

| Field | Type | Description |
|-------|------|-------------|
| `tool_id` | string | Tool identifier. |
| `name` | string | Human-readable tool name. |
| `invocation_count` | int | Total invocations (success + error). |
| `success_count` | int | Successful invocations. |
| `error_count` | int | Failed invocations. |
| `error_rate` | float | `error_count / invocation_count` (0.0 if no invocations). |
| `avg_latency_ms` | float | Mean latency across all invocations. |
| `p50_latency_ms` | float | Median latency. |
| `p95_latency_ms` | float | 95th percentile latency. |
| `last_invoked_at` | string (ISO datetime) or null | Timestamp of most recent invocation. |
| `status` | string | Current tool status (`active`, `degraded`, `unhealthy`, `deprecated`). |
