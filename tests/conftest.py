import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

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

    from conversation.persistence import mysql_models as _conversation_mysql_models  # noqa: F401
    from registry.database import Base

    _ = _conversation_mysql_models  # register session tables on Base.metadata

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


class FakeStructuredLLM:
    """Minimal ChatModel that only implements with_structured_output().ainvoke."""

    def __init__(self, sequence: list):
        self.sequence = list(sequence)
        self._idx = 0

    def with_structured_output(self, schema, include_raw=False):
        parent = self

        class Runnable:
            async def ainvoke(self, messages, config=None):
                if parent._idx >= len(parent.sequence):
                    raise RuntimeError("no more fake LLM responses")
                val = parent.sequence[parent._idx]
                parent._idx += 1
                raw = AIMessage(
                    content="ok",
                    usage_metadata={
                        "input_tokens": 10,
                        "output_tokens": 32,
                        "total_tokens": 42,
                    },
                )
                if include_raw:
                    return {"parsed": val, "raw": raw}
                return val

        return Runnable()


@pytest.fixture
def agent_config():
    from agents.config import AgentConfig

    return AgentConfig.model_validate({"langfuse_enabled": False})


@pytest.fixture
def sample_research_state(agent_config):
    from agents.state import merge_graph_defaults

    return merge_graph_defaults(
        {
            "query": "What is X?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "test-session",
        },
        agent_config.max_iterations,
    )


@pytest.fixture
def mock_registry_client():
    from agents.tools.registry_client import RegistryClient

    reg = MagicMock(spec=RegistryClient)
    reg.search = AsyncMock(
        return_value={
            "results": [
                {
                    "tool_id": "t1",
                    "name": "one",
                    "description": "d1",
                    "capabilities": ["c"],
                    "version": "1.0.0",
                    "status": "active",
                    "avg_latency_ms": 1.0,
                },
                {
                    "tool_id": "t2",
                    "name": "two",
                    "description": "d2",
                    "capabilities": ["c"],
                    "version": "1.0.0",
                    "status": "active",
                    "avg_latency_ms": 2.0,
                },
                {
                    "tool_id": "t3",
                    "name": "three",
                    "description": "d3",
                    "capabilities": ["c"],
                    "version": "1.0.0",
                    "status": "active",
                    "avg_latency_ms": 3.0,
                },
            ],
            "total": 3,
        }
    )
    reg.bind = AsyncMock(
        return_value={
            "endpoint": "https://example.test/t1",
            "method": "POST",
            "name": "t1",
            "description": "d",
            "args_schema": {},
            "version": "1.0.0",
            "return_schema": {},
        }
    )
    reg.invoke = AsyncMock(
        return_value={"url": "https://arxiv.org/abs/1", "title": "Paper One"},
    )
    reg.log_usage = AsyncMock(return_value=None)
    return reg


@pytest.fixture
def mock_llm():
    from agents.response_models import (
        AnalysisResponse,
        CritiqueResponse,
        SynthesisResponse,
        ToolSelectionResponse,
    )

    return FakeStructuredLLM(
        [
            ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="best match"),
            AnalysisResponse(analysis="## A\ncontent"),
            CritiqueResponse(critique="good", critique_pass=True, gaps=[]),
            SynthesisResponse(synthesis="## Answer\nSee [Paper](https://arxiv.org/abs/1)"),
        ]
    )
