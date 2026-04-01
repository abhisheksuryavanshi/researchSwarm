from __future__ import annotations

import json
import secrets
from typing import Any

import redis.asyncio as redis


class RedisSessionStore:
    """Working-set cache, per-session FIFO lock, optional inbox (Redis)."""

    def __init__(
        self,
        redis_url: str,
        *,
        lock_ttl_seconds: int = 120,
        doc_ttl_seconds: int = 86400,
    ):
        self._url = redis_url
        self._lock_ttl_ms = lock_ttl_seconds * 1000
        self._doc_ttl = doc_ttl_seconds
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        if self._client is None:
            self._client = redis.from_url(self._url, decode_responses=True)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _r(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("RedisSessionStore not connected")
        return self._client

    def doc_key(self, session_id: str) -> str:
        return f"session:{session_id}:doc"

    def lock_key(self, session_id: str) -> str:
        return f"session:{session_id}:turn_lock"

    def inbox_key(self, session_id: str) -> str:
        return f"session:{session_id}:inbox"

    async def get_working_doc(self, session_id: str) -> dict[str, Any] | None:
        await self.connect()
        raw = await self._r().get(self.doc_key(session_id))
        if not raw:
            return None
        return json.loads(raw)

    async def set_working_doc(self, session_id: str, doc: dict[str, Any]) -> None:
        await self.connect()
        await self._r().set(
            self.doc_key(session_id),
            json.dumps(doc),
            ex=self._doc_ttl,
        )

    async def delete_working_doc(self, session_id: str) -> None:
        await self.connect()
        await self._r().delete(self.doc_key(session_id))

    async def acquire_turn_lock(self, session_id: str) -> str | None:
        """Return lock token if acquired, else None."""
        await self.connect()
        token = secrets.token_hex(16)
        ok = await self._r().set(
            self.lock_key(session_id),
            token,
            nx=True,
            px=self._lock_ttl_ms,
        )
        return token if ok else None

    async def release_turn_lock(self, session_id: str, token: str) -> None:
        await self.connect()
        key = self.lock_key(session_id)
        cur = await self._r().get(key)
        if cur == token:
            await self._r().delete(key)

    async def inbox_push(self, session_id: str, payload: str) -> None:
        await self.connect()
        await self._r().rpush(self.inbox_key(session_id), payload)

    async def inbox_pop_blocking(self, session_id: str, timeout_s: int = 1) -> str | None:
        await self.connect()
        out = await self._r().blpop(self.inbox_key(session_id), timeout=timeout_s)
        if out is None:
            return None
        return out[1]

    async def ping(self) -> bool:
        try:
            await self.connect()
            return await self._r().ping()
        except Exception:
            return False
