import pytest
from pydantic import ValidationError

from agents.config import AgentConfig


def test_agent_config_defaults():
    c = AgentConfig.model_validate({})
    assert c.llm_model == "gemini-2.5-flash-lite"
    assert c.llm_temperature == 0.1
    assert c.llm_timeout_seconds == 30
    assert c.llm_max_retries == 3
    assert c.max_iterations == 3
    assert c.graph_timeout_seconds == 60


def test_max_iterations_validation():
    with pytest.raises(ValidationError):
        AgentConfig.model_validate({"max_iterations": 6})


def test_graph_timeout_seconds_from_env(monkeypatch):
    monkeypatch.setenv("GRAPH_TIMEOUT_SECONDS", "120")
    c = AgentConfig()
    assert c.graph_timeout_seconds == 120
