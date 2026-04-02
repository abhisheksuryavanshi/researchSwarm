"""Unit tests for ToolDiscoveryTool fallback and timeout behavior."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.config import AgentConfig
from agents.response_models import ToolSelectionResponse
from agents.tools.discovery import ToolDiscoveryTool
from agents.tools.registry_client import RegistryClient
from tests.conftest import FakeStructuredLLM


@pytest.mark.asyncio
async def test_fallback_second_tool_succeeds(agent_config):
    reg = MagicMock(spec=RegistryClient)
    reg.search = AsyncMock(
        return_value={
            "results": [
                {
                    "tool_id": "t1",
                    "name": "a",
                    "description": "d",
                    "capabilities": ["c"],
                    "avg_latency_ms": 1.0,
                },
                {
                    "tool_id": "t2",
                    "name": "b",
                    "description": "d",
                    "capabilities": ["c"],
                    "avg_latency_ms": 2.0,
                },
            ],
        }
    )

    async def bind_side(tid: str):
        return {
            "endpoint": f"https://ex.test/{tid}",
            "method": "POST",
            "name": tid,
            "description": "d",
            "args_schema": {},
            "version": "1",
            "return_schema": {},
        }

    reg.bind = AsyncMock(side_effect=bind_side)
    reg.invoke = AsyncMock(
        side_effect=[Exception("down"), {"url": "https://ok", "title": "OK"}],
    )
    reg.log_usage = AsyncMock(return_value=None)

    llm = FakeStructuredLLM(
        [ToolSelectionResponse(selected_tool_ids=["t1", "t2"], reasoning="order")],
    )
    tool = ToolDiscoveryTool(registry=reg, llm=llm, config=agent_config)
    raw = await tool.ainvoke(
        {
            "capability": "c",
            "query": "q",
            "constraints": {},
            "gaps": [],
            "agent_id": "a",
            "session_id": "s",
        }
    )
    assert "true" in raw.lower()
    assert reg.invoke.await_count == 2
    assert reg.log_usage.await_count == 2


@pytest.mark.asyncio
async def test_max_attempts_cap(agent_config):
    cfg = AgentConfig.model_validate(
        {"langfuse_enabled": False, "max_tool_fallback_attempts": 2},
    )
    reg = MagicMock(spec=RegistryClient)
    reg.search = AsyncMock(
        return_value={
            "results": [
                {
                    "tool_id": f"t{i}",
                    "name": f"n{i}",
                    "description": "d",
                    "capabilities": ["c"],
                    "avg_latency_ms": float(i),
                }
                for i in range(1, 5)
            ],
        }
    )
    reg.bind = AsyncMock(
        return_value={
            "endpoint": "https://ex.test/x",
            "method": "POST",
            "name": "x",
            "description": "d",
            "args_schema": {},
            "version": "1",
            "return_schema": {},
        }
    )
    reg.invoke = AsyncMock(side_effect=Exception("fail"))
    reg.log_usage = AsyncMock(return_value=None)

    llm = FakeStructuredLLM(
        [ToolSelectionResponse(selected_tool_ids=["t1", "t2", "t3"], reasoning="x")],
    )
    tool = ToolDiscoveryTool(registry=reg, llm=llm, config=cfg)
    raw = await tool.ainvoke(
        {
            "capability": "c",
            "query": "q",
            "constraints": {},
            "gaps": [],
            "agent_id": "a",
            "session_id": "s",
        }
    )
    assert "false" in raw.lower() or '"success": false' in raw.lower()
    assert reg.invoke.await_count == 2


@pytest.mark.asyncio
async def test_log_usage_receives_canonical_session_not_only_client_hint(agent_config):
    canonical = str(uuid.uuid4())
    reg = MagicMock(spec=RegistryClient)
    reg.search = AsyncMock(
        return_value={
            "results": [
                {
                    "tool_id": "t1",
                    "name": "a",
                    "description": "d",
                    "capabilities": ["c"],
                    "avg_latency_ms": 1.0,
                },
            ],
        }
    )
    reg.bind = AsyncMock(
        return_value={
            "endpoint": "https://ex.test/t1",
            "method": "POST",
            "name": "t1",
            "description": "d",
            "args_schema": {},
            "version": "1",
            "return_schema": {},
        }
    )
    reg.invoke = AsyncMock(return_value={"url": "https://ok", "title": "OK"})
    reg.log_usage = AsyncMock(return_value=None)

    llm = FakeStructuredLLM(
        [ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="x")],
    )
    tool = ToolDiscoveryTool(registry=reg, llm=llm, config=agent_config)
    await tool.ainvoke(
        {
            "capability": "c",
            "query": "q",
            "constraints": {},
            "gaps": [],
            "agent_id": "researcher",
            "session_id": canonical,
            "trace_id": str(uuid.uuid4()),
            "client_session_id": "browser-tab-xyz",
        }
    )
    reg.log_usage.assert_awaited()
    kw = reg.log_usage.await_args.kwargs
    assert kw.get("session_id") == canonical
    assert kw.get("session_id") != "browser-tab-xyz"


@pytest.mark.asyncio
async def test_single_llm_selection_no_latency_padding(agent_config):
    """Only explicitly selected tools are tried; search extras are not auto-appended."""
    reg = MagicMock(spec=RegistryClient)
    reg.search = AsyncMock(
        return_value={
            "results": [
                {
                    "tool_id": "t1",
                    "name": "a",
                    "description": "d",
                    "capabilities": ["c"],
                    "avg_latency_ms": 99.0,
                },
                {
                    "tool_id": "t2",
                    "name": "b",
                    "description": "d",
                    "capabilities": ["c"],
                    "avg_latency_ms": 1.0,
                },
            ],
        }
    )
    reg.bind = AsyncMock(
        return_value={
            "endpoint": "https://ex.test/x",
            "method": "POST",
            "name": "x",
            "description": "d",
            "args_schema": {},
            "version": "1",
            "return_schema": {},
        }
    )
    reg.invoke = AsyncMock(side_effect=Exception("fail"))
    reg.log_usage = AsyncMock(return_value=None)

    llm = FakeStructuredLLM(
        [ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="only one needed")],
    )
    tool = ToolDiscoveryTool(registry=reg, llm=llm, config=agent_config)
    raw = await tool.ainvoke(
        {
            "capability": "c",
            "query": "q",
            "constraints": {},
            "gaps": [],
            "agent_id": "a",
            "session_id": "s",
        }
    )
    assert "false" in raw.lower() or '"success": false' in raw.lower()
    assert reg.invoke.await_count == 1
