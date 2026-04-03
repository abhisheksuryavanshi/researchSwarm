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

_log = structlog.get_logger("langfuse_tracing")

_TRACE_REDACT_HOOK: Any = None

_trace_excerpt_max: contextvars.ContextVar[int] = contextvars.ContextVar(
    "_trace_excerpt_max",
    default=2048,
)
_langfuse_enabled_ctx: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_langfuse_enabled_ctx",
    default=False,
)
_active_handlers: contextvars.ContextVar[list[Any]] = contextvars.ContextVar(
    "_active_handlers",
    default=[],
)
_progress_queue: contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar(
    "_progress_queue",
    default=None,
)

_langfuse_client: Any = None
_langfuse_config: dict[str, Any] = {}


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
    """Langfuse trace ids must be valid UUID strings; normalize."""
    s = (trace_id or "").replace("-", "").lower()
    if len(s) == 32 and re.fullmatch(r"[0-9a-f]{32}", s):
        return s
    return hashlib.sha256((trace_id or "").encode()).hexdigest()[:32]


def lf_trace_context(trace_id: str) -> dict[str, str]:
    """Return a dict with normalized trace_id for Langfuse."""
    return {"trace_id": trace_id_for_langfuse(trace_id)}


def initialize_langfuse(agent_config: Any) -> None:
    """Eagerly create the module-level Langfuse client and validate connectivity.

    Call this once at application startup (before any requests) so that
    mis-configuration is detected early and logged loudly.
    """
    global _langfuse_client, _langfuse_config

    if not getattr(agent_config, "langfuse_enabled", False):
        _log.info("langfuse_disabled", reason="langfuse_enabled=False in config")
        return

    public_key = getattr(agent_config, "langfuse_public_key", None) or os.environ.get(
        "LANGFUSE_PUBLIC_KEY"
    )
    secret_key = getattr(agent_config, "langfuse_secret_key", None) or os.environ.get(
        "LANGFUSE_SECRET_KEY"
    )
    host = getattr(agent_config, "langfuse_host", None) or os.environ.get(
        "LANGFUSE_HOST", "http://localhost:3000"
    )

    if not public_key or not secret_key:
        _log.error(
            "langfuse_init_failed",
            reason="LANGFUSE_PUBLIC_KEY and/or LANGFUSE_SECRET_KEY not set",
        )
        return

    _langfuse_config = {
        "public_key": public_key,
        "secret_key": secret_key,
        "host": host,
    }

    try:
        from langfuse import Langfuse
    except ModuleNotFoundError:
        _log.error("langfuse_init_failed", reason="langfuse package not installed")
        return

    try:
        client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        ok = client.auth_check()
        if ok:
            _langfuse_client = client
            _log.info(
                "langfuse_initialized",
                host=host,
                public_key=public_key[:12] + "...",
                auth_check="passed",
            )
        else:
            _log.error(
                "langfuse_init_failed",
                host=host,
                public_key=public_key[:12] + "...",
                auth_check="failed — check keys and server connectivity",
            )
    except Exception as exc:
        _log.error(
            "langfuse_init_failed",
            host=host,
            error=str(exc),
            exc_info=True,
        )


def get_langfuse_client() -> Any:
    """Return the module-level Langfuse client (may be None if not initialized)."""
    return _langfuse_client


def flush_langfuse() -> None:
    """Flush all active Langfuse handler clients + the module-level client."""
    flushed = 0
    for handler in _active_handlers.get([]):
        lf = getattr(handler, "langfuse", None)
        if lf is not None:
            try:
                lf.flush()
                flushed += 1
            except Exception as exc:
                _log.error("langfuse_handler_flush_failed", error=str(exc), exc_info=True)
    _active_handlers.set([])

    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
            flushed += 1
        except Exception as exc:
            _log.error("langfuse_client_flush_failed", error=str(exc), exc_info=True)

    if flushed > 0:
        _log.debug("langfuse_flushed", clients=flushed)
    elif is_langfuse_run_enabled():
        _log.warning("langfuse_flush_noop", reason="no clients to flush")


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
        from langfuse.callback import CallbackHandler as LangfuseCallbackHandler
    except ModuleNotFoundError:
        _log.error("langfuse_import_failed", module="langfuse.callback")
        return None
    from langchain_core.outputs import ChatGeneration

    public_key = _langfuse_config.get("public_key") or getattr(
        agent_config, "langfuse_public_key", None
    ) or os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = _langfuse_config.get("secret_key") or getattr(
        agent_config, "langfuse_secret_key", None
    ) or os.environ.get("LANGFUSE_SECRET_KEY")
    host = _langfuse_config.get("host") or getattr(
        agent_config, "langfuse_host", None
    ) or os.environ.get("LANGFUSE_HOST")

    if not public_key or not secret_key:
        _log.error(
            "langfuse_tracer_skipped",
            reason="missing public_key or secret_key",
        )
        return None

    class _TruncatingHandler(LangfuseCallbackHandler):
        def __init__(self, *, excerpt_max: int, **kwargs: Any) -> None:
            super().__init__(**kwargs)
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

    try:
        handler = _TruncatingHandler(
            excerpt_max=lim,
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            trace_name="research-graph",
        )
        handlers = _active_handlers.get([])
        handlers.append(handler)
        _active_handlers.set(handlers)
        _log.debug("langfuse_tracer_created", trace_id=trace_id)
        return handler
    except Exception as exc:
        _log.error(
            "langfuse_tracer_creation_failed",
            error=str(exc),
            exc_info=True,
        )
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
    client = _langfuse_client
    if client is None:
        _log.warning("langfuse_critic_span_skipped", reason="no langfuse client")
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
        norm_tid = trace_id_for_langfuse(state["trace_id"])
        trace_ref = client.trace(id=norm_tid)
        span = trace_ref.span(
            name="route_after_critic",
            input=truncate_for_trace(json.dumps(summary, default=str), max_c),
            output={"destination": destination},
            metadata=meta,
        )
        span.end()
    except Exception as exc:
        _log.error(
            "langfuse_critic_span_failed",
            error=str(exc),
            exc_info=True,
        )


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


def bind_progress_queue(queue: Any) -> contextvars.Token[Optional[Any]]:
    return _progress_queue.set(queue)


def reset_progress_queue(token: contextvars.Token[Optional[Any]]) -> None:
    _progress_queue.reset(token)


async def emit_progress(stage: str) -> None:
    """Push a progress event to the bound queue (no-op if no queue is bound)."""
    q = _progress_queue.get(None)
    if q is not None:
        await q.put({"stage": stage})
