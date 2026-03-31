from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from registry.config import settings
from registry.middleware.logging import RequestLoggingMiddleware, configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage the startup and shutdown lifecycle events for the FastAPI application.
    Initializes logging and HTTP client on startup, and gracefully closes them on shutdown.
    """
    configure_logging(settings.log_level)
    logger = structlog.get_logger()

    app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0))
    await logger.ainfo("http_client_initialized")

    yield

    await app.state.http_client.aclose()
    await logger.ainfo("shutdown_complete")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application instance for the Tool Registry Service.
    Registers middleware, routers, and global exception handlers.
    """
    application = FastAPI(
        title="Tool Registry Service",
        description="Central tool catalog for the Research Swarm system",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(RequestLoggingMiddleware)

    from registry.routers import bind, health, register, search, stats, usage

    application.include_router(register.router, tags=["registration"])
    application.include_router(search.router, tags=["search"])
    application.include_router(bind.router, tags=["binding"])
    application.include_router(usage.router, tags=["usage"])
    application.include_router(health.router, tags=["health"])
    application.include_router(stats.router, tags=["stats"])

    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """
        Handle all uncaught exceptions globally gracefully.
        Logs the error details and returns a standard 500 Internal Server Error response.
        """
        logger = structlog.get_logger()
        await logger.aerror("unhandled_exception", error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return application


app = create_app()
