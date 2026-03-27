"""Unit tests for Pydantic schema validation (T019)."""

import pytest
from pydantic import ValidationError

from registry.schemas import ToolCreateRequest


def _base_payload(**overrides):
    """Generate a minimally valid request payload payload allowing dynamic overrides."""
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
    """Group tests focused specifically on format validations of the core tool ID string constraint."""
    def test_valid_tool_id(self):
        """Assert hyphen-included IDs pass seamlessly through validation."""
        t = ToolCreateRequest(**_base_payload(tool_id="my-tool-v1"))
        assert t.tool_id == "my-tool-v1"

    def test_valid_tool_id_no_hyphens(self):
        """Assert uniformly alphanumeric IDs predictably clear format checks."""
        t = ToolCreateRequest(**_base_payload(tool_id="mytool"))
        assert t.tool_id == "mytool"

    @pytest.mark.parametrize(
        "bad_id",
        ["UPPERCASE", "has spaces", "-starts-hyphen", "ends-hyphen-", "a!", "ab"],
    )
    def test_invalid_tool_id(self, bad_id):
        """Reject tool IDs containing disallowed patterns iteratively passed by parametrization."""
        with pytest.raises(ValidationError):
            ToolCreateRequest(**_base_payload(tool_id=bad_id))


class TestVersionValidation:
    """Verify semantic version fields naturally meet regex pattern constraints accurately."""
    def test_valid_semver(self):
        """Accept perfectly compliant 3-part numerics version inputs natively."""
        t = ToolCreateRequest(**_base_payload(version="2.1.0"))
        assert t.version == "2.1.0"

    @pytest.mark.parametrize("bad", ["v1.0.0", "1.0", "1", "1.0.0-beta"])
    def test_invalid_semver(self, bad):
        """Block broken semantics, alphabetic additions, or excessively stripped down variations effectively."""
        with pytest.raises(ValidationError):
            ToolCreateRequest(**_base_payload(version=bad))


class TestEndpointValidation:
    """Verify url schema guarantees correctly identifying standard API interfaces."""
    def test_valid_http(self):
        """Allow endpoints originating with standard insecure HTTP correctly."""
        t = ToolCreateRequest(**_base_payload(endpoint="http://example.com/api"))
        assert t.endpoint == "http://example.com/api"

    def test_valid_https(self):
        """Allow endpoint inputs appropriately secured with HTTPS protocols correctly."""
        t = ToolCreateRequest(**_base_payload(endpoint="https://example.com/api"))
        assert t.endpoint == "https://example.com/api"

    def test_invalid_endpoint(self):
        """Prevent FTP or explicitly non web conforming URL usage directly natively."""
        with pytest.raises(ValidationError):
            ToolCreateRequest(**_base_payload(endpoint="ftp://bad.com"))


class TestCapabilityValidation:
    """Ensure provided capability arrays contain elements formatted distinctly using snake_case terms."""
    def test_valid_capability(self):
        """Accept arrays composed entirely of standard matching simple words."""
        t = ToolCreateRequest(**_base_payload(capabilities=["web_search", "general_knowledge"]))
        assert t.capabilities == ["web_search", "general_knowledge"]

    @pytest.mark.parametrize("bad_cap", ["UPPER", "has-hyphen", "1starts_num", "has space"])
    def test_invalid_capability(self, bad_cap):
        """Block items containing forbidden spaces, uppercase elements, or leading numbers completely."""
        with pytest.raises(ValidationError):
            ToolCreateRequest(**_base_payload(capabilities=[bad_cap]))


class TestDescriptionValidation:
    """Measure raw text bounds assuring sufficiently detailed manual texts natively input."""
    def test_too_short(self):
        """Reject unhelpful short phrases failing base length boundaries immediately."""
        with pytest.raises(ValidationError):
            ToolCreateRequest(**_base_payload(description="short"))

    def test_valid_long(self):
        """Ensure adequately informative descriptive paragraphs satisfy checks naturally."""
        t = ToolCreateRequest(**_base_payload(description="A sufficiently long description"))
        assert len(t.description) >= 10
