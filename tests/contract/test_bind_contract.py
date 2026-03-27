"""Contract tests for GET /tools/{id}/bind (T025)."""

import pytest
from httpx import AsyncClient

BIND_TOOL = {
    "tool_id": "bind-test-v1",
    "name": "Bind Test Tool",
    "description": "A tool for testing the bind endpoint returns LangChain-compatible definition",
    "capabilities": ["testing"],
    "input_schema": {
        "type": "object",
        "properties": {"ticker": {"type": "string"}},
        "required": ["ticker"],
    },
    "output_schema": {
        "type": "object",
        "properties": {"result": {"type": "string"}},
    },
    "endpoint": "http://localhost:9999/bind-test",
    "version": "2.0.0",
    "method": "POST",
}


@pytest.fixture
async def bound_tool(client: AsyncClient):
    """Pre-register testing tool cleanly to prepare dependency states precisely beforehand."""
    resp = await client.post("/tools/register", json=BIND_TOOL)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_bind_200(client: AsyncClient, bound_tool):
    """Verify tool metadata accurately translates effectively against bind structure requests."""
    resp = await client.get(f"/tools/{bound_tool['tool_id']}/bind")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "bind-test-v1"
    assert data["description"] == BIND_TOOL["description"]
    assert data["args_schema"] == BIND_TOOL["input_schema"]
    assert data["endpoint"] == BIND_TOOL["endpoint"]
    assert data["method"] == "POST"
    assert data["version"] == "2.0.0"
    assert data["return_schema"] == BIND_TOOL["output_schema"]


@pytest.mark.asyncio
async def test_bind_404(client: AsyncClient):
    """Ensure fetching unknown applications returns accurate 404 absent indicators systematically."""
    resp = await client.get("/tools/nonexistent-tool/bind")
    assert resp.status_code == 404
