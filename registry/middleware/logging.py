import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


def configure_logging(log_level: str = "INFO") -> None:
    """
    Configure structured JSON logging for the application.
    Sets up processors for timestamps, log levels, and exceptions.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.get_level_from_name(log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
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
        session_id = request.headers.get("x-session-id", "")

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            session_id=session_id,
        )

        logger = structlog.get_logger()
        start_time = time.perf_counter()

        await logger.ainfo(
            "request_started",
            method=request.method,
            path=str(request.url.path),
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
