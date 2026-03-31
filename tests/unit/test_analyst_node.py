import uuid

import pytest
from langgraph.runtime import Runtime

from agents.context import GraphContext
from agents.nodes.analyst import analyst_node
from agents.response_models import AnalysisResponse
from agents.state import merge_graph_defaults
from tests.conftest import FakeStructuredLLM


@pytest.mark.asyncio
async def test_analyst_with_findings(mock_registry_client, agent_config):
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
            "raw_findings": [{"x": 1}, {"x": 2}, {"x": 3}],
            "sources": [],
            "accumulated_context": ["prior"],
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM([AnalysisResponse(analysis="## structured")])
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    out = await analyst_node(state, Runtime(context=ctx))
    assert "## structured" in out["analysis"]


@pytest.mark.asyncio
async def test_analyst_empty_findings(mock_registry_client, agent_config):
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
            "raw_findings": [],
            "sources": [],
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM([AnalysisResponse(analysis="No primary data")])
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    out = await analyst_node(state, Runtime(context=ctx))
    assert "note" in out["analysis"].lower() or "no" in out["analysis"].lower()
