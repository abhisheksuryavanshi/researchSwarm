import uuid

import pytest
from langgraph.runtime import Runtime

from agents.context import GraphContext
from agents.nodes.critic import critic_node, route_after_critic
from agents.response_models import CritiqueResponse
from agents.state import merge_graph_defaults
from tests.conftest import FakeStructuredLLM


@pytest.mark.asyncio
async def test_critic_pass_scenario(mock_registry_client, agent_config):
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
            "analysis": "a",
            "iteration_count": 1,
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM(
        [CritiqueResponse(critique="ok", critique_pass=True, gaps=[])],
    )
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    out = await critic_node(state, Runtime(context=ctx))
    assert out["critique_pass"] is True
    assert out["gaps"] == []


@pytest.mark.asyncio
async def test_critic_fail_scenario(mock_registry_client, agent_config):
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
            "analysis": "a",
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM(
        [
            CritiqueResponse(
                critique="no",
                critique_pass=False,
                gaps=["more data"],
            ),
        ],
    )
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    out = await critic_node(state, Runtime(context=ctx))
    assert out["critique_pass"] is False
    assert out["gaps"]


def test_route_after_critic_loop():
    s = {
        "critique_pass": False,
        "iteration_count": 1,
        "max_iterations": 3,
    }
    assert route_after_critic(s) == "researcher"


def test_route_after_critic_synthesizer_on_pass():
    s = {"critique_pass": True, "iteration_count": 1, "max_iterations": 3}
    assert route_after_critic(s) == "synthesizer"


def test_route_after_critic_exhausted():
    s = {"critique_pass": False, "iteration_count": 3, "max_iterations": 3}
    assert route_after_critic(s) == "synthesizer"
