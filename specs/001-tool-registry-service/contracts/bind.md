# Contract: GET /tools/{tool_id}/bind

## Request

**Method**: GET
**Path**: `/tools/{tool_id}/bind`

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool_id` | string | The unique tool identifier. |

## Responses

### 200 OK

Returns a LangChain-compatible tool definition that an agent can use to
construct a `StructuredTool` at runtime.

```json
{
  "name": "sec-filing-parser-v1",
  "description": "Parses SEC EDGAR filings and extracts structured financial data including income statements, balance sheets, and cash flow statements.",
  "args_schema": {
    "type": "object",
    "properties": {
      "ticker": {
        "type": "string",
        "description": "Stock ticker symbol"
      },
      "filing_type": {
        "type": "string",
        "enum": ["10-K", "10-Q", "8-K"],
        "description": "Type of SEC filing"
      }
    },
    "required": ["ticker"]
  },
  "endpoint": "http://tools-service:8001/sec-parser",
  "method": "POST",
  "version": "1.0.0",
  "return_schema": {
    "type": "object",
    "properties": {
      "sections": { "type": "array", "items": { "type": "object" } },
      "financials": { "type": "object" }
    }
  }
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Tool identifier — maps to `StructuredTool.name`. |
| `description` | string | Tool description — maps to `StructuredTool.description`. |
| `args_schema` | object | JSON Schema for input — maps to `StructuredTool.args_schema`. |
| `endpoint` | string | HTTP URL to invoke the tool. |
| `method` | string | HTTP method (`GET` or `POST`). |
| `version` | string | Tool version. |
| `return_schema` | object | JSON Schema for the tool's return value. |

### 404 Not Found

```json
{
  "detail": "Tool 'nonexistent-tool' not found."
}
```
