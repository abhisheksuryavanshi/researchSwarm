from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from registry.database import get_db
from registry.models import Tool, ToolCapability
from registry.schemas import ToolCreateRequest, ToolResponse, ToolUpdateRequest

router = APIRouter()
logger = structlog.get_logger()


def _tool_to_response(tool: Tool) -> dict:
    """
    Serialize a Tool model instance into a standard dictionary format.
    Used consistently to structure the API responses.
    """
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
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new tool registration in the system database.
    Rejects the request appropriately if the tool ID naturally exists.
    """
    existing = await db.execute(select(Tool).where(Tool.tool_id == payload.tool_id))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tool with id '{payload.tool_id}' already exists.",
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
    db: AsyncSession = Depends(get_db),
):
    """
    Patch an existing tool's descriptive and configuration properties.
    Fails systematically with a 404 if the target tool id is absent.
    """
    result = await db.execute(select(Tool).where(Tool.tool_id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found.")

    update_data = payload.model_dump(exclude_unset=True)

    if "capabilities" in update_data:
        for cap in list(tool.capabilities):
            await db.delete(cap)
        await db.flush()
        for cap_tag in update_data.pop("capabilities"):
            tool.capabilities.append(ToolCapability(capability=cap_tag))

    for field, value in update_data.items():
        setattr(tool, field, value)

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
    """
    Logically soft-delete a designated tool by deprecating its status.
    Effectively prevents further use without erasing historical usage logging data.
    """
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
