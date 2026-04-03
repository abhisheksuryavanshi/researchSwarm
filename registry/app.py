from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from registry.config import settings
from registry.middleware.logging import RequestLoggingMiddleware, configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage the startup and shutdown lifecycle events for the FastAPI application.
    Initializes logging and HTTP client on startup, and gracefully closes them on shutdown.
    """
    configure_logging(settings.log_level, settings.log_directory)
    logger = structlog.get_logger()

    app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0))
    await logger.ainfo("http_client_initialized")

    app.state.conversation_coordinator = None
    app.state._conversation_mysql = None
    app.state._conversation_redis = None
    try:
        from agents.config import AgentConfig
        from agents.graph import (
            build_research_graph,
            build_synthesizer_only_graph,
            default_graph_context,
        )
        from conversation.config import ConversationSettings
        from conversation.coordinator import ConversationCoordinator
        from conversation.intent import IntentClassifier
        from conversation.persistence.mysql_store import MysqlSessionStore
        from conversation.persistence.redis_store import RedisSessionStore

        cs = ConversationSettings()
        mysql = MysqlSessionStore(cs.database_url)
        redis_store = RedisSessionStore(
            cs.redis_url,
            lock_ttl_seconds=cs.turn_lock_ttl_seconds,
            doc_ttl_seconds=cs.redis_working_set_ttl_seconds,
        )
        await redis_store.connect()
        agent_cfg = AgentConfig()
        ctx = default_graph_context(agent_cfg)
        full = build_research_graph()
        light = build_synthesizer_only_graph()
        classifier = IntentClassifier(
            ctx["llm"],
            confidence_threshold=cs.intent_confidence_threshold,
        )
        app.state.conversation_coordinator = ConversationCoordinator(
            cs,
            mysql,
            redis_store,
            ctx,
            full_graph_compiled=full,
            light_graph_compiled=light,
            intent_classifier=classifier,
        )
        app.state._conversation_mysql = mysql
        app.state._conversation_redis = redis_store
        await logger.ainfo("conversation_coordinator_initialized")
    except Exception as exc:
        await logger.awarning("conversation_coordinator_skipped", error=str(exc))

    yield

    if getattr(app.state, "_conversation_redis", None) is not None:
        await app.state._conversation_redis.close()
    if getattr(app.state, "_conversation_mysql", None) is not None:
        await app.state._conversation_mysql.dispose()
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

    _cors_origins = [
        o.strip() for o in settings.cors_origins.split(",") if o.strip()
    ]
    # CORSMiddleware last so it wraps all responses (FastAPI / Starlette convention).
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Trace-ID",
            "X-Session-ID",
            "Idempotency-Key",
        ],
    )

    from conversation.api.routes import router as conversation_router
    from registry.routers import bind, health, register, search, stats, usage

    application.include_router(conversation_router, tags=["sessions"])
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
