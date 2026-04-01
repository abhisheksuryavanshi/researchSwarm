import uuid
from unittest.mock import MagicMock

import pytest
from langgraph.runtime import Runtime
from structlog.testing import capture_logs

from agents.context import GraphContext
from agents.nodes.researcher import researcher_node
from agents.response_models import ToolSelectionResponse
from agents.state import merge_graph_defaults
from agents.tracing import truncate_for_trace
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
    assert state.get("client_session_id") == "obs"
    assert "obs" in blob
    assert "researcher" in blob


def test_truncate_for_trace_empty_and_over_limit():
    assert truncate_for_trace(None, 10) == ""
    assert truncate_for_trace("", 10) == ""
    long = "a" * 100
    out = truncate_for_trace(long, 20)
    assert len(out) < len(long)
    assert out.startswith("aaaaaaaaaaaaaaaaaaaa")
    assert "truncated" in out


@pytest.mark.asyncio
async def test_get_tracer_passed_when_langfuse_enabled(mock_registry_client, monkeypatch):
    from agents import nodes
    from agents.config import AgentConfig

    cfg = AgentConfig.model_validate({"langfuse_enabled": True})
    mock_cb = MagicMock()
    monkeypatch.setattr(nodes.researcher, "get_tracer", lambda _c, **kw: mock_cb)

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
    meta = conf.get("metadata") or {}
    assert meta.get("langfuse_session_id") == state["session_id"]
    assert meta.get("trace_id") == state["trace_id"]
    assert meta.get("client_session_id") == "lf"


def test_emit_critic_route_span_calls_langfuse_when_enabled(monkeypatch):
    from agents.tracing import emit_critic_route_span

    mock_span = MagicMock()
    mock_client = MagicMock()
    mock_client.start_observation.return_value = mock_span

    import agents.tracing as tracing_mod

    monkeypatch.setattr(tracing_mod, "is_langfuse_run_enabled", lambda: True)

    monkeypatch.setattr("langfuse.get_client", lambda: mock_client)

    tid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    state = {
        "trace_id": tid,
        "session_id": sid,
        "client_session_id": "client-hint",
        "critique_pass": False,
        "iteration_count": 0,
        "max_iterations": 3,
    }
    emit_critic_route_span(state, "researcher")  # type: ignore[arg-type]

    mock_client.start_observation.assert_called_once()
    call_kw = mock_client.start_observation.call_args.kwargs
    assert call_kw.get("name") == "route_after_critic"
    assert call_kw.get("as_type") == "span"
    mock_span.end.assert_called_once()
