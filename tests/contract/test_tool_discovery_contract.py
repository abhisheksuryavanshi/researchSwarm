"""Contract tests for ToolDiscoveryInput / ToolDiscoveryResult / InvocationAttempt."""

import pytest
from pydantic import ValidationError

from agents.response_models import (
    InvocationAttempt,
    ToolDiscoveryInput,
    ToolDiscoveryResult,
)


def test_tool_discovery_input_capability_pattern():
    ToolDiscoveryInput(capability="web_search", query="q")
    with pytest.raises(ValidationError):
        ToolDiscoveryInput(capability="Bad-Cap", query="q")
    ToolDiscoveryInput(capability="", query="q")


def test_tool_discovery_input_query_required():
    with pytest.raises(ValidationError):
        ToolDiscoveryInput(capability="", query="")


def test_tool_discovery_result_json_round_trip():
    r = ToolDiscoveryResult(
        success=True,
        tool_id="t1",
        data={"raw": 1},
        source={"url": "u", "title": "x", "tool_id": "t1"},
        attempts=[
            InvocationAttempt(
                tool_id="t1",
                success=True,
                latency_ms=12.0,
                error_message=None,
            )
        ],
    )
    j = r.model_dump_json()
    r2 = ToolDiscoveryResult.model_validate_json(j)
    assert r2.success and r2.tool_id == "t1"
    assert len(r2.attempts) == 1


def test_invocation_attempt_fields():
    a = InvocationAttempt(tool_id="x", success=False, latency_ms=0.0, error_message="e")
    assert a.model_dump()["error_message"] == "e"
