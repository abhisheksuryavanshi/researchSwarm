import httpx
import pytest

from agents.config import AgentConfig
from agents.tools.registry_client import RegistryClient


@pytest.mark.asyncio
async def test_registry_client_search_bind_invoke_log():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        path = request.url.path
        if path == "/tools/search":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "tool_id": "t1",
                            "name": "n1",
                            "description": "d",
                            "capabilities": ["search"],
                            "version": "1.0.0",
                            "status": "active",
                            "avg_latency_ms": 1.0,
                        }
                    ],
                    "total": 1,
                },
            )
        if path == "/tools/t1/bind":
            return httpx.Response(
                200,
                json={
                    "name": "t1",
                    "description": "d",
                    "args_schema": {},
                    "endpoint": "https://tool.example/run",
                    "method": "POST",
                    "version": "1.0.0",
                    "return_schema": {},
                },
            )
        if path == "/tools/usage-log":
            return httpx.Response(201, json={"status": "created"})
        host = request.url.host
        if host == "tool.example" or host == "example.test":
            return httpx.Response(200, json={"url": "https://src", "title": "paper"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    reg_client = httpx.AsyncClient(transport=transport, base_url="http://registry")
    cfg = AgentConfig.model_validate({"registry_base_url": "http://registry"})
    rc = RegistryClient(cfg, client=reg_client, tool_client=reg_client)

    s = await rc.search("search")
    assert s["total"] == 1
    b = await rc.bind("t1")
    assert b["endpoint"] == "https://tool.example/run"
    data = await rc.invoke(b["endpoint"], b["method"], {})
    assert data["title"] == "paper"
    await rc.log_usage("t1", "agent", "sess", 12.0, True, None)
    await rc.aclose()

    assert any("/tools/usage-log" in c[1] for c in calls)


@pytest.mark.asyncio
async def test_registry_client_search_connection_error():
    cfg = AgentConfig.model_validate({"registry_base_url": "http://127.0.0.1:1"})
    rc = RegistryClient(cfg)
    with pytest.raises(httpx.HTTPError):
        await rc.search()
    await rc.aclose()
