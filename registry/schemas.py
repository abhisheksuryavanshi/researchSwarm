import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

TOOL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
CAPABILITY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
URL_PATTERN = re.compile(r"^https?://")


class ToolCreateRequest(BaseModel):
    tool_id: str = Field(..., min_length=3, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=10)
    capabilities: list[str] = Field(..., min_length=1)
    input_schema: dict
    output_schema: dict
    endpoint: str = Field(..., max_length=500)
    version: str = Field(..., max_length=50)
    method: str = Field(default="POST", max_length=10)
    health_check: str | None = None
    cost_per_call: float = 0.0

    @field_validator("tool_id")
    @classmethod
    def validate_tool_id(cls, v: str) -> str:
        if not TOOL_ID_PATTERN.match(v):
            raise ValueError(
                "tool_id must match ^[a-z0-9][a-z0-9-]*[a-z0-9]$ "
                "(lowercase alphanumeric with hyphens)"
            )
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        if not SEMVER_PATTERN.match(v):
            raise ValueError("version must match semver pattern (e.g., 1.0.0)")
        return v

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        if not URL_PATTERN.match(v):
            raise ValueError("endpoint must be a valid HTTP/HTTPS URL")
        return v

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, v: list[str]) -> list[str]:
        for cap in v:
            if not CAPABILITY_PATTERN.match(cap):
                raise ValueError(
                    f"capability '{cap}' must match ^[a-z][a-z0-9_]*$ (lowercase snake_case)"
                )
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty after trimming")
        return v


class ToolUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=10)
    capabilities: list[str] | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    endpoint: str | None = Field(default=None, max_length=500)
    version: str | None = Field(default=None, max_length=50)
    method: str | None = Field(default=None, max_length=10)
    health_check: str | None = None
    cost_per_call: float | None = None
    status: str | None = None

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str | None) -> str | None:
        if v is not None and not SEMVER_PATTERN.match(v):
            raise ValueError("version must match semver pattern (e.g., 1.0.0)")
        return v

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str | None) -> str | None:
        if v is not None and not URL_PATTERN.match(v):
            raise ValueError("endpoint must be a valid HTTP/HTTPS URL")
        return v

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for cap in v:
                if not CAPABILITY_PATTERN.match(cap):
                    raise ValueError(
                        f"capability '{cap}' must match ^[a-z][a-z0-9_]*$ (lowercase snake_case)"
                    )
        return v

    @model_validator(mode="after")
    def at_least_one_field(self) -> "ToolUpdateRequest":
        if all(
            getattr(self, f) is None
            for f in self.model_fields
        ):
            raise ValueError("At least one field must be provided for update")
        return self


class ToolResponse(BaseModel):
    tool_id: str
    name: str
    description: str
    capabilities: list[str]
    input_schema: dict
    output_schema: dict
    endpoint: str
    method: str
    version: str
    health_check: str | None
    status: str
    avg_latency_ms: float
    cost_per_call: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ToolSearchResult(BaseModel):
    tool_id: str
    name: str
    description: str
    capabilities: list[str]
    version: str
    status: str
    score: float | None = None
    avg_latency_ms: float

    model_config = {"from_attributes": True}


class ToolSearchResponse(BaseModel):
    results: list[ToolSearchResult]
    total: int
    query: str | None = None
    capability_filter: str | None = None


class ToolBindResponse(BaseModel):
    name: str
    description: str
    args_schema: dict
    endpoint: str
    method: str
    version: str
    return_schema: dict


class ToolHealthResponse(BaseModel):
    tool_id: str
    status: str
    latency_ms: float | None = None
    checked_at: datetime
    endpoint_checked: str | None = None
    message: str | None = None
    error: str | None = None


class ToolStatsItem(BaseModel):
    tool_id: str
    name: str
    invocation_count: int
    success_count: int
    error_count: int
    error_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    last_invoked_at: datetime | None
    status: str


class ToolStatsResponse(BaseModel):
    stats: list[ToolStatsItem]
    total_tools: int
    total_invocations: int
    since: str | None = None


class UsageLogCreateRequest(BaseModel):
    tool_id: str
    agent_id: str | None = None
    session_id: str | None = None
    latency_ms: float = Field(..., ge=0)
    success: bool
    error_message: str | None = None
