import pytest


@pytest.mark.asyncio
async def test_redis_lock_acquire_release():
    """Lock token round-trip with an in-memory fake Redis client."""
    from conversation.persistence.redis_store import RedisSessionStore

    store = RedisSessionStore("redis://localhost:6379/0")

    class FakeRedis:
        def __init__(self):
            self._locks: dict[str, str] = {}

        async def set(self, key, val, nx=False, px=None):
            if nx and key in self._locks:
                return None
            self._locks[key] = val
            return True

        async def get(self, key):
            return self._locks.get(key)

        async def delete(self, key):
            self._locks.pop(key, None)

        async def aclose(self):
            pass

        async def ping(self):
            return True

    store._client = FakeRedis()  # type: ignore[assignment]

    tok = await store.acquire_turn_lock("sess-1")
    assert tok
    assert await store.acquire_turn_lock("sess-1") is None
    await store.release_turn_lock("sess-1", tok)
    again = await store.acquire_turn_lock("sess-1")
    assert again is not None
