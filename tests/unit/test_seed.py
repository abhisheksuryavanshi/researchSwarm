"""Unit tests for seed script (T027)."""

from registry.schemas import CAPABILITY_PATTERN, SEMVER_PATTERN, TOOL_ID_PATTERN, URL_PATTERN
from registry.seed import SEED_TOOLS


def test_seed_has_7_tools():
    assert len(SEED_TOOLS) == 7


def test_all_tools_have_valid_ids():
    for tool in SEED_TOOLS:
        assert TOOL_ID_PATTERN.match(tool["tool_id"]), f"Invalid tool_id: {tool['tool_id']}"


def test_all_tools_have_capabilities():
    for tool in SEED_TOOLS:
        assert len(tool["capabilities"]) > 0, f"{tool['tool_id']} has no capabilities"
        for cap in tool["capabilities"]:
            assert CAPABILITY_PATTERN.match(cap), f"Invalid capability: {cap}"


def test_all_tools_have_valid_versions():
    for tool in SEED_TOOLS:
        assert SEMVER_PATTERN.match(tool["version"]), f"Invalid version: {tool['version']}"


def test_all_tools_have_valid_endpoints():
    for tool in SEED_TOOLS:
        assert URL_PATTERN.match(tool["endpoint"]), f"Invalid endpoint: {tool['endpoint']}"


def test_all_tools_have_schemas():
    for tool in SEED_TOOLS:
        assert "input_schema" in tool and tool["input_schema"]
        assert "output_schema" in tool and tool["output_schema"]


def test_all_tool_ids_unique():
    ids = [t["tool_id"] for t in SEED_TOOLS]
    assert len(ids) == len(set(ids))
