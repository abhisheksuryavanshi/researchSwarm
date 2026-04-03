from __future__ import annotations

import contextvars
import hashlib
import json
import os
import re
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Literal, Optional

import structlog
from langchain_core.callbacks import BaseCallbackHandler

if TYPE_CHECKING:
    from agents.state import ResearchState

# Future: plug redaction here (PII, secrets) before truncation.
_TRACE_REDACT_HOOK: Any = None

_trace_excerpt_max: contextvars.ContextVar[int] = contextvars.ContextVar(
    "_trace_excerpt_max",
    default=2048,
)
_langfuse_enabled_ctx: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_langfuse_enabled_ctx",
    default=False,
)


def bind_trace_excerpt_max(max_chars: int) -> contextvars.Token[int]:
    return _trace_excerpt_max.set(max_chars)


def reset_trace_excerpt_max(token: contextvars.Token[int]) -> None:
    _trace_excerpt_max.reset(token)


def current_trace_excerpt_max() -> int:
    return _trace_excerpt_max.get()


def bind_langfuse_run_enabled(enabled: bool) -> contextvars.Token[bool]:
    return _langfuse_enabled_ctx.set(enabled)


def reset_langfuse_run_enabled(token: contextvars.Token[bool]) -> None:
    _langfuse_enabled_ctx.reset(token)


def is_langfuse_run_enabled() -> bool:
    return _langfuse_enabled_ctx.get()


def trace_id_for_langfuse(trace_id: str) -> str:
    """Langfuse trace ids must be 32 lowercase hex chars; normalize standard UUID strings."""
    s = (trace_id or "").replace("-", "").lower()
    if len(s) == 32 and re.fullmatch(r"[0-9a-f]{32}", s):
        return s
    return hashlib.sha256((trace_id or "").encode()).hexdigest()[:32]


def truncate_for_trace(text: Optional[str], max_chars: int) -> str:
    if text is None:
        return ""
    if _TRACE_REDACT_HOOK is not None:
        text = _TRACE_REDACT_HOOK(text)
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"...[truncated,{len(text)}chars]"


def get_tracer(
    agent_config: Any,
    *,
    trace_id: str,
    max_chars: Optional[int] = None,
) -> Optional[BaseCallbackHandler]:
    if not getattr(agent_config, "langfuse_enabled", False):
        return None
    lim = max_chars
    if lim is None:
        lim = int(getattr(agent_config, "trace_excerpt_max_chars", 2048))
    try:
        from langfuse.langchain.CallbackHandler import LangchainCallbackHandler
        from langfuse.types import TraceContext
    except ModuleNotFoundError:
        return None
    from langchain_core.outputs import ChatGeneration

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

    class _TruncatingLangfuseHandler(LangchainCallbackHandler):
        def __init__(self, *, excerpt_max: int, **kw: Any) -> None:
            super().__init__(**kw)
            self._excerpt_max = excerpt_max

        def on_llm_end(
            self,
            response: Any,
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> Any:
            response = deepcopy(response)
            for gen_list in response.generations or []:
                for g in gen_list:
                    if isinstance(g, ChatGeneration) and g.message is not None:
                        c = getattr(g.message, "content", None)
                        if isinstance(c, str):
                            g.message.content = truncate_for_trace(c, self._excerpt_max)
            return super().on_llm_end(
                response,
                run_id=run_id,
                parent_run_id=parent_run_id,
                **kwargs,
            )

    lf_trace_id = trace_id_for_langfuse(trace_id)
    tc = TraceContext(trace_id=lf_trace_id)
    try:
        return _TruncatingLangfuseHandler(excerpt_max=lim, trace_context=tc)
    except Exception:  # pragma: no cover — Langfuse misconfiguration
        return None


def langfuse_run_metadata_dict(
    *,
    session_id: str,
    trace_id: str,
    client_session_id: Optional[str] = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "langfuse_session_id": session_id,
        "trace_id": trace_id,
    }
    if client_session_id:
        meta["client_session_id"] = client_session_id
    return meta


def llm_invoke_config(
    state: ResearchState,
    callbacks: list[Any],
) -> Optional[dict[str, Any]]:
    if not callbacks:
        return None
    return {
        "callbacks": callbacks,
        "metadata": langfuse_run_metadata_dict(
            session_id=state["session_id"],
            trace_id=state["trace_id"],
            client_session_id=state.get("client_session_id"),
        ),
    }


def emit_critic_route_span(
    state: ResearchState,
    destination: Literal["researcher", "synthesizer"],
) -> None:
    if not is_langfuse_run_enabled():
        return
    try:
        from langfuse import get_client
        from langfuse.types import TraceContext
    except ModuleNotFoundError:
        return
    client = get_client()
    if client is None:
        return
    max_c = current_trace_excerpt_max()
    meta: dict[str, Any] = {
        "agent_id": "critic",
        "session_id": state["session_id"],
        "trace_id": state["trace_id"],
    }
    csid = state.get("client_session_id")
    if csid:
        meta["client_session_id"] = csid
    try:
        summary = {
            "critique_pass": state.get("critique_pass"),
            "iteration_count": state.get("iteration_count"),
            "max_iterations": state.get("max_iterations"),
            "destination": destination,
        }
        span = client.start_observation(
            trace_context=TraceContext(trace_id=trace_id_for_langfuse(state["trace_id"])),
            name="route_after_critic",
            as_type="span",
            input=truncate_for_trace(json.dumps(summary, default=str), max_c),
            output={"destination": destination},
            metadata=meta,
        )
        span.end()
    except Exception:  # FR-008 — best-effort only
        pass


def get_logger(
    trace_id: str,
    session_id: str,
    agent_id: str,
    client_session_id: Optional[str] = None,
) -> structlog.BoundLogger:
    fields: dict[str, Any] = {
        "trace_id": trace_id,
        "session_id": session_id,
        "agent_id": agent_id,
    }
    if client_session_id:
        fields["client_session_id"] = client_session_id
    return structlog.get_logger().bind(**fields)


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
