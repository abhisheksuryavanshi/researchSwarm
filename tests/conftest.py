import asyncio
import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest

from registry.embeddings import VECTOR_DIMENSION

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/researchswarm_test",
)


class FakeEmbeddingProvider:
    """Deterministic embedding provider for tests — hashes text to produce a stable vector."""

    async def embed(self, text: str) -> list[float]:
        h = hash(text) % (10**9)
        base = [(h >> i & 1) * 0.1 + 0.01 * (i % 10) for i in range(VECTOR_DIMENSION)]
        norm = sum(x * x for x in base) ** 0.5
        if norm == 0:
            return [0.0] * VECTOR_DIMENSION
        return [x / norm for x in base]


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _db_available() -> bool:
    import socket

    try:
        s = socket.create_connection(("localhost", 5432), timeout=1)
        s.close()
        return True
    except OSError:
        return False


db_available = _db_available()
requires_db = pytest.mark.skipif(
    not db_available,
    reason="PostgreSQL not available on localhost:5432",
)


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    if not db_available:
        yield
        return

    from sqlalchemy import text as sa_text
    from sqlalchemy.ext.asyncio import create_async_engine

    from registry.database import Base

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(sa_text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session() -> AsyncGenerator:
    if not db_available:
        pytest.skip("PostgreSQL not available")

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
def fake_embedding_provider() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
async def client(db_session, fake_embedding_provider) -> AsyncGenerator:
    from httpx import ASGITransport, AsyncClient

    from registry.app import create_app
    from registry.database import get_db

    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.state.embedding_provider = fake_embedding_provider
    app.state.http_client = AsyncMock()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
