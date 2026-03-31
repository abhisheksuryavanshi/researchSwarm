import uuid

import pytest
from langgraph.runtime import Runtime

from agents.context import GraphContext
from agents.nodes.synthesizer import synthesizer_node
from agents.response_models import SynthesisResponse
from agents.state import merge_graph_defaults
from tests.conftest import FakeStructuredLLM


@pytest.mark.asyncio
async def test_synthesizer_contract(mock_registry_client, agent_config):
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
            "analysis": "## a",
            "sources": [{"url": "https://cite.test/x", "title": "Cite", "tool_id": "t"}],
            "critique": "c",
            "critique_pass": True,
        },
        agent_config.max_iterations,
    )
    text = "## Answer\n[Cite](https://cite.test/x) details."
    llm = FakeStructuredLLM([SynthesisResponse(synthesis=text)])
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    out = await synthesizer_node(state, Runtime(context=ctx))
    assert len(out["synthesis"]) > 0
    assert "https://cite.test" in out["synthesis"] or "Cite" in out["synthesis"]
    assert "synthesizer" in out["token_usage"]


@pytest.mark.asyncio
async def test_synthesizer_limitations_when_not_passed(mock_registry_client, agent_config):
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
            "analysis": "## a",
            "sources": [{"url": "https://cite.test/x", "title": "Cite", "tool_id": "t"}],
            "critique": "weak",
            "critique_pass": False,
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM([SynthesisResponse(synthesis="# Out\nSome claim.")])
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    out = await synthesizer_node(state, Runtime(context=ctx))
    assert "limitation" in out["synthesis"].lower()
