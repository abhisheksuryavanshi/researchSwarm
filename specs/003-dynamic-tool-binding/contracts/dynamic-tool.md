# Contract: DynamicTool Builder

**Entity**: `agents.tools.discovery.build_dynamic_tool`
**Type**: Factory function — constructs ephemeral `StructuredTool` from bind response

## Signature

```python
def build_dynamic_tool(
    bind_response: dict[str, Any],
    registry: RegistryClient,
    timeout_seconds: int = 30,
) -> StructuredTool:
```

## Responsibilities

- Accept a bind response (from `GET /tools/{id}/bind`) and construct a LangChain `StructuredTool`
- Generate a Pydantic model from the bind response's `args_schema` for input validation
- Create an async invocation function that calls the tool's HTTP endpoint via RegistryClient
- Return a fully conformant `StructuredTool` with name, description, and args_schema

## Input (bind_response dict)

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `name` | `str` | `ToolBindResponse.name` | Tool identifier, used as StructuredTool.name |
| `description` | `str` | `ToolBindResponse.description` | Used as StructuredTool.description |
| `args_schema` | `dict` | `ToolBindResponse.args_schema` | JSON Schema → Pydantic model for validation |
| `endpoint` | `str` | `ToolBindResponse.endpoint` | HTTP endpoint for invocation |
| `method` | `str` | `ToolBindResponse.method` | HTTP method (POST/GET) |

## Output

A `StructuredTool` instance with:
- `name`: from bind_response
- `description`: from bind_response
- `args_schema`: dynamically generated Pydantic model (or generic fallback)
- `coroutine`: async function that invokes `RegistryClient.invoke(endpoint, method, payload)`

## Behavioral Contract

1. MUST produce a tool whose `name` matches `bind_response["name"]`
2. MUST produce a tool whose `description` matches `bind_response["description"]`
3. MUST generate a Pydantic model from `args_schema["properties"]` when present
4. When `args_schema` is empty, missing, or has no `properties`, MUST fall back to a generic model: `GenericToolInput(query: str, constraints: dict = {}, gaps: list = [])`
5. The generated tool's `coroutine` MUST call `RegistryClient.invoke(endpoint, method, payload)`
6. The generated tool MUST be usable as a standard LangChain tool (`.ainvoke()` works)

## Schema Generation Rules

| args_schema State | Generated Model |
|-------------------|----------------|
| Has `properties` with typed fields | `create_model("DynamicArgs_<name>", field1=(type, default), ...)` |
| Has `properties` but no `required` list | All fields optional with defaults |
| Empty dict `{}` | `GenericToolInput(query: str, constraints: dict = {}, gaps: list = [])` |
| `None` or missing | `GenericToolInput(query: str, constraints: dict = {}, gaps: list = [])` |

### Type Mapping (JSON Schema → Python)

| JSON Schema type | Python type | Default |
|------------------|-------------|---------|
| `"string"` | `str` | `""` |
| `"integer"` | `int` | `0` |
| `"number"` | `float` | `0.0` |
| `"boolean"` | `bool` | `False` |
| `"array"` | `list` | `[]` |
| `"object"` | `dict` | `{}` |

## Test Expectations

1. Given a bind response with `args_schema.properties`, the built tool has a matching Pydantic args_schema
2. Given an empty `args_schema`, the built tool uses GenericToolInput
3. The built tool's name and description match the bind response
4. Invoking the built tool calls `RegistryClient.invoke()` with correct endpoint and method
5. The built tool validates input against the generated schema before invocation
6. JSON Schema types are correctly mapped to Python types
