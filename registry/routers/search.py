from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from registry.database import get_db
from registry.schemas import ToolSearchResponse
from registry.search import search_tools

router = APIRouter()


@router.get("/tools/search", response_model=ToolSearchResponse)
async def search(
    request: Request,
    capability: str | None = Query(default=None),
    query: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    min_score: float = Query(default=0.3, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    if not capability and not query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of 'capability' or 'query' must be provided.",
        )

    results = await search_tools(
        db=db,
        embedding_provider=request.app.state.embedding_provider,
        capability=capability,
        query=query,
        limit=limit,
        min_score=min_score,
    )

    return ToolSearchResponse(
        results=results,
        total=len(results),
        query=query,
        capability_filter=capability,
    )
