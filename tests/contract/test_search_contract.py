"""Contract tests for GET /tools/search (T021)."""

import pytest
from httpx import AsyncClient

TOOLS = [
    {
        "tool_id": f"search-test-{i}",
        "name": f"Search Test Tool {i}",
        "description": (
            f"A tool number {i} for testing search functionality "
            f"with different capabilities"
        ),
        "capabilities": cap,
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "endpoint": f"http://localhost:9999/tool-{i}",
        "version": "1.0.0",
    }
    for i, cap in enumerate(
        [
            ["web_search"],
            ["web_search", "general_knowledge"],
            ["financial_data"],
            ["academic_papers"],
            ["math", "calculation"],
        ]
    )
]


@pytest.fixture
async def seeded_tools(client: AsyncClient):
    for tool in TOOLS:
        resp = await client.post("/tools/register", json=tool)
        assert resp.status_code == 201
    return TOOLS


@pytest.mark.asyncio
async def test_search_by_capability(client: AsyncClient, seeded_tools):
    resp = await client.get("/tools/search", params={"capability": "web_search"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert data["capability_filter"] == "web_search"


@pytest.mark.asyncio
async def test_search_by_query(client: AsyncClient, seeded_tools):
    resp = await client.get("/tools/search", params={"query": "financial data analysis"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["results"], list)
    assert data["query"] == "financial data analysis"


@pytest.mark.asyncio
async def test_search_combined(client: AsyncClient, seeded_tools):
    resp = await client.get(
        "/tools/search",
        params={"capability": "web_search", "query": "general knowledge"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_empty_results(client: AsyncClient):
    resp = await client.get("/tools/search", params={"capability": "nonexistent_cap"})
    assert resp.status_code == 200
    assert resp.json()["results"] == []


@pytest.mark.asyncio
async def test_search_422_no_params(client: AsyncClient):
    resp = await client.get("/tools/search")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_limit_parameter(client: AsyncClient, seeded_tools):
    resp = await client.get("/tools/search", params={"capability": "web_search", "limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()["results"]) <= 1
