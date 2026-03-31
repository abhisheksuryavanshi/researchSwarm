from pydantic import BaseModel, Field, field_validator


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
