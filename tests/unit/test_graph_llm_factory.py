from langchain_ollama import ChatOllama

from agents.config import AgentConfig
from agents.graph import create_default_llm


def test_create_default_llm_ollama():
    cfg = AgentConfig.model_validate(
        {
            "llm_provider": "ollama",
            "llm_model": "llama3.1:8b",
            "ollama_base_url": "http://127.0.0.1:11434",
        }
    )
    llm = create_default_llm(cfg)
    assert isinstance(llm, ChatOllama)
    assert llm.model == "llama3.1:8b"
    assert llm.base_url == "http://127.0.0.1:11434"
