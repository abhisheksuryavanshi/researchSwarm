"""Unit tests for ToolDiscoveryTool fallback and timeout behavior."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.config import AgentConfig
from agents.response_models import ToolDiscoveryResult, ToolSelectionResponse
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


_WIKI_BIND = {
    "endpoint": "https://en.wikipedia.org/w/api.php",
    "method": "GET",
    "name": "Wikipedia Lookup",
    "description": "wiki",
    "args_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "default": "query"},
            "format": {"type": "string", "default": "json"},
            "generator": {"type": "string", "default": "search"},
            "gsrsearch": {"type": "string"},
            "gsrlimit": {"type": "integer", "default": 1},
            "gsrnamespace": {"type": "integer", "default": 0},
            "prop": {"type": "string", "default": "extracts|info"},
            "inprop": {"type": "string", "default": "url"},
            "exintro": {"type": "integer", "default": 0},
            "explaintext": {"type": "integer", "default": 1},
        },
        "required": ["gsrsearch"],
    },
    "version": "1",
    "return_schema": {},
}


@pytest.mark.asyncio
async def test_wikipedia_parse_enrichment_merges_plaintext(agent_config):
    reg = MagicMock(spec=RegistryClient)
    reg.search = AsyncMock(
        return_value={
            "results": [
                {
                    "tool_id": "wikipedia-lookup-v1",
                    "name": "Wikipedia Lookup",
                    "description": "wiki",
                    "capabilities": ["general_knowledge"],
                    "avg_latency_ms": 1.0,
                },
            ],
        }
    )
    reg.bind = AsyncMock(return_value=_WIKI_BIND)
    wiki_query = {
        "query": {
            "pages": {
                "42": {
                    "title": "Test Article",
                    "extract": "Short lead.",
                    "fullurl": "https://en.wikipedia.org/wiki/Test_Article",
                }
            }
        }
    }
    parse_body = {
        "parse": {
            "text": "<p>First part. <b>Bold</b> detail.</p><p>Second part.</p>",
        }
    }
    reg.invoke = AsyncMock(side_effect=[wiki_query, parse_body])
    reg.log_usage = AsyncMock(return_value=None)

    llm = FakeStructuredLLM(
        [
            ToolSelectionResponse(
                selected_tool_ids=["wikipedia-lookup-v1"],
                reasoning="encyclopedia",
            )
        ],
    )
    tool = ToolDiscoveryTool(registry=reg, llm=llm, config=agent_config)
    raw = await tool.ainvoke(
        {
            "capability": "general_knowledge",
            "query": "What is test article?",
            "constraints": {},
            "gaps": [],
            "agent_id": "a",
            "session_id": "s",
            "trace_id": str(uuid.uuid4()),
        }
    )
    res = ToolDiscoveryResult.model_validate_json(raw)
    assert res.success is True
    rd = res.data["raw_data"]
    assert rd["extract"] == "Short lead."
    assert "enriched_article_plaintext" in rd
    assert "Bold detail" in rd["enriched_article_plaintext"]
    assert "Second part" in rd["enriched_article_plaintext"]
    assert reg.invoke.await_count == 2


@pytest.mark.asyncio
async def test_wikipedia_enrichment_skipped_when_disabled(agent_config):
    cfg = AgentConfig.model_validate(
        {"langfuse_enabled": False, "wikipedia_enrich_with_parse": False}
    )
    reg = MagicMock(spec=RegistryClient)
    reg.search = AsyncMock(
        return_value={
            "results": [
                {
                    "tool_id": "wikipedia-lookup-v1",
                    "name": "Wikipedia Lookup",
                    "description": "wiki",
                    "capabilities": ["general_knowledge"],
                    "avg_latency_ms": 1.0,
                },
            ],
        }
    )
    reg.bind = AsyncMock(return_value=_WIKI_BIND)
    wiki_query = {
        "query": {
            "pages": {
                "1": {
                    "title": "X",
                    "extract": "lead",
                    "fullurl": "https://en.wikipedia.org/wiki/X",
                }
            }
        }
    }
    reg.invoke = AsyncMock(return_value=wiki_query)
    reg.log_usage = AsyncMock(return_value=None)

    llm = FakeStructuredLLM(
        [
            ToolSelectionResponse(
                selected_tool_ids=["wikipedia-lookup-v1"],
                reasoning="x",
            )
        ],
    )
    tool = ToolDiscoveryTool(registry=reg, llm=llm, config=cfg)
    raw = await tool.ainvoke(
        {
            "capability": "general_knowledge",
            "query": "q",
            "constraints": {},
            "gaps": [],
            "agent_id": "a",
            "session_id": "s",
            "trace_id": str(uuid.uuid4()),
        }
    )
    res = ToolDiscoveryResult.model_validate_json(raw)
    assert res.success is True
    assert "enriched_article_plaintext" not in res.data["raw_data"]
    assert reg.invoke.await_count == 1
