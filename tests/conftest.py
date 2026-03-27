import asyncio
import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+aiomysql://root:root@localhost:3306/researchswarm_test",
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _db_available() -> bool:
    """Check if the test MySQL database daemon is currently accessible."""
    import socket

    try:
        s = socket.create_connection(("localhost", 3306), timeout=1)
        s.close()
        return True
    except OSError:
        return False


db_available = _db_available()
requires_db = pytest.mark.skipif(
    not db_available,
    reason="MySQL not available on localhost:3306",
)


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """
    Initialize the complete database schema natively before tests run.
    Wipes the schema completely after the session is finished.
    """
    if not db_available:
        yield
        return

    from sqlalchemy.ext.asyncio import create_async_engine

    from registry.database import Base

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session() -> AsyncGenerator:
    """
    Provide an isolated, transactional asynchronous database session.
    Automatically rolls back any uncommitted changes securely after the test completes.
    """
    if not db_available:
        pytest.skip("MySQL not available")

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
async def client(db_session) -> AsyncGenerator:
    """
    Yield a configured asynchronous testing client overriding DB dependencies.
    Provides mocked outgoing request clients and connected databases natively.
    """
    from httpx import ASGITransport, AsyncClient

    from registry.app import create_app
    from registry.database import get_db

    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.state.http_client = AsyncMock()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
