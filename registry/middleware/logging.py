from __future__ import annotations

import logging
import sys
import time
import uuid
from pathlib import Path
from typing import TextIO

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class _TeeTextIO:
    """Write the same bytes to stdout and a log file (line-oriented structlog output)."""

    __slots__ = ("_streams",)

    def __init__(self, *streams: TextIO) -> None:
        self._streams = streams

    def write(self, s: str) -> int:
        for stream in self._streams:
            stream.write(s)
        return len(s)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def _log_level_int(name: str) -> int:
    """Map log level string to logging int for structlog filtering."""
    key = (name or "INFO").upper()
    level = getattr(logging, key, None)
    return level if isinstance(level, int) else logging.INFO


def configure_logging(log_level: str = "INFO", log_directory: str = "logs") -> None:
    """
    Configure structured JSON logging for the application.
    Writes JSON lines to ``{log_directory}/backend.jsonl`` and mirrors them to stdout.
    """
    log_dir = Path(log_directory)
    log_dir.mkdir(parents=True, exist_ok=True)
    backend_log = log_dir / "backend.jsonl"
    log_file = open(backend_log, "a", encoding="utf-8", buffering=1)
    out = _TeeTextIO(sys.stdout, log_file)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(_log_level_int(log_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=out),
        cache_logger_on_first_use=True,
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that uniquely traces and systematically logs every HTTP request.
    Records duration, status codes, and path details.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Intercept the incoming request to inject trace identifiers and log its lifecycle.
        Assures each API call is accurately measured and monitored.
        """
        trace_id = request.headers.get("x-trace-id", str(uuid.uuid4()))
        raw_client_session = request.headers.get("x-session-id")
        client_session_id = (
            raw_client_session.strip()
            if isinstance(raw_client_session, str) and raw_client_session.strip()
            else None
        )

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            client_session_id=client_session_id,
        )

        logger = structlog.get_logger()
        start_time = time.perf_counter()

        await logger.ainfo(
            "request_started",
            method=request.method,
            path=str(request.url.path),
            authorization_header_present=bool(request.headers.get("authorization")),
        )

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        await logger.ainfo(
            "request_completed",
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            elapsed_ms=round(elapsed_ms, 2),
        )

        response.headers["X-Trace-ID"] = trace_id
        return response
