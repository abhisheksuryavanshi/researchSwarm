from __future__ import annotations

from typing import Any, Optional

import httpx
import structlog

from agents.config import AgentConfig

_LOG = structlog.get_logger()


class RegistryClient:
    def __init__(
        self,
        config: AgentConfig,
        client: Optional[httpx.AsyncClient] = None,
        tool_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._config = config
        self._own_registry = client is None
        timeout = httpx.Timeout(config.llm_timeout_seconds, connect=5.0)
        self._registry = client or httpx.AsyncClient(
            base_url=config.registry_base_url, timeout=timeout
        )
        if tool_client is not None:
            self._tool_client = tool_client
            self._own_tool = False
        else:
            self._tool_client = httpx.AsyncClient(timeout=timeout)
            self._own_tool = True

    async def aclose(self) -> None:
        if self._own_tool:
            await self._tool_client.aclose()
        if self._own_registry:
            await self._registry.aclose()

    async def search(
        self,
        capability: Optional[str] = None,
        limit: int = 10,
        constraints: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if capability:
            params["capability"] = capability
        if constraints and isinstance(constraints.get("sources"), list):
            src = constraints["sources"]
            params["sources"] = ",".join(str(s) for s in src if s is not None)
        r = await self._registry.get("/tools/search", params=params)
        r.raise_for_status()
        return r.json()

    async def bind(self, tool_id: str) -> dict[str, Any]:
        r = await self._registry.get(f"/tools/{tool_id}/bind")
        r.raise_for_status()
        return r.json()

    async def invoke(
        self, endpoint: str, method: str, payload: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        m = method.upper()
        if m == "POST":
            r = await self._tool_client.post(endpoint, json=payload or {})
        elif m == "GET":
            r = await self._tool_client.get(endpoint, params=payload or {})
        else:
            raise ValueError(f"unsupported HTTP method: {method}")
        r.raise_for_status()
        if not r.content:
            return {}
        return r.json()

    async def log_usage(
        self,
        tool_id: str,
        agent_id: Optional[str],
        session_id: Optional[str],
        latency_ms: float,
        success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        """POST usage to the registry (best-effort).

        ``session_id`` MUST be the **canonical** server-issued id from graph state,
        not a client hint alone (see ``client_session_id`` on ``ResearchState``).
        """
        body = {
            "tool_id": tool_id,
            "agent_id": agent_id,
            "session_id": session_id,
            "latency_ms": latency_ms,
            "success": success,
            "error_message": error_message,
        }
        try:
            r = await self._registry.post("/tools/usage-log", json=body)
            r.raise_for_status()
        except Exception as exc:  # pragma: no cover — best-effort logging
            await _LOG.awarning("registry_log_usage_failed", error=str(exc), tool_id=tool_id)
