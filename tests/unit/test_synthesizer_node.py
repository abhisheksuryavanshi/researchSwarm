import uuid

import pytest
from langgraph.runtime import Runtime

from agents.context import GraphContext
from agents.nodes.synthesizer import synthesizer_node
from agents.response_models import SynthesisResponse
from agents.state import merge_graph_defaults
from tests.conftest import FakeStructuredLLM


@pytest.mark.asyncio
async def test_synthesizer_calls_llm(mock_registry_client, agent_config):
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "s1",
            "analysis": "a",
            "raw_findings": [],
            "sources": [{"url": "u1", "title": "T1", "tool_id": "t"}],
            "critique": "ok",
            "critique_pass": True,
            "constraints": {"format": "markdown"},
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM(
        [SynthesisResponse(synthesis="## Done\nRef T1 and u1.")],
    )
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    out = await synthesizer_node(state, Runtime(context=ctx))
    assert "T1" in out["synthesis"] or "u1" in out["synthesis"]
