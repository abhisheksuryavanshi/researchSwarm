from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from registry.database import get_db
from registry.models import Tool, ToolCapability
from registry.schemas import ToolCreateRequest, ToolResponse, ToolUpdateRequest

router = APIRouter()
logger = structlog.get_logger()


def _tool_to_response(tool: Tool) -> dict:
    return {
        "tool_id": tool.tool_id,
        "name": tool.name,
        "description": tool.description,
        "capabilities": [c.capability for c in tool.capabilities],
        "input_schema": tool.input_schema,
        "output_schema": tool.output_schema,
        "endpoint": tool.endpoint,
        "method": tool.method,
        "version": tool.version,
        "health_check": tool.health_check,
        "status": tool.status,
        "avg_latency_ms": tool.avg_latency_ms,
        "cost_per_call": tool.cost_per_call,
        "created_at": tool.created_at,
        "updated_at": tool.updated_at,
    }


@router.post("/tools/register", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def register_tool(
    payload: ToolCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Tool).where(Tool.tool_id == payload.tool_id))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tool with id '{payload.tool_id}' already exists.",
        )

    try:
        embedding = await request.app.state.embedding_provider.embed(payload.description)
    except Exception as exc:
        await logger.aerror("embedding_failed", tool_id=payload.tool_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding provider unavailable.",
        )

    now = datetime.now(timezone.utc)
    tool = Tool(
        tool_id=payload.tool_id,
        name=payload.name,
        description=payload.description,
        version=payload.version,
        endpoint=payload.endpoint,
        method=payload.method,
        input_schema=payload.input_schema,
        output_schema=payload.output_schema,
        health_check=payload.health_check,
        cost_per_call=payload.cost_per_call,
        embedding=embedding,
        created_at=now,
        updated_at=now,
    )

    for cap_tag in payload.capabilities:
        tool.capabilities.append(ToolCapability(capability=cap_tag))

    db.add(tool)
    await db.flush()
    await db.refresh(tool)

    await logger.ainfo("tool_registered", tool_id=tool.tool_id)
    return _tool_to_response(tool)


@router.put("/tools/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str,
    payload: ToolUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tool).where(Tool.tool_id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found.")

    update_data = payload.model_dump(exclude_unset=True)
    description_changed = "description" in update_data

    if "capabilities" in update_data:
        for cap in list(tool.capabilities):
            await db.delete(cap)
        await db.flush()
        for cap_tag in update_data.pop("capabilities"):
            tool.capabilities.append(ToolCapability(capability=cap_tag))

    for field, value in update_data.items():
        setattr(tool, field, value)

    if description_changed:
        try:
            tool.embedding = await request.app.state.embedding_provider.embed(tool.description)
        except Exception as exc:
            await logger.aerror("re_embedding_failed", tool_id=tool_id, error=str(exc))

    tool.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(tool)

    await logger.ainfo("tool_updated", tool_id=tool.tool_id)
    return _tool_to_response(tool)


@router.delete("/tools/{tool_id}", response_model=ToolResponse)
async def delete_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tool).where(Tool.tool_id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found.")

    tool.status = "deprecated"
    tool.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(tool)

    await logger.ainfo("tool_deprecated", tool_id=tool.tool_id)
    return _tool_to_response(tool)
