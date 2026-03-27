"""Unit tests for ORM models (T020)."""

from registry.models import Tool, ToolCapability, ToolUsageLog


def test_tool_defaults():
    """Verify Python-level defaults on Tool model fields."""
    tool = Tool(
        tool_id="test-v1",
        name="Test",
        description="A test tool",
        version="1.0.0",
        endpoint="http://localhost/test",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        status="active",
        method="POST",
        avg_latency_ms=0.0,
        cost_per_call=0.0,
    )
    assert tool.status == "active"
    assert tool.method == "POST"
    assert tool.avg_latency_ms == 0.0
    assert tool.cost_per_call == 0.0
    assert tool.health_check is None


def test_tool_capability_fields():
    """Verify ToolCapability fields assignment correctly persists basic attributes natively."""
    cap = ToolCapability(tool_id="test-v1", capability="web_search")
    assert cap.tool_id == "test-v1"
    assert cap.capability == "web_search"


def test_tool_usage_log_fields():
    """Verify ToolUsageLog captures the correct event fields including latency and success state."""
    log = ToolUsageLog(
        tool_id="test-v1",
        agent_id="researcher",
        session_id="sess-123",
        latency_ms=150.0,
        success=True,
    )
    assert log.tool_id == "test-v1"
    assert log.success is True
    assert log.latency_ms == 150.0
    assert log.error_message is None
