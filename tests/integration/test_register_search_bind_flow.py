"""Integration test: register -> search -> bind flow (T033)."""

import pytest
from httpx import AsyncClient

FLOW_TOOLS = [
    {
        "tool_id": "flow-financial-v1",
        "name": "Financial Analyzer",
        "description": "Analyzes financial statements and key metrics from company reports",
        "capabilities": ["financial_data", "analysis"],
        "input_schema": {"type": "object", "properties": {"ticker": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"metrics": {"type": "object"}}},
        "endpoint": "http://localhost:9999/financial",
        "version": "1.0.0",
    },
    {
        "tool_id": "flow-search-v1",
        "name": "Web Searcher",
        "description": "Searches the web for information using multiple search engines and APIs",
        "capabilities": ["web_search", "general_knowledge"],
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"results": {"type": "array"}}},
        "endpoint": "http://localhost:9999/search",
        "version": "1.0.0",
    },
    {
        "tool_id": "flow-math-v1",
        "name": "Math Calculator",
        "description": "Math and statistical calculations on numeric data",
        "capabilities": ["math", "calculation"],
        "input_schema": {"type": "object", "properties": {"expression": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"result": {"type": "number"}}},
        "endpoint": "http://localhost:9999/math",
        "version": "1.0.0",
    },
]


@pytest.mark.asyncio
async def test_register_search_bind_flow(client: AsyncClient):
    """Integrate basic agent workflows natively connecting endpoint loops together continuously."""
    for tool in FLOW_TOOLS:
        resp = await client.post("/tools/register", json=tool)
        assert resp.status_code == 201, f"Failed to register {tool['tool_id']}: {resp.text}"

    search_resp = await client.get("/tools/search", params={"capability": "financial_data"})
    assert search_resp.status_code == 200
    results = search_resp.json()["results"]
    assert any(r["tool_id"] == "flow-financial-v1" for r in results)

    all_resp = await client.get("/tools/search")
    assert all_resp.status_code == 200
    assert len(all_resp.json()["results"]) >= len(FLOW_TOOLS)

    bind_resp = await client.get("/tools/flow-financial-v1/bind")
    assert bind_resp.status_code == 200
    bind_data = bind_resp.json()
    assert bind_data["name"] == "flow-financial-v1"
    assert bind_data["args_schema"] == FLOW_TOOLS[0]["input_schema"]
    assert bind_data["return_schema"] == FLOW_TOOLS[0]["output_schema"]
    assert bind_data["endpoint"] == FLOW_TOOLS[0]["endpoint"]
