import uuid

import pytest
from langgraph.runtime import Runtime

from agents.context import GraphContext
from agents.nodes.analyst import analyst_node
from agents.response_models import AnalysisResponse
from agents.state import merge_graph_defaults
from tests.conftest import FakeStructuredLLM


@pytest.mark.asyncio
async def test_analyst_contract(mock_registry_client, agent_config):
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
            "raw_findings": [{"tool_id": "t", "data": {}, "timestamp": "now"}],
            "sources": [{"url": "u", "title": "T", "tool_id": "t"}],
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM([AnalysisResponse(analysis="# A\nok")])
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    out = await analyst_node(state, Runtime(context=ctx))
    assert isinstance(out["analysis"], str) and len(out["analysis"]) > 0
    assert "analyst" in out["token_usage"]
    assert mock_registry_client.bind.await_count == 0
    assert mock_registry_client.invoke.await_count == 0
    assert "messages" in out
