from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from registry.database import get_db
from registry.models import Tool
from registry.schemas import ToolBindResponse

router = APIRouter()


@router.get("/tools/{tool_id}/bind", response_model=ToolBindResponse)
async def bind_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tool).where(Tool.tool_id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found.")

    return ToolBindResponse(
        name=tool.tool_id,
        description=tool.description,
        args_schema=tool.input_schema,
        endpoint=tool.endpoint,
        method=tool.method,
        version=tool.version,
        return_schema=tool.output_schema,
    )
