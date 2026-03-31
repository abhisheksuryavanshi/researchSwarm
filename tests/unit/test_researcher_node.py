import uuid

import pytest
from langgraph.runtime import Runtime

from agents.context import GraphContext
from agents.nodes.researcher import researcher_node
from agents.response_models import ToolSelectionResponse
from agents.state import merge_graph_defaults
from tests.conftest import FakeStructuredLLM


@pytest.mark.asyncio
async def test_researcher_selects_binds_invokes(mock_registry_client, agent_config):
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM(
        [ToolSelectionResponse(selected_tool_ids=["t1", "t2"], reasoning="two")],
    )
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    out = await researcher_node(state, Runtime(context=ctx))
    mock_registry_client.search.assert_awaited()
    mock_registry_client.bind.assert_awaited()
    mock_registry_client.invoke.assert_awaited()
    invoke_call = mock_registry_client.invoke.await_args_list[0]
    assert invoke_call.args[2] != {}
    assert invoke_call.args[2]["query"] == "q?"
    assert len(out["raw_findings"]) >= 1
    assert len(out["sources"]) >= 1


@pytest.mark.asyncio
async def test_researcher_refinement_with_gaps(mock_registry_client, agent_config):
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
            "iteration_count": 1,
            "gaps": ["need more on Y"],
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM(
        [ToolSelectionResponse(selected_tool_ids=["t2"], reasoning="gap fill")],
    )
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    await researcher_node(state, Runtime(context=ctx))
    mock_registry_client.search.assert_awaited()


@pytest.mark.asyncio
async def test_researcher_invoke_fallback(mock_registry_client, agent_config):
    from unittest.mock import AsyncMock

    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM(
        [ToolSelectionResponse(selected_tool_ids=["t1", "t2"], reasoning="two tools fallback")],
    )
    mock_registry_client.invoke.side_effect = [
        Exception("tool down"),
        {"url": "https://u2", "title": "T2"},
    ]

    async def bind_side(tool_id):
        if tool_id == "t1":
            return {
                "endpoint": "https://example.test/t1",
                "method": "POST",
                "name": "t1",
                "description": "d",
                "args_schema": {},
                "version": "1.0.0",
                "return_schema": {},
            }
        return {
            "endpoint": "https://example.test/t2",
            "method": "POST",
            "name": "t2",
            "description": "d",
            "args_schema": {},
            "version": "1.0.0",
            "return_schema": {},
        }

    mock_registry_client.bind = AsyncMock(side_effect=bind_side)
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    out = await researcher_node(state, Runtime(context=ctx))
    assert mock_registry_client.invoke.await_count == 2
    assert len(out["errors"]) >= 1
    assert len(out["raw_findings"]) == 1


@pytest.mark.asyncio
async def test_researcher_registry_unreachable(agent_config):
    from unittest.mock import AsyncMock, MagicMock

    from agents.tools.registry_client import RegistryClient

    reg = MagicMock(spec=RegistryClient)
    reg.search = AsyncMock(side_effect=OSError("down"))
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM([])
    ctx: GraphContext = {"llm": llm, "registry": reg, "agent_config": agent_config}
    out = await researcher_node(state, Runtime(context=ctx))
    assert out["errors"]


@pytest.mark.asyncio
async def test_researcher_builds_payload_from_args_schema(mock_registry_client, agent_config):
    from unittest.mock import AsyncMock

    state = merge_graph_defaults(
        {
            "query": "latest transformer advances",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
            "constraints": {"max_results": 5, "sources": ["arxiv"]},
            "gaps": ["recent benchmarks"],
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM(
        [ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="schema aware")],
    )

    mock_registry_client.bind = AsyncMock(
        return_value={
            "endpoint": "https://example.test/t1",
            "method": "POST",
            "name": "t1",
            "description": "d",
            "args_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                    "filters": {"type": "object"},
                    "gaps": {"type": "array"},
                },
                "required": ["query", "max_results"],
            },
            "version": "1.0.0",
            "return_schema": {},
        }
    )
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    await researcher_node(state, Runtime(context=ctx))

    payload = mock_registry_client.invoke.await_args_list[0].args[2]
    assert payload["query"] == "latest transformer advances"
    assert payload["max_results"] == 5
    assert payload["filters"] == {"max_results": 5, "sources": ["arxiv"]}
    assert payload["gaps"] == ["recent benchmarks"]
