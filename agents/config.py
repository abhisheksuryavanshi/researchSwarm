from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "groq"
    llm_model: str = "llama-3.1-8b-instant"
    llm_temperature: float = 0.1
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 3
    llm_retries_enabled: bool = Field(
        default=False,
        description=(
            "Global switch for LangChain/Google client HTTP retries on failed LLM calls. "
            "When False, max_retries is forced to 0 (one API attempt per node call). "
            "Enable when quotas are stable and transient errors should be retried."
        ),
    )
    max_iterations: int = 3
    graph_timeout_seconds: int = 60
    registry_base_url: str = "http://localhost:8000"
    tool_invocation_timeout_seconds: int = 30
    max_tool_fallback_attempts: int = 3
    google_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    langfuse_enabled: bool = True
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    token_usage_warn_threshold: int = Field(
        default=100_000,
        description="Summed token estimate threshold for warning logs.",
    )
    trace_excerpt_max_chars: int = Field(
        default=2048,
        description="Max characters for excerpts sent to external traces (e.g. Langfuse).",
    )
    wikipedia_enrich_with_parse: bool = Field(
        default=True,
        description=(
            "After a successful wikipedia-lookup-v1 call, fetch full article HTML via "
            "action=parse, strip to plain text, and attach as enriched_article_plaintext."
        ),
    )
    wikipedia_max_article_chars: int = Field(
        default=100_000,
        ge=0,
        description="Max plain-text characters to keep from parse enrichment (0 = no limit).",
    )

    @field_validator("llm_max_retries")
    @classmethod
    def llm_max_retries_bounds(cls, v: int) -> int:
        if not isinstance(v, int) or v < 0:
            raise ValueError("llm_max_retries must be >= 0")
        return v

    @field_validator("max_iterations")
    @classmethod
    def max_iterations_bounds(cls, v: int) -> int:
        if not isinstance(v, int) or not (1 <= v <= 5):
            raise ValueError("max_iterations must be between 1 and 5 inclusive")
        return v

    @field_validator("tool_invocation_timeout_seconds")
    @classmethod
    def tool_timeout_bounds(cls, v: int) -> int:
        if not isinstance(v, int) or v < 1:
            raise ValueError("tool_invocation_timeout_seconds must be >= 1")
        return v

    @field_validator("max_tool_fallback_attempts")
    @classmethod
    def max_fallback_bounds(cls, v: int) -> int:
        if not isinstance(v, int) or not (1 <= v <= 10):
            raise ValueError("max_tool_fallback_attempts must be between 1 and 10 inclusive")
        return v
