from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from registry.database import get_db
from registry.models import Tool, ToolUsageLog
from registry.schemas import ToolStatsItem, ToolStatsResponse

router = APIRouter()


@router.get("/tools/stats", response_model=ToolStatsResponse)
async def get_stats(
    tool_id: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    log_filters = []
    if since:
        log_filters.append(ToolUsageLog.invoked_at >= since)

    invocation_count = func.count(ToolUsageLog.id)
    success_count = func.sum(case((ToolUsageLog.success.is_(True), 1), else_=0))
    error_count = func.sum(case((ToolUsageLog.success.is_(False), 1), else_=0))
    avg_latency = func.coalesce(func.avg(ToolUsageLog.latency_ms), 0.0)
    p50_latency = func.coalesce(
        func.percentile_cont(0.5).within_group(ToolUsageLog.latency_ms), 0.0
    )
    p95_latency = func.coalesce(
        func.percentile_cont(0.95).within_group(ToolUsageLog.latency_ms), 0.0
    )
    last_invoked = func.max(ToolUsageLog.invoked_at)

    stmt = (
        select(
            Tool.tool_id,
            Tool.name,
            Tool.status,
            invocation_count.label("invocation_count"),
            success_count.label("success_count"),
            error_count.label("error_count"),
            avg_latency.label("avg_latency_ms"),
            p50_latency.label("p50_latency_ms"),
            p95_latency.label("p95_latency_ms"),
            last_invoked.label("last_invoked_at"),
        )
        .outerjoin(ToolUsageLog, Tool.tool_id == ToolUsageLog.tool_id)
    )

    if tool_id:
        stmt = stmt.where(Tool.tool_id == tool_id)

    if log_filters:
        for f in log_filters:
            stmt = stmt.where(f)

    stmt = stmt.group_by(Tool.tool_id, Tool.name, Tool.status)
    result = await db.execute(stmt)
    rows = result.all()

    stats = []
    total_invocations = 0
    for row in rows:
        inv_count = int(row.invocation_count or 0)
        succ_count = int(row.success_count or 0)
        err_count = int(row.error_count or 0)
        error_rate = round(err_count / inv_count, 4) if inv_count > 0 else 0.0
        total_invocations += inv_count

        stats.append(
            ToolStatsItem(
                tool_id=row.tool_id,
                name=row.name,
                invocation_count=inv_count,
                success_count=succ_count,
                error_count=err_count,
                error_rate=error_rate,
                avg_latency_ms=round(float(row.avg_latency_ms or 0), 2),
                p50_latency_ms=round(float(row.p50_latency_ms or 0), 2),
                p95_latency_ms=round(float(row.p95_latency_ms or 0), 2),
                last_invoked_at=row.last_invoked_at,
                status=row.status,
            )
        )

    return ToolStatsResponse(
        stats=stats,
        total_tools=len(stats),
        total_invocations=total_invocations,
        since=since.isoformat() if since else None,
    )
