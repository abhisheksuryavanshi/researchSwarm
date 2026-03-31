from __future__ import annotations

import os
from typing import Any

import structlog
from langchain_core.callbacks import BaseCallbackHandler


def get_tracer(agent_config: Any) -> BaseCallbackHandler | None:
    if not getattr(agent_config, "langfuse_enabled", False):
        return None
    try:
        from langfuse.langchain import CallbackHandler
    except ModuleNotFoundError:
        return None
    public_key = getattr(agent_config, "langfuse_public_key", None) or os.environ.get(
        "LANGFUSE_PUBLIC_KEY"
    )
    secret = getattr(agent_config, "langfuse_secret_key", None) or os.environ.get(
        "LANGFUSE_SECRET_KEY"
    )
    host = getattr(agent_config, "langfuse_host", None) or os.environ.get("LANGFUSE_HOST")
    if public_key and secret:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", public_key)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", secret)
    if host:
        os.environ.setdefault("LANGFUSE_HOST", host)
    try:
        return CallbackHandler()
    except Exception:  # pragma: no cover — Langfuse misconfiguration
        return None


def get_logger(trace_id: str, session_id: str, agent_id: str) -> structlog.BoundLogger:
    return structlog.get_logger().bind(
        trace_id=trace_id,
        session_id=session_id,
        agent_id=agent_id,
    )


def tokens_from_raw_message(raw: Any) -> int:
    if raw is None:
        return 0
    meta = getattr(raw, "usage_metadata", None) or {}
    total = meta.get("total_tokens")
    if isinstance(total, int) and total > 0:
        return total
    inp = meta.get("input_tokens") or 0
    out = meta.get("output_tokens") or 0
    if inp or out:
        return int(inp) + int(out)
    return 100
