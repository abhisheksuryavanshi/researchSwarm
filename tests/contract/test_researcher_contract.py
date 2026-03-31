import uuid

import pytest
from langgraph.runtime import Runtime

from agents.context import GraphContext
from agents.nodes.researcher import researcher_node
from agents.response_models import ToolSelectionResponse
from agents.state import merge_graph_defaults
from tests.conftest import FakeStructuredLLM


@pytest.mark.asyncio
async def test_researcher_contract_output_shape(mock_registry_client, agent_config):
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM(
        [ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="r")],
    )
    ctx: GraphContext = {
        "llm": llm,
        "registry": mock_registry_client,
        "agent_config": agent_config,
    }
    out = await researcher_node(state, Runtime(context=ctx))
    assert isinstance(out.get("raw_findings"), list)
    assert isinstance(out.get("sources"), list)
    assert out["iteration_count"] == state["iteration_count"] + 1
    assert "researcher" in out.get("token_usage", {})
    assert "analysis" not in out
    assert "synthesis" not in out
    assert "critique" not in out
    assert "messages" in out
