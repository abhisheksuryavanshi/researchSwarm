import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class InvocationAttempt(BaseModel):
    tool_id: str
    success: bool
    latency_ms: float
    error_message: Optional[str] = None


class ToolDiscoveryInput(BaseModel):
    capability: str = ""
    query: str
    constraints: dict = Field(default_factory=dict)
    gaps: list[str] = Field(default_factory=list)
    agent_id: str = ""
    session_id: str = ""
    trace_id: str = ""
    client_session_id: Optional[str] = None

    @field_validator("capability")
    @classmethod
    def capability_tag(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            return ""
        if not re.match(r"^[a-z][a-z0-9_]*$", s):
            raise ValueError(
                "capability must be empty (search all) or match ^[a-z][a-z0-9_]*$"
            )
        return s

    @field_validator("query")
    @classmethod
    def query_non_empty(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("query must be non-empty")
        return v.strip()


class ToolDiscoveryResult(BaseModel):
    success: bool
    tool_id: Optional[str] = None
    data: dict = Field(default_factory=dict)
    source: dict = Field(default_factory=dict)
    attempts: list[InvocationAttempt] = Field(default_factory=list)
    error: Optional[str] = None


class ToolSelectionResponse(BaseModel):
    selected_tool_ids: list[str] = Field(..., min_length=1, max_length=3)
    reasoning: str = Field(..., min_length=1)

    @field_validator("selected_tool_ids")
    @classmethod
    def non_empty_ids(cls, v: list[str]) -> list[str]:
        for tid in v:
            if not tid or not str(tid).strip():
                raise ValueError("tool ids must be non-empty strings")
        return v


class CritiqueResponse(BaseModel):
    critique: str = Field(..., min_length=1)
    critique_pass: bool
    gaps: list[str]


class AnalysisResponse(BaseModel):
    analysis: str = Field(..., min_length=1)


class SynthesisResponse(BaseModel):
    synthesis: str = Field(..., min_length=1)
