# Contract: GET /tools/search

## Request

**Method**: GET
**Path**: `/tools/search`

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `capability` | string | No | Filter by capability tag (exact match). |
| `limit` | int | No | Max results (default: 10, max: 50). |

When no `capability` is provided, all active tools are returned (enabling
agents to receive the full catalog for LLM-based tool selection).

### Behavior

1. If `capability` is provided: filter tools by tag, return ordered by
   `created_at` descending.
2. If no filter is provided: return all active tools ordered by
   `created_at` descending.
3. Tools with `status = 'deprecated'` are always excluded.
4. Tools with `status = 'unhealthy'` are excluded by default (discoverable
   only when explicitly queried by ID).

## Responses

### 200 OK

```json
{
  "results": [
    {
      "tool_id": "sec-filing-parser-v1",
      "name": "SEC Filing Parser",
      "description": "Parses SEC EDGAR filings and extracts structured financial data...",
      "capabilities": ["financial_data", "sec_filings", "document_parsing"],
      "version": "1.0.0",
      "status": "active",
      "avg_latency_ms": 2300.0
    },
    {
      "tool_id": "calculator-v1",
      "name": "Calculator",
      "description": "Performs mathematical calculations...",
      "capabilities": ["math", "calculation"],
      "version": "1.0.0",
      "status": "active",
      "avg_latency_ms": 50.0
    }
  ],
  "total": 2,
  "capability_filter": "financial_data"
}
```

### 200 OK (no results)

```json
{
  "results": [],
  "total": 0,
  "capability_filter": "quantum_computing"
}
```
