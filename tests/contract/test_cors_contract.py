"""CORS headers contract for operator web UI (FR-021)."""

import pytest
from httpx import AsyncClient

ORIGIN = "http://localhost:5173"
EXPECTED_HEADERS = (
    "Authorization",
    "Content-Type",
    "X-Trace-ID",
    "X-Session-ID",
    "Idempotency-Key",
)


@pytest.mark.asyncio
async def test_cors_preflight_options(client: AsyncClient):
    resp = await client.options(
        "/tools/search",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": ", ".join(h.lower() for h in EXPECTED_HEADERS),
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == ORIGIN
    allow_headers = (resp.headers.get("access-control-allow-headers") or "").lower()
    for name in EXPECTED_HEADERS:
        assert name.lower() in allow_headers.replace(" ", "")
    methods = (resp.headers.get("access-control-allow-methods") or "").upper()
    assert "GET" in methods
    assert "POST" in methods
    assert resp.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_cors_get_with_origin(client: AsyncClient):
    resp = await client.get(
        "/tools/search",
        headers={"Origin": ORIGIN},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == ORIGIN
    assert resp.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_cors_post_session_with_origin(client: AsyncClient):
    resp = await client.post(
        "/v1/sessions",
        headers={
            "Origin": ORIGIN,
            "Authorization": "Bearer test-principal-cors",
        },
    )
    assert resp.status_code in (201, 503)
    assert resp.headers.get("access-control-allow-origin") == ORIGIN
    assert resp.headers.get("access-control-allow-credentials") == "true"
