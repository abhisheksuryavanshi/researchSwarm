"""Contract: correlation keys on structured logs (spec 004 / correlation-and-logs.md)."""

import uuid

import pytest
from structlog.testing import capture_logs

from agents.config import AgentConfig
from agents.context import GraphContext
from agents.graph import build_research_graph, invoke_research_graph
from agents.response_models import (
    AnalysisResponse,
    CritiqueResponse,
    SynthesisResponse,
    ToolSelectionResponse,
)
from tests.conftest import FakeStructuredLLM


@pytest.mark.asyncio
async def test_graph_run_logs_include_correlation_fields(mock_registry_client):
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
            {
                "query": "What?",
                "trace_id": tid,
                "session_id": "client-hint-abc",
            },
            ctx,
        )
    blob = str(cap)
    assert "graph_invoke_start" in blob
    assert "graph_invoke_complete" in blob
    assert tid in blob
    assert "client-hint-abc" in blob
    assert "researcher" in blob or "node_enter" in blob
