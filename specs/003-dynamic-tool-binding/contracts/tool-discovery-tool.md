# Contract: ToolDiscoveryTool

**Entity**: `agents.tools.discovery.ToolDiscoveryTool`
**Type**: LangChain `BaseTool` subclass (async)

## Signature

```python
class ToolDiscoveryTool(BaseTool):
    name: str = "tool_discovery"
    description: str = "Search the tool registry for a capability, select the best tool, and invoke it"
    args_schema: type[BaseModel] = ToolDiscoveryInput

    async def _arun(self, **kwargs) -> str:
        """Returns JSON-serialized ToolDiscoveryResult."""
```

## Responsibilities

- Search the Tool Registry for tools matching an explicit capability tag
- Use the LLM to rank and select the best-matching tool(s) from search results
- Construct an ephemeral LangChain `StructuredTool` from the bind response
- Invoke the constructed tool with a schema-aware payload
- On failure, attempt the next-ranked alternative (up to 3 total attempts)
- Log every invocation attempt (success or failure) to the registry
- Return a structured result with the tool output, attempt history, and success status

## Input Schema (ToolDiscoveryInput)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `capability` | `str` | Yes | Registry capability tag (e.g., `"sec_filings"`) |
| `query` | `str` | Yes | Research query for payload mapping and LLM context |
| `constraints` | `dict` | No | Research constraints forwarded to search and invocation |
| `gaps` | `list[str]` | No | Gaps from Critic for refinement queries |
| `agent_id` | `str` | No | Calling agent ID for usage logs |
| `session_id` | `str` | No | Session ID for usage log correlation |

## Output Schema (ToolDiscoveryResult — JSON serialized)

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | `True` if any tool invocation succeeded |
| `tool_id` | `str \| None` | tool_id of the successful tool |
| `data` | `dict` | Raw output from the successful tool |
| `source` | `dict` | `{"url": str, "title": str, "tool_id": str}` |
| `attempts` | `list[InvocationAttempt]` | All attempts with per-attempt metrics |
| `error` | `str \| None` | Summary error if all attempts failed |

## Behavioral Contract

1. MUST search the registry via `RegistryClient.search(capability=...)` — never hardcode tool lists
2. MUST use `with_structured_output(ToolSelectionResponse)` to rank tools when multiple candidates exist
3. When LLM selection fails, MUST fall back to lowest `avg_latency_ms` from search results
4. MUST call `RegistryClient.bind(tool_id)` for each tool before invocation
5. MUST construct payload via `build_tool_payload()` using the tool's `args_schema`
6. MUST enforce per-tool timeout (`asyncio.wait_for(..., timeout=config.tool_invocation_timeout_seconds)`)
7. On tool failure, MUST attempt next-ranked alternative up to `config.max_tool_fallback_attempts` total
8. MUST log every attempt to registry via `RegistryClient.log_usage()` with agent_id, session_id, latency_ms, success, error_message
9. MUST return a `ToolDiscoveryResult` serialized as JSON string
10. MUST forward `constraints` to both the registry search and the tool invocation payload
11. MUST NOT make LLM calls for capability inference — capability is provided by the caller

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Registry unreachable | Return `ToolDiscoveryResult(success=False, error="registry search failed: ...")` |
| No tools match capability | Return `ToolDiscoveryResult(success=False, error="no tools found for capability: X")` |
| LLM selection fails | Fall back to lowest-latency tool from search results |
| Tool invocation fails | Log failure, attempt next fallback (if within cap) |
| All attempts exhausted | Return `ToolDiscoveryResult(success=False, attempts=[...], error="all N attempts failed")` |
| Per-tool timeout | Treat as failure, log with error, proceed to fallback |

## Test Expectations

1. Given a mock registry with 3 tools, the ToolDiscoveryTool searches, selects, binds, and invokes at least 1
2. `ToolDiscoveryResult.success` is `True` when any tool invocation succeeds
3. `ToolDiscoveryResult.attempts` contains exactly the number of attempts made (1-3)
4. On primary tool failure, fallback to alternative is attempted (verified via mock call counts)
5. All attempts are logged to registry (verified via `log_usage` mock assertions)
6. Per-tool timeout triggers fallback (not graph-level abort)
7. Empty search results → `success=False` with descriptive error
8. Constraints are forwarded to both search and invocation payload
