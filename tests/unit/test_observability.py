import uuid
from unittest.mock import MagicMock

import pytest
from langgraph.runtime import Runtime
from structlog.testing import capture_logs

from agents.context import GraphContext
from agents.nodes.researcher import researcher_node
from agents.response_models import ToolSelectionResponse
from agents.state import merge_graph_defaults
from tests.conftest import FakeStructuredLLM


@pytest.mark.asyncio
async def test_logs_contain_correlation_ids(mock_registry_client, agent_config):
    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "obs",
        },
        agent_config.max_iterations,
    )
    llm = FakeStructuredLLM([ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="r")])
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": agent_config}
    with capture_logs() as cap:
        await researcher_node(state, Runtime(context=ctx))
    blob = str(cap)
    assert state["trace_id"] in blob
    assert state["session_id"] in blob
    assert "researcher" in blob


@pytest.mark.asyncio
async def test_get_tracer_passed_when_langfuse_enabled(mock_registry_client, monkeypatch):
    from agents import nodes
    from agents.config import AgentConfig

    cfg = AgentConfig.model_validate({"langfuse_enabled": True})
    mock_cb = MagicMock()
    monkeypatch.setattr(nodes.researcher, "get_tracer", lambda _c: mock_cb)

    state = merge_graph_defaults(
        {
            "query": "q?",
            "trace_id": str(uuid.uuid4()),
            "session_id": "lf",
        },
        cfg.max_iterations,
    )
    llm = FakeStructuredLLM([ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="r")])

    captured = {}

    class LLMWrapper:
        def with_structured_output(self, schema, include_raw=False):
            real = llm.with_structured_output(schema, include_raw=include_raw)

            class R:
                async def ainvoke(self, messages, config=None):
                    captured["config"] = config
                    return await real.ainvoke(messages, config=config)

            return R()

    ctx: GraphContext = {"llm": LLMWrapper(), "registry": mock_registry_client, "agent_config": cfg}
    await researcher_node(state, Runtime(context=ctx))
    conf = captured.get("config") or {}
    cbs = conf.get("callbacks") or []
    assert mock_cb in cbs
