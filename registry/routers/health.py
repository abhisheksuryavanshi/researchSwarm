import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from registry.database import get_db
from registry.models import Tool
from registry.schemas import ToolHealthResponse

router = APIRouter()
logger = structlog.get_logger()

HEALTH_TIMEOUT_MS = 500


@router.get("/tools/{tool_id}/health", response_model=ToolHealthResponse)
async def check_health(
    tool_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tool).where(Tool.tool_id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found.")

    now = datetime.now(timezone.utc)

    if not tool.health_check:
        return ToolHealthResponse(
            tool_id=tool.tool_id,
            status="unknown",
            latency_ms=None,
            checked_at=now,
            endpoint_checked=None,
            message="No health check endpoint configured for this tool.",
        )

    if tool.health_check.startswith("http"):
        health_url = tool.health_check
    else:
        base = tool.endpoint.rsplit("/", 1)[0] + "/"
        health_url = urljoin(base, tool.health_check.lstrip("/"))

    http_client = request.app.state.http_client
    start = time.perf_counter()

    try:
        import httpx

        response = await http_client.get(
            health_url, timeout=httpx.Timeout(HEALTH_TIMEOUT_MS / 1000.0)
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        if response.status_code < 300 and elapsed_ms < HEALTH_TIMEOUT_MS:
            new_status = "healthy"
        else:
            new_status = "degraded"

        tool.status = new_status
        tool.updated_at = now
        await db.flush()

        resp = ToolHealthResponse(
            tool_id=tool.tool_id,
            status=new_status,
            latency_ms=round(elapsed_ms, 2),
            checked_at=now,
            endpoint_checked=health_url,
        )
        if new_status == "degraded":
            resp.message = "Health check responded but exceeded 500ms budget."
        return resp

    except Exception as exc:
        tool.status = "unhealthy"
        tool.updated_at = now
        await db.flush()

        await logger.awarning("health_check_failed", tool_id=tool_id, error=str(exc))

        return ToolHealthResponse(
            tool_id=tool.tool_id,
            status="unhealthy",
            latency_ms=None,
            checked_at=now,
            endpoint_checked=health_url,
            error=str(exc),
        )
