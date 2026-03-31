"""ToolDiscoveryTool is invokable as a standard LangChain tool (ainvoke)."""

import pytest

from agents.response_models import ToolSelectionResponse
from agents.tools.discovery import ToolDiscoveryTool
from tests.conftest import FakeStructuredLLM


@pytest.mark.asyncio
async def test_tool_discovery_ainvoke_structured_args(mock_registry_client, agent_config):
    llm = FakeStructuredLLM(
        [ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="r")],
    )
    tool = ToolDiscoveryTool(
        registry=mock_registry_client,
        llm=llm,
        config=agent_config,
    )
    out = await tool.ainvoke(
        {
            "capability": "",
            "query": "q",
            "constraints": {},
            "gaps": [],
            "agent_id": "agent",
            "session_id": "sess",
        }
    )
    assert isinstance(out, str)
    parsed = __import__("json").loads(out)
    assert "success" in parsed
    assert "attempts" in parsed
