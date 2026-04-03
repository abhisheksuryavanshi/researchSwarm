from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from registry.models import Tool, ToolCapability


async def search_tools(
    db: AsyncSession,
    capability: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """
    Search for actively available tools using optional capability filters.
    Returns a sorted list of matched tools with essential metadata.
    """
    stmt = select(Tool).where(
        Tool.status.notin_(["deprecated", "unhealthy", "inactive"])
    )

    if capability:
        stmt = stmt.join(ToolCapability).where(ToolCapability.capability == capability)

    stmt = stmt.order_by(Tool.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    tools = result.scalars().unique().all()

    return [
        {
            "tool_id": tool.tool_id,
            "name": tool.name,
            "description": tool.description,
            "capabilities": [c.capability for c in tool.capabilities],
            "version": tool.version,
            "status": tool.status,
            "avg_latency_ms": tool.avg_latency_ms,
        }
        for tool in tools
    ]
