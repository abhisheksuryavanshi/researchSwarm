import uuid

import pytest
from langgraph.runtime import Runtime

from agents.context import GraphContext
from agents.nodes.critic import critic_node
from agents.response_models import CritiqueResponse
from agents.state import merge_graph_defaults
from tests.conftest import FakeStructuredLLM


@pytest.mark.asyncio
async def test_critic_contract_pass(mock_registry_client, agent_config):
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
            "analysis": "good",
            "raw_findings": [],
            "sources": [],
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM(
        [CritiqueResponse(critique="acceptable", critique_pass=True, gaps=[])],
    )
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    out = await critic_node(state, Runtime(context=ctx))
    assert isinstance(out["critique"], str) and len(out["critique"]) > 0
    assert out["critique_pass"] is True
    assert out["gaps"] == []
    assert "critic" in out["token_usage"]
    assert mock_registry_client.invoke.await_count == 0


@pytest.mark.asyncio
async def test_critic_contract_fail_has_gaps(mock_registry_client, agent_config):
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
            "analysis": "weak",
            "raw_findings": [],
            "sources": [],
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM(
        [
            CritiqueResponse(
                critique="missing evidence",
                critique_pass=False,
                gaps=["add primary sources"],
            ),
        ],
    )
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    out = await critic_node(state, Runtime(context=ctx))
    assert out["critique_pass"] is False
    assert len(out["gaps"]) >= 1
    assert all(len(g.strip()) > 0 for g in out["gaps"])
