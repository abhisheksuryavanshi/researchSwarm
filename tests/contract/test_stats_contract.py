"""Contract tests for GET /tools/stats (T031)."""

import pytest
from httpx import AsyncClient

STATS_TOOL = {
    "tool_id": "stats-test-v1",
    "name": "Stats Test Tool",
    "description": "A tool for testing usage statistics aggregation in contract tests",
    "capabilities": ["testing"],
    "input_schema": {"type": "object"},
    "output_schema": {"type": "object"},
    "endpoint": "http://localhost:9999/stats-test",
    "version": "1.0.0",
}


@pytest.fixture
async def stats_tool(client: AsyncClient):
    """Establish fresh verifiable tool instance strictly for aggregating isolated analytical tests."""
    resp = await client.post("/tools/register", json=STATS_TOOL)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_stats_zeroed_metrics(client: AsyncClient, stats_tool):
    """Assert completely fresh applications report exactly zeroed statistics across metrics dimensions universally."""
    resp = await client.get("/tools/stats", params={"tool_id": stats_tool["tool_id"]})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["stats"]) == 1
    s = data["stats"][0]
    assert s["invocation_count"] == 0
    assert s["success_count"] == 0
    assert s["error_count"] == 0
    assert s["error_rate"] == 0.0
    assert s["avg_latency_ms"] == 0.0
    assert s["last_invoked_at"] is None


@pytest.mark.asyncio
async def test_stats_all_tools(client: AsyncClient, stats_tool):
    """Ensure fetching global statistics encompasses standard seeded instances seamlessly."""
    resp = await client.get("/tools/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tools"] >= 1
