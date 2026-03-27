"""Contract tests for POST /tools/register (T013)."""

import pytest
from httpx import AsyncClient

VALID_TOOL_PAYLOAD = {
    "tool_id": "test-tool-v1",
    "name": "Test Tool",
    "description": "A test tool for verifying registration works correctly in contract tests",
    "capabilities": ["testing", "validation"],
    "input_schema": {"type": "object", "properties": {"input": {"type": "string"}}},
    "output_schema": {"type": "object", "properties": {"output": {"type": "string"}}},
    "endpoint": "http://localhost:9999/test",
    "version": "1.0.0",
}


@pytest.mark.asyncio
async def test_register_tool_201(client: AsyncClient):
    """Verify clean tool injections successfully bind returning identically valid responses."""
    response = await client.post("/tools/register", json=VALID_TOOL_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert data["tool_id"] == "test-tool-v1"
    assert data["name"] == "Test Tool"
    assert data["status"] == "active"
    assert data["capabilities"] == ["testing", "validation"]
    assert data["version"] == "1.0.0"
    assert data["method"] == "POST"
    assert data["avg_latency_ms"] == 0.0
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_register_tool_422_missing_fields(client: AsyncClient):
    """Enforce strict field population preventing broken structural payloads systematically."""
    response = await client.post("/tools/register", json={"tool_id": "bad"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_tool_422_invalid_tool_id(client: AsyncClient):
    """Verify tool id formats properly fail when invalid characters enter directly."""
    payload = {**VALID_TOOL_PAYLOAD, "tool_id": "INVALID_ID!"}
    response = await client.post("/tools/register", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_tool_409_duplicate(client: AsyncClient):
    """Assert unique constraints hold tight during repeat registrations synchronously."""
    payload = {**VALID_TOOL_PAYLOAD, "tool_id": "dup-tool-v1"}
    resp1 = await client.post("/tools/register", json=payload)
    assert resp1.status_code == 201
    resp2 = await client.post("/tools/register", json=payload)
    assert resp2.status_code == 409
