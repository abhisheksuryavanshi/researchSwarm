"""Unit tests for Pydantic schema validation (T019)."""

import pytest
from pydantic import ValidationError

from registry.schemas import ToolCreateRequest


def _base_payload(**overrides):
    base = {
        "tool_id": "valid-tool-v1",
        "name": "Valid Tool",
        "description": "A valid test tool for unit testing schema validation",
        "capabilities": ["testing"],
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "endpoint": "http://localhost:9999/test",
        "version": "1.0.0",
    }
    base.update(overrides)
    return base


class TestToolIdValidation:
    def test_valid_tool_id(self):
        t = ToolCreateRequest(**_base_payload(tool_id="my-tool-v1"))
        assert t.tool_id == "my-tool-v1"

    def test_valid_tool_id_no_hyphens(self):
        t = ToolCreateRequest(**_base_payload(tool_id="mytool"))
        assert t.tool_id == "mytool"

    @pytest.mark.parametrize(
        "bad_id",
        ["UPPERCASE", "has spaces", "-starts-hyphen", "ends-hyphen-", "a!", "ab"],
    )
    def test_invalid_tool_id(self, bad_id):
        with pytest.raises(ValidationError):
            ToolCreateRequest(**_base_payload(tool_id=bad_id))


class TestVersionValidation:
    def test_valid_semver(self):
        t = ToolCreateRequest(**_base_payload(version="2.1.0"))
        assert t.version == "2.1.0"

    @pytest.mark.parametrize("bad", ["v1.0.0", "1.0", "1", "1.0.0-beta"])
    def test_invalid_semver(self, bad):
        with pytest.raises(ValidationError):
            ToolCreateRequest(**_base_payload(version=bad))


class TestEndpointValidation:
    def test_valid_http(self):
        t = ToolCreateRequest(**_base_payload(endpoint="http://example.com/api"))
        assert t.endpoint == "http://example.com/api"

    def test_valid_https(self):
        t = ToolCreateRequest(**_base_payload(endpoint="https://example.com/api"))
        assert t.endpoint == "https://example.com/api"

    def test_invalid_endpoint(self):
        with pytest.raises(ValidationError):
            ToolCreateRequest(**_base_payload(endpoint="ftp://bad.com"))


class TestCapabilityValidation:
    def test_valid_capability(self):
        t = ToolCreateRequest(**_base_payload(capabilities=["web_search", "general_knowledge"]))
        assert t.capabilities == ["web_search", "general_knowledge"]

    @pytest.mark.parametrize("bad_cap", ["UPPER", "has-hyphen", "1starts_num", "has space"])
    def test_invalid_capability(self, bad_cap):
        with pytest.raises(ValidationError):
            ToolCreateRequest(**_base_payload(capabilities=[bad_cap]))


class TestDescriptionValidation:
    def test_too_short(self):
        with pytest.raises(ValidationError):
            ToolCreateRequest(**_base_payload(description="short"))

    def test_valid_long(self):
        t = ToolCreateRequest(**_base_payload(description="A sufficiently long description"))
        assert len(t.description) >= 10
