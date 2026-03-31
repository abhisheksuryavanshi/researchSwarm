import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from registry.database import get_db
from registry.models import Tool, ToolUsageLog
from registry.schemas import UsageLogCreateRequest

router = APIRouter()
logger = structlog.get_logger()


@router.post("/tools/usage-log", status_code=status.HTTP_201_CREATED)
async def create_usage_log(
    body: UsageLogCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    result = await db.execute(select(Tool).where(Tool.tool_id == body.tool_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{body.tool_id}' not found.",
        )
    log = ToolUsageLog(
        tool_id=body.tool_id,
        agent_id=body.agent_id,
        session_id=body.session_id,
        latency_ms=body.latency_ms,
        success=body.success,
        error_message=body.error_message,
    )
    db.add(log)
    await db.commit()
    await logger.ainfo("usage_log_created", tool_id=body.tool_id, success=body.success)
    return {"status": "created"}
