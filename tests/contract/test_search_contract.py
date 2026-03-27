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
    """Prepare multi-record tool arrays directly ensuring stable environments actively."""
    for tool in TOOLS:
        resp = await client.post("/tools/register", json=tool)
        assert resp.status_code == 201
    return TOOLS


@pytest.mark.asyncio
async def test_search_by_capability(client: AsyncClient, seeded_tools):
    """Target capability subsets explicitly analyzing isolated results efficiently."""
    resp = await client.get("/tools/search", params={"capability": "web_search"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert data["capability_filter"] == "web_search"


@pytest.mark.asyncio
async def test_search_all_tools(client: AsyncClient, seeded_tools):
    """Guarantee global fetching effectively produces unclipped full scale indexes automatically."""
    resp = await client.get("/tools/search")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["results"], list)
    assert data["total"] >= len(TOOLS)


@pytest.mark.asyncio
async def test_search_empty_results(client: AsyncClient):
    """Guarantee isolated terms uniquely extract correctly avoiding unrelated noise safely."""
    resp = await client.get("/tools/search", params={"capability": "nonexistent_cap"})
    assert resp.status_code == 200
    assert resp.json()["results"] == []


@pytest.mark.asyncio
async def test_search_limit_parameter(client: AsyncClient, seeded_tools):
    """Bind boundary caps assertively blocking expansive oversized queries effectively."""
    resp = await client.get("/tools/search", params={"capability": "web_search", "limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()["results"]) <= 1
