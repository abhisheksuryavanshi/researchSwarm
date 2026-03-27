"""Contract tests for PUT /tools/{id} (T014)."""

import pytest
from httpx import AsyncClient

TOOL_PAYLOAD = {
    "tool_id": "update-test-v1",
    "name": "Update Test Tool",
    "description": "A tool created for testing the update endpoint in contract tests",
    "capabilities": ["testing"],
    "input_schema": {"type": "object", "properties": {"x": {"type": "string"}}},
    "output_schema": {"type": "object", "properties": {"y": {"type": "string"}}},
    "endpoint": "http://localhost:9999/update-test",
    "version": "1.0.0",
}


@pytest.fixture
async def registered_tool(client: AsyncClient):
    """Bootstrap update requests strictly depending on active preexisting tool instances accurately."""
    resp = await client.post("/tools/register", json=TOOL_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_update_tool_200(client: AsyncClient, registered_tool):
    """Verify targeted field alterations dynamically update corresponding elements natively."""
    response = await client.put(
        f"/tools/{registered_tool['tool_id']}",
        json={"name": "Updated Name"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["updated_at"] != registered_tool["updated_at"]


@pytest.mark.asyncio
async def test_update_description(client: AsyncClient, registered_tool):
    """Corroborate independent textual mutations reflecting properly without side effects."""
    response = await client.put(
        f"/tools/{registered_tool['tool_id']}",
        json={"description": "A completely different description for testing updates"},
    )
    assert response.status_code == 200
    assert (
        response.json()["description"]
        == "A completely different description for testing updates"
    )


@pytest.mark.asyncio
async def test_update_tool_404(client: AsyncClient):
    """Intercept modification directives aimed at ghost tools rejecting accordingly."""
    response = await client.put("/tools/nonexistent-tool", json={"name": "New Name"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_tool_422_invalid_fields(client: AsyncClient, registered_tool):
    """Deny semantically noncompliant format additions predictably."""
    response = await client.put(
        f"/tools/{registered_tool['tool_id']}",
        json={"version": "not-semver"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_partial_update_preserves_fields(client: AsyncClient, registered_tool):
    """Guarantee unmentioned underlying record components persist firmly undamaged after patches."""
    response = await client.put(
        f"/tools/{registered_tool['tool_id']}",
        json={"name": "Partial Update"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Partial Update"
    assert data["description"] == registered_tool["description"]
    assert data["endpoint"] == registered_tool["endpoint"]
