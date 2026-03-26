# Contract: GET /tools/search

## Request

**Method**: GET
**Path**: `/tools/search`

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `capability` | string | No | Filter by capability tag (exact match). |
| `query` | string | No | Natural language query for semantic search. |
| `limit` | int | No | Max results (default: 10, max: 50). |
| `min_score` | float | No | Minimum similarity score 0.0-1.0 (default: 0.3). |

At least one of `capability` or `query` MUST be provided.

### Behavior

1. If only `capability` is provided: filter tools by tag, return ordered by
   `created_at` descending.
2. If only `query` is provided: embed the query, compute cosine similarity
   against all active tool embeddings, return ranked by similarity score.
3. If both are provided: filter by capability tag first, then rank the
   filtered subset by semantic similarity to the query.
4. Tools with `status = 'deprecated'` are always excluded.
5. Tools with `status = 'unhealthy'` are excluded by default (discoverable
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
      "score": 0.89,
      "avg_latency_ms": 2300.0
    },
    {
      "tool_id": "calculator-v1",
      "name": "Calculator",
      "description": "Performs mathematical calculations...",
      "capabilities": ["math", "calculation"],
      "version": "1.0.0",
      "status": "active",
      "score": 0.42,
      "avg_latency_ms": 50.0
    }
  ],
  "total": 2,
  "query": "parse SEC filings",
  "capability_filter": null
}
```

### 200 OK (no results)

```json
{
  "results": [],
  "total": 0,
  "query": "quantum computing simulator",
  "capability_filter": null
}
```

### 422 Validation Error

Returned when neither `capability` nor `query` is provided.

```json
{
  "detail": "At least one of 'capability' or 'query' must be provided."
}
```
