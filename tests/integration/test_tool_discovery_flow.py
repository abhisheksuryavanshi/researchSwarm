"""Integration-style test: ToolDiscoveryTool with mocked registry + fake LLM."""

import pytest

from agents.response_models import ToolSelectionResponse
from agents.tools.discovery import ToolDiscoveryTool
from tests.conftest import FakeStructuredLLM


@pytest.mark.asyncio
async def test_tool_discovery_happy_path(mock_registry_client, agent_config):
    llm = FakeStructuredLLM(
        [ToolSelectionResponse(selected_tool_ids=["t1"], reasoning="pick t1")],
    )
    tool = ToolDiscoveryTool(
        registry=mock_registry_client,
        llm=llm,
        config=agent_config,
    )
    raw = await tool.ainvoke(
        {
            "capability": "",
            "query": "research question",
            "constraints": {},
            "gaps": [],
            "agent_id": "researcher",
            "session_id": "s1",
        }
    )
    assert isinstance(raw, str)
    assert "success" in raw
    assert "true" in raw.lower()
    mock_registry_client.search.assert_awaited()
    mock_registry_client.bind.assert_awaited()
    mock_registry_client.invoke.assert_awaited()
    mock_registry_client.log_usage.assert_awaited()
