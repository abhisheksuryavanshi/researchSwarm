from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from registry.embeddings import EmbeddingProvider
from registry.models import Tool, ToolCapability


async def search_tools(
    db: AsyncSession,
    embedding_provider: EmbeddingProvider,
    capability: str | None = None,
    query: str | None = None,
    limit: int = 10,
    min_score: float = 0.3,
) -> list[dict]:
    stmt = select(Tool).where(
        Tool.status.notin_(["deprecated", "unhealthy"])
    )

    if capability:
        stmt = stmt.join(ToolCapability).where(ToolCapability.capability == capability)

    if query and not capability:
        query_embedding = await embedding_provider.embed(query)
        stmt = stmt.where(Tool.embedding.isnot(None))
        stmt = stmt.order_by(Tool.embedding.cosine_distance(query_embedding))
    elif query and capability:
        query_embedding = await embedding_provider.embed(query)
        stmt = stmt.where(Tool.embedding.isnot(None))
        stmt = stmt.order_by(Tool.embedding.cosine_distance(query_embedding))
    else:
        stmt = stmt.order_by(Tool.created_at.desc())

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    tools = result.scalars().unique().all()

    results = []
    for tool in tools:
        score = None
        if query and tool.embedding is not None:
            query_emb = query_embedding
            cosine_dist = _cosine_distance(query_emb, list(tool.embedding))
            score = 1.0 - cosine_dist
            if score < min_score:
                continue

        results.append({
            "tool_id": tool.tool_id,
            "name": tool.name,
            "description": tool.description,
            "capabilities": [c.capability for c in tool.capabilities],
            "version": tool.version,
            "status": tool.status,
            "score": round(score, 4) if score is not None else None,
            "avg_latency_ms": tool.avg_latency_ms,
        })

    return results


def _cosine_distance(a: list[float], b: list[float]) -> float:
    import math

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - (dot / (norm_a * norm_b))
