"""Integration test: seed idempotency (T034)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from registry.models import Tool
from registry.seed import SEED_TOOLS, seed


@pytest.mark.asyncio
async def test_seed_idempotency(db_session: AsyncSession):
    """Verify executing database seeding consecutively only modifies initial state once exclusively."""
    count1 = await seed(db_session)
    assert count1 == len(SEED_TOOLS)

    result = await db_session.execute(select(func.count()).select_from(Tool))
    total_after_first = result.scalar()
    assert total_after_first >= len(SEED_TOOLS)

    count2 = await seed(db_session)
    assert count2 == 0

    result2 = await db_session.execute(select(func.count()).select_from(Tool))
    total_after_second = result2.scalar()
    assert total_after_second == total_after_first
