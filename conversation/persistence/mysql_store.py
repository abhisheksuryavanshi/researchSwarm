from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from conversation.persistence.mysql_models import ResearchSnapshotRow, SessionRow, SessionTurnRow


class MysqlSessionStore:
    """Async MySQL persistence for sessions, turns, snapshots (registry-aligned DSN)."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
        self._sessions = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def dispose(self) -> None:
        await self._engine.dispose()

    async def create_session(
        self,
        owner_principal_id: str,
        *,
        tenant_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> SessionRow:
        now = datetime.now(timezone.utc)
        sid = str(uuid.uuid4())
        row = SessionRow(
            id=sid,
            owner_principal_id=owner_principal_id,
            tenant_id=tenant_id,
            status="active",
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        async with self._sessions() as s:
            s.add(row)
            await s.commit()
            await s.refresh(row)
        return row

    async def get_session_for_owner(
        self, session_id: str, owner_principal_id: str
    ) -> SessionRow | None:
        async with self._sessions() as s:
            r = await s.get(SessionRow, session_id)
            if r is None:
                return None
            if r.owner_principal_id != owner_principal_id:
                return None
            return r

    async def get_session_any_owner(self, session_id: str) -> SessionRow | None:
        async with self._sessions() as s:
            return await s.get(SessionRow, session_id)

    async def next_turn_index(self, session_id: str) -> int:
        async with self._sessions() as s:
            q = select(func.coalesce(func.max(SessionTurnRow.turn_index), -1)).where(
                SessionTurnRow.session_id == session_id
            )
            res = await s.execute(q)
            mx = res.scalar_one()
            return int(mx) + 1

    async def append_turn(
        self,
        session_id: str,
        turn_index: int,
        role: str,
        content: dict[str, Any] | list[Any] | str,
        *,
        intent: str | None = None,
        intent_confidence: float | None = None,
        trace_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> SessionTurnRow:
        now = datetime.now(timezone.utc)
        row = SessionTurnRow(
            session_id=session_id,
            turn_index=turn_index,
            role=role,
            content=content,
            intent=intent,
            intent_confidence=intent_confidence,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            created_at=now,
        )
        async with self._sessions() as s:
            s.add(row)
            sess = await s.get(SessionRow, session_id)
            if sess:
                sess.updated_at = now
            await s.commit()
            await s.refresh(row)
        return row

    async def find_turn_by_idempotency(
        self, session_id: str, idempotency_key: str
    ) -> SessionTurnRow | None:
        async with self._sessions() as s:
            q = select(SessionTurnRow).where(
                SessionTurnRow.session_id == session_id,
                SessionTurnRow.idempotency_key == idempotency_key,
            )
            res = await s.execute(q)
            return res.scalar_one_or_none()

    async def get_turn(self, session_id: str, turn_index: int) -> SessionTurnRow | None:
        async with self._sessions() as s:
            q = select(SessionTurnRow).where(
                SessionTurnRow.session_id == session_id,
                SessionTurnRow.turn_index == turn_index,
            )
            res = await s.execute(q)
            return res.scalar_one_or_none()

    async def latest_snapshot(self, session_id: str) -> ResearchSnapshotRow | None:
        async with self._sessions() as s:
            q = (
                select(ResearchSnapshotRow)
                .where(ResearchSnapshotRow.session_id == session_id)
                .order_by(ResearchSnapshotRow.after_turn_index.desc())
                .limit(1)
            )
            res = await s.execute(q)
            return res.scalar_one_or_none()

    async def save_snapshot(
        self, session_id: str, after_turn_index: int, state_blob: dict[str, Any]
    ) -> ResearchSnapshotRow:
        now = datetime.now(timezone.utc)
        row = ResearchSnapshotRow(
            session_id=session_id,
            after_turn_index=after_turn_index,
            state_blob=state_blob,
            created_at=now,
        )
        async with self._sessions() as s:
            s.add(row)
            sess = await s.get(SessionRow, session_id)
            if sess:
                sess.updated_at = now
            await s.commit()
            await s.refresh(row)
        return row
