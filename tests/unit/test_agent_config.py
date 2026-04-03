import pytest
from pydantic import ValidationError

from agents.config import AgentConfig


def test_agent_config_defaults():
    c = AgentConfig.model_validate({})
    assert c.llm_provider == "groq"
    assert c.llm_model == "llama-3.1-8b-instant"
    assert c.ollama_base_url == "http://localhost:11434"
    assert c.llm_temperature == 0.1
    assert c.llm_timeout_seconds == 30
    assert c.llm_max_retries == 3
    assert c.llm_retries_enabled is False
    assert c.max_iterations == 3
    assert c.graph_timeout_seconds == 180
    assert c.wikipedia_enrich_with_parse is True
    assert c.wikipedia_max_article_chars == 100_000


def test_llm_retries_enabled_uses_max_retries(monkeypatch):
    monkeypatch.setenv("LLM_RETRIES_ENABLED", "true")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    c = AgentConfig()
    assert c.llm_retries_enabled is True
    assert c.llm_max_retries == 2


def test_max_iterations_validation():
    with pytest.raises(ValidationError):
        AgentConfig.model_validate({"max_iterations": 6})


def test_graph_timeout_seconds_from_env(monkeypatch):
    monkeypatch.setenv("GRAPH_TIMEOUT_SECONDS", "120")
    c = AgentConfig()
    assert c.graph_timeout_seconds == 120
