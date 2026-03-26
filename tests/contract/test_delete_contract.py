"""Contract tests for DELETE /tools/{id} (T015)."""

import pytest
from httpx import AsyncClient

DELETE_TOOL = {
    "tool_id": "delete-test-v1",
    "name": "Delete Test Tool",
    "description": "A tool created specifically for testing the delete/deprecate endpoint",
    "capabilities": ["testing"],
    "input_schema": {"type": "object", "properties": {"x": {"type": "string"}}},
    "output_schema": {"type": "object", "properties": {"y": {"type": "string"}}},
    "endpoint": "http://localhost:9999/delete-test",
    "version": "1.0.0",
}


@pytest.fixture
async def deletable_tool(client: AsyncClient):
    resp = await client.post("/tools/register", json=DELETE_TOOL)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_delete_tool_200(client: AsyncClient, deletable_tool):
    response = await client.delete(f"/tools/{deletable_tool['tool_id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deprecated"


@pytest.mark.asyncio
async def test_delete_tool_404(client: AsyncClient):
    response = await client.delete("/tools/nonexistent-tool")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_deprecated_tool_excluded_from_search(client: AsyncClient, deletable_tool):
    await client.delete(f"/tools/{deletable_tool['tool_id']}")
    search_resp = await client.get("/tools/search", params={"capability": "testing"})
    assert search_resp.status_code == 200
    tool_ids = [r["tool_id"] for r in search_resp.json()["results"]]
    assert deletable_tool["tool_id"] not in tool_ids


@pytest.mark.asyncio
async def test_status_restorable_via_put(client: AsyncClient, deletable_tool):
    await client.delete(f"/tools/{deletable_tool['tool_id']}")
    restore_resp = await client.put(
        f"/tools/{deletable_tool['tool_id']}",
        json={"status": "active"},
    )
    assert restore_resp.status_code == 200
    assert restore_resp.json()["status"] == "active"
