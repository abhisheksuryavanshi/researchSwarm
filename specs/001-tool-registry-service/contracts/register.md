# Contract: POST /tools/register

## Request

**Method**: POST
**Path**: `/tools/register`
**Content-Type**: `application/json`

### Request Body

```json
{
  "tool_id": "sec-filing-parser-v1",
  "name": "SEC Filing Parser",
  "description": "Parses SEC EDGAR filings and extracts structured financial data including income statements, balance sheets, and cash flow statements.",
  "capabilities": ["financial_data", "sec_filings", "document_parsing"],
  "input_schema": {
    "type": "object",
    "properties": {
      "ticker": { "type": "string", "description": "Stock ticker symbol" },
      "filing_type": { "type": "string", "enum": ["10-K", "10-Q", "8-K"] }
    },
    "required": ["ticker"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "sections": { "type": "array", "items": { "type": "object" } },
      "financials": { "type": "object" }
    }
  },
  "endpoint": "http://tools-service:8001/sec-parser",
  "method": "POST",
  "version": "1.0.0",
  "health_check": "/health",
  "cost_per_call": 0.0
}
```

### Required Fields

| Field | Type | Validation |
|-------|------|------------|
| `tool_id` | string | `^[a-z0-9][a-z0-9-]*[a-z0-9]$`, 3-100 chars |
| `name` | string | 1-255 chars, non-empty |
| `description` | string | 10+ chars |
| `capabilities` | string[] | Each tag: `^[a-z][a-z0-9_]*$` |
| `input_schema` | object | Valid JSON Schema |
| `output_schema` | object | Valid JSON Schema |
| `endpoint` | string | Valid HTTP/HTTPS URL |
| `version` | string | Semver: `^\d+\.\d+\.\d+$` |

### Optional Fields

| Field | Type | Default |
|-------|------|---------|
| `method` | string | `"POST"` |
| `health_check` | string | `null` |
| `cost_per_call` | float | `0.0` |

## Responses

### 201 Created

```json
{
  "tool_id": "sec-filing-parser-v1",
  "name": "SEC Filing Parser",
  "description": "Parses SEC EDGAR filings and extracts structured financial data...",
  "capabilities": ["financial_data", "sec_filings", "document_parsing"],
  "input_schema": { ... },
  "output_schema": { ... },
  "endpoint": "http://tools-service:8001/sec-parser",
  "method": "POST",
  "version": "1.0.0",
  "health_check": "/health",
  "status": "active",
  "avg_latency_ms": 0.0,
  "cost_per_call": 0.0,
  "created_at": "2026-03-26T10:00:00Z",
  "updated_at": "2026-03-26T10:00:00Z"
}
```

### 409 Conflict

```json
{
  "detail": "Tool with id 'sec-filing-parser-v1' already exists."
}
```

### 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "tool_id"],
      "msg": "String should match pattern '^[a-z0-9][a-z0-9-]*[a-z0-9]$'",
      "type": "string_pattern_mismatch"
    }
  ]
}
```
