import pytest
from pydantic import ValidationError

from agents.response_models import (
    AnalysisResponse,
    CritiqueResponse,
    SynthesisResponse,
    ToolSelectionResponse,
)


def test_tool_selection_response():
    m = ToolSelectionResponse(selected_tool_ids=["a", "b"], reasoning="because")
    assert len(m.selected_tool_ids) == 2


def test_tool_selection_too_many():
    with pytest.raises(ValidationError):
        ToolSelectionResponse(selected_tool_ids=["a", "b", "c", "d"], reasoning="x")


def test_tool_selection_empty_reasoning():
    with pytest.raises(ValidationError):
        ToolSelectionResponse(selected_tool_ids=["a"], reasoning="")


def test_critique_response():
    CritiqueResponse(critique="ok", critique_pass=True, gaps=[])


def test_analysis_response():
    AnalysisResponse(analysis="# hello")


def test_synthesis_response():
    SynthesisResponse(synthesis="# out")
