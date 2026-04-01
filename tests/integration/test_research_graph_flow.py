import asyncio
import uuid

import pytest
from structlog.testing import capture_logs

from agents.config import AgentConfig
from agents.context import GraphContext
from agents.graph import GraphBusyError, build_research_graph, invoke_research_graph
from agents.response_models import (
    AnalysisResponse,
    CritiqueResponse,
    SynthesisResponse,
    ToolSelectionResponse,
)
from tests.conftest import FakeStructuredLLM


@pytest.mark.asyncio
async def test_full_research_flow_with_loop_back(mock_registry_client):
    cfg = AgentConfig.model_validate({"langfuse_enabled": False, "max_iterations": 3})
    llm = FakeStructuredLLM(
        [
            ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="first"),
            AnalysisResponse(analysis="## round1"),
            CritiqueResponse(
                critique="need more",
                critique_pass=False,
                gaps=["expand"],
            ),
            ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="second"),
            AnalysisResponse(analysis="## round2"),
            CritiqueResponse(critique="ok", critique_pass=True, gaps=[]),
            SynthesisResponse(
                synthesis="# Final\nSee [Paper](https://arxiv.org/abs/1) for detail.",
            ),
        ],
    )
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": cfg}
    graph = build_research_graph()
    tid = str(uuid.uuid4())
    result = await invoke_research_graph(
        graph,
        {"query": "What?", "trace_id": tid, "session_id": "int-session"},
        ctx,
    )
    assert result["synthesis"]
    assert result["critique_pass"] is True
    u = result.get("token_usage") or {}
    assert "researcher" in u and "analyst" in u
    assert uuid.UUID(result["session_id"])
    assert result.get("client_session_id") == "int-session"


@pytest.mark.asyncio
async def test_full_flow_logs_contain_trace_and_session_ids(mock_registry_client):
    cfg = AgentConfig.model_validate({"langfuse_enabled": False, "max_iterations": 1})
    llm = FakeStructuredLLM(
        [
            ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="x"),
            AnalysisResponse(analysis="a"),
            CritiqueResponse(critique="c", critique_pass=True, gaps=[]),
            SynthesisResponse(synthesis="s"),
        ],
    )
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": cfg}
    graph = build_research_graph()
    tid = str(uuid.uuid4())
    with capture_logs() as cap:
        await invoke_research_graph(
            graph,
            {"query": "Q", "trace_id": tid, "session_id": "log-hint"},
            ctx,
        )
    text = str(cap)
    assert tid in text
    assert "log-hint" in text


@pytest.mark.asyncio
async def test_max_iterations_routes_to_synthesizer(mock_registry_client):
    cfg = AgentConfig.model_validate({"langfuse_enabled": False, "max_iterations": 2})
    llm = FakeStructuredLLM(
        [
            ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="a1"),
            AnalysisResponse(analysis="a"),
            CritiqueResponse(critique="bad1", critique_pass=False, gaps=["g"]),
            ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="a2"),
            AnalysisResponse(analysis="b"),
            CritiqueResponse(critique="bad2", critique_pass=False, gaps=["g"]),
            SynthesisResponse(synthesis="# Partial\nSee [Paper](https://arxiv.org/abs/1)."),
        ],
    )
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": cfg}
    graph = build_research_graph()
    tid = str(uuid.uuid4())
    result = await invoke_research_graph(
        graph,
        {"query": "What?", "trace_id": tid, "session_id": "exhaust"},
        ctx,
    )
    assert result["synthesis"]
    assert result["iteration_count"] == 2
    assert result["critique_pass"] is False


@pytest.mark.asyncio
async def test_graph_timeout(mock_registry_client):
    cfg = AgentConfig.model_validate(
        {"langfuse_enabled": False, "graph_timeout_seconds": 1, "max_iterations": 1},
    )

    class SlowLLM(FakeStructuredLLM):
        def with_structured_output(self, schema, include_raw=False):
            runnable = super().with_structured_output(schema, include_raw=include_raw)

            class Wrapped:
                async def ainvoke(self, *a, **kw):
                    await asyncio.sleep(2.0)
                    return await runnable.ainvoke(*a, **kw)

            return Wrapped()

    llm = SlowLLM(
        [
            ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="x"),
            AnalysisResponse(analysis="a"),
            CritiqueResponse(critique="c", critique_pass=True, gaps=[]),
            SynthesisResponse(synthesis="s"),
        ],
    )
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": cfg}
    graph = build_research_graph()
    tid = str(uuid.uuid4())
    with pytest.raises(TimeoutError):
        await invoke_research_graph(
            graph,
            {"query": "What?", "trace_id": tid, "session_id": "to"},
            ctx,
        )


@pytest.mark.asyncio
async def test_graph_busy_second_call(mock_registry_client):
    import agents.graph as graph_mod

    cfg = AgentConfig.model_validate({"langfuse_enabled": False})
    llm = FakeStructuredLLM(
        [
            ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="1"),
            AnalysisResponse(analysis="a"),
            CritiqueResponse(critique="c", critique_pass=True, gaps=[]),
            SynthesisResponse(synthesis="s"),
        ],
    )
    ctx: GraphContext = {"llm": llm, "registry": mock_registry_client, "agent_config": cfg}
    graph = build_research_graph()
    tid = str(uuid.uuid4())
    async with graph_mod._run_lock:
        graph_mod._busy = True
    try:
        with pytest.raises(GraphBusyError):
            await invoke_research_graph(
                graph,
                {"query": "Q", "trace_id": tid, "session_id": "b1"},
                ctx,
            )
    finally:
        async with graph_mod._run_lock:
            graph_mod._busy = False
