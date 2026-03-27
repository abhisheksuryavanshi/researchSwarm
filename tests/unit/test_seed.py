"""Unit tests for seed script (T027)."""

from registry.schemas import CAPABILITY_PATTERN, SEMVER_PATTERN, TOOL_ID_PATTERN, URL_PATTERN
from registry.seed import SEED_TOOLS


def test_seed_has_7_tools():
    """Assert exactly 7 fundamental tools exist in the default seed payload."""
    assert len(SEED_TOOLS) == 7


def test_all_tools_have_valid_ids():
    """Guarantee every manually curated seed tool conforms exactly to the tool ID schema requirements."""
    for tool in SEED_TOOLS:
        assert TOOL_ID_PATTERN.match(tool["tool_id"]), f"Invalid tool_id: {tool['tool_id']}"


def test_all_tools_have_capabilities():
    """Guarantee seed tools declare explicit capabilities formatted suitably as lowercase words."""
    for tool in SEED_TOOLS:
        assert len(tool["capabilities"]) > 0, f"{tool['tool_id']} has no capabilities"
        for cap in tool["capabilities"]:
            assert CAPABILITY_PATTERN.match(cap), f"Invalid capability: {cap}"


def test_all_tools_have_valid_versions():
    """Assert every standard issue tool utilizes formalized semantic versioning formats properly."""
    for tool in SEED_TOOLS:
        assert SEMVER_PATTERN.match(tool["version"]), f"Invalid version: {tool['version']}"


def test_all_tools_have_valid_endpoints():
    """Assert seed configurations expose HTTP/HTTPS endpoints successfully configured without missing parts."""
    for tool in SEED_TOOLS:
        assert URL_PATTERN.match(tool["endpoint"]), f"Invalid endpoint: {tool['endpoint']}"


def test_all_tools_have_schemas():
    """Check that all built-in applications expose strictly defined input and output JSON schemas natively."""
    for tool in SEED_TOOLS:
        assert "input_schema" in tool and tool["input_schema"]
        assert "output_schema" in tool and tool["output_schema"]


def test_all_tool_ids_unique():
    """Ensure absolutely no collisions exist between internally configured foundational tool ids."""
    ids = [t["tool_id"] for t in SEED_TOOLS]
    assert len(ids) == len(set(ids))
