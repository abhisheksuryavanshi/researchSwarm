"""Unit tests for build_dynamic_tool."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from agents.tools.discovery import GenericToolInput, build_dynamic_tool
from agents.tools.registry_client import RegistryClient


@pytest.mark.asyncio
async def test_build_dynamic_tool_empty_schema_uses_generic():
    reg = MagicMock(spec=RegistryClient)
    reg.invoke = AsyncMock(return_value={"ok": True})
    bind = {
        "name": "mytool",
        "description": "desc",
        "args_schema": {},
        "endpoint": "https://tool.example/run",
        "method": "POST",
    }
    tool = build_dynamic_tool(bind, reg, timeout_seconds=30)
    assert tool.name == "mytool"
    assert tool.description == "desc"
    assert tool.args_schema is GenericToolInput
    await tool.ainvoke(
        {"query": "q", "constraints": {"a": 1}, "gaps": ["g"]},
    )
    reg.invoke.assert_awaited_once()
    call = reg.invoke.await_args
    assert call.args[0] == "https://tool.example/run"
    assert call.args[1] == "POST"
    assert call.args[2]["query"] == "q"


@pytest.mark.asyncio
async def test_build_dynamic_tool_typed_schema_validates():
    reg = MagicMock(spec=RegistryClient)
    reg.invoke = AsyncMock(return_value={})
    bind = {
        "name": "typed",
        "description": "d",
        "args_schema": {
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
        "endpoint": "https://tool.example/t",
        "method": "POST",
    }
    tool = build_dynamic_tool(bind, reg, timeout_seconds=30)
    with pytest.raises(ValidationError):
        await tool.ainvoke({})
    await tool.ainvoke({"q": "hello"})
    reg.invoke.assert_awaited()
