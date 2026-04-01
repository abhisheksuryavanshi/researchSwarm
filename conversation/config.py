"""Conversation layer settings.

Environment variables (see also quickstart):

- ``CONVERSATION_REDIS_URL``: Redis URL for locks and working-set cache.
- ``CONVERSATION_DATABASE_URL``: Async MySQL DSN (registry-aligned), e.g.
  ``mysql+aiomysql://user:pass@host:3306/dbname``.
- ``CONVERSATION_LLM_MODEL``: Model id for intent classification (optional).
- ``CONVERSATION_INTENT_CONFIDENCE_THRESHOLD``: Below this, FR-015 clarification path.
- ``CONVERSATION_TURN_LOCK_TTL_SECONDS``: Redis lock TTL for per-session FIFO.
- ``CONVERSATION_REDIS_WORKING_SET_TTL_SECONDS``: TTL for cached session doc keys.
- ``CONVERSATION_INTENT_CONFIDENCE_THRESHOLD``: 0.0–1.0; below this, clarification path (FR-015).

Run ``alembic upgrade head`` on the registry MySQL URL; revision ``002_conversation_sessions``
adds ``session``, ``session_turn``, and ``research_snapshot`` tables.
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConversationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CONVERSATION_",
        extra="ignore",
    )

    redis_url: str = Field(default="redis://localhost:6379/0")
    database_url: str = Field(
        default="mysql+aiomysql://root:root@localhost:3306/researchswarm",
    )
    llm_model: str = Field(default="gemini-2.0-flash")
    intent_confidence_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    turn_lock_ttl_seconds: int = Field(default=120, ge=5, le=3600)
    redis_working_set_ttl_seconds: int = Field(default=86400, ge=60, le=86400 * 30)
    google_api_key: Optional[str] = Field(default=None)
