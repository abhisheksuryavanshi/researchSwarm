"""Contract tests for GET /tools/{id}/health (T029)."""

from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import AsyncClient

HEALTH_TOOL = {
    "tool_id": "health-test-v1",
    "name": "Health Test Tool",
    "description": "A tool for testing health check proxying with mocked responses",
    "capabilities": ["testing"],
    "input_schema": {"type": "object"},
    "output_schema": {"type": "object"},
    "endpoint": "http://localhost:9999/health-test",
    "version": "1.0.0",
    "health_check": "/health",
}

NO_HEALTH_TOOL = {
    "tool_id": "no-health-v1",
    "name": "No Health Tool",
    "description": "A tool without a health check endpoint for testing unknown status",
    "capabilities": ["testing"],
    "input_schema": {"type": "object"},
    "output_schema": {"type": "object"},
    "endpoint": "http://localhost:9999/no-health",
    "version": "1.0.0",
}


@pytest.fixture
async def health_tool(client: AsyncClient):
    resp = await client.post("/tools/register", json=HEALTH_TOOL)
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def no_health_tool(client: AsyncClient):
    resp = await client.post("/tools/register", json=NO_HEALTH_TOOL)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_health_unknown_no_config(client: AsyncClient, no_health_tool):
    resp = await client.get(f"/tools/{no_health_tool['tool_id']}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unknown"
    assert data["endpoint_checked"] is None
    assert "No health check" in data["message"]


@pytest.mark.asyncio
async def test_health_404(client: AsyncClient):
    resp = await client.get("/tools/nonexistent-tool/health")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_health_unhealthy_connection_refused(client: AsyncClient, health_tool):
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")
    client._transport.app.state.http_client = mock_client  # type: ignore

    resp = await client.get(f"/tools/{health_tool['tool_id']}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert data["error"] is not None
