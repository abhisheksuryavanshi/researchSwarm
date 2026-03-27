from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from registry.database import get_db
from registry.schemas import ToolSearchResponse
from registry.search import search_tools

router = APIRouter()


@router.get("/tools/search", response_model=ToolSearchResponse)
async def search(
    capability: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Discover registered tools optionally filtered by specific capability tags.
    Orchestrates the query securely using the search_tools logic.
    """
    results = await search_tools(
        db=db,
        capability=capability,
        limit=limit,
    )

    return ToolSearchResponse(
        results=results,
        total=len(results),
        capability_filter=capability,
    )
