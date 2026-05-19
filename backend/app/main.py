"""
AtomQuest FastAPI application entry point.

Startup sequence:
  1. Optionally auto-create DB tables (dev/test only; prod uses Alembic).
  2. Create a shared Redis connection pool on app.state so middleware and
     dependencies share the same pool without creating per-request connections.
  3. Expose Prometheus /metrics endpoint.

Middleware stack (outermost → innermost):
  CORSMiddleware           → added via add_middleware (FastAPI/Starlette pattern)
  CorrelationIdMiddleware  → injects X-Correlation-ID on every request
  RequestLoggingMiddleware → structured JSON request/response logging
  RateLimiterMiddleware    → Redis sliding-window, role-aware

CORS:
  Origins are driven by the ``ALLOWED_ORIGINS`` env variable so prod can
  lock down to specific domains without code changes.

Global error handler:
  All unhandled 500 exceptions are caught and returned as a consistent
  JSON error body that includes the correlation ID for tracing.
"""
import traceback
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from redis.asyncio import Redis

from app.config import settings
from app.database import init_db
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.routers import (
    achievements,
    admin,
    analytics,
    audit,
    auth,
    checkins,
    escalations,
    goals,
    health,
    reports,
    system,
    users,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    # Auto-create tables (dev / first-run only; production should use Alembic)
    if settings.auto_create_tables:
        await init_db()
        logger.info("database_tables_ready")

    # Shared Redis pool — stored on app.state so all middleware and DI can
    # reference the same pool instead of creating per-request connections.
    app.state.redis = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        max_connections=20,
    )
    try:
        await app.state.redis.ping()
        logger.info("redis_connection_pool_ready", url=settings.redis_url)
    except Exception as exc:
        # Log warning but don't abort startup — system degrades gracefully
        logger.warning("redis_connection_failed_at_startup", error=str(exc))

    logger.info(
        "atomquest_api_started",
        environment=settings.environment,
        version="1.0.0",
        notifications_email=settings.email_enabled,
        notifications_teams=settings.teams_enabled,
    )

    # ── Production hardening checks ───────────────────────────────────────────
    if settings.environment == "production":
        if settings.secret_key == "change-me-before-deploying":
            logger.critical(
                "INSECURE_SECRET_KEY",
                detail="SECRET_KEY is the default placeholder. Set a strong random key before production use.",
            )
        if settings.allowed_origins == "*":
            logger.warning(
                "CORS_TOO_PERMISSIVE",
                detail="ALLOWED_ORIGINS=* is not suitable for production. Set specific frontend origins.",
            )
        if not settings.email_enabled:
            logger.warning(
                "NOTIFICATIONS_DISABLED",
                detail="Email notifications are off. Set NOTIFICATIONS_ENABLED=true with SMTP credentials to enable.",
            )

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    # Drain Redis pool — allows in-flight async ops to complete
    if hasattr(app.state, "redis") and app.state.redis is not None:
        try:
            await app.state.redis.aclose()
            logger.info("redis_connection_pool_closed")
        except Exception as exc:
            logger.warning("redis_shutdown_error", error=str(exc))
    logger.info("atomquest_api_shutdown_complete")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "AtomQuest Goal Setting & Tracking API — production-grade "
        "enterprise performance management backend."
    ),
    lifespan=lifespan,
    # Disable interactive docs in production to reduce attack surface
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None if settings.environment == "production" else "/redoc",
    openapi_url=None if settings.environment == "production" else "/openapi.json",
)


# ── Global Exception Handler ──────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unhandled exceptions.

    Returns a consistent 500 error body that includes the correlation ID
    so incidents can be correlated with structured logs.
    Never leaks internal stack traces to clients in production.
    """
    correlation_id = request.headers.get("X-Correlation-ID", "unknown")
    logger.error(
        "unhandled_exception",
        path=str(request.url),
        method=request.method,
        correlation_id=correlation_id,
        error=str(exc),
        traceback=traceback.format_exc(),
    )
    body = {
        "detail": "An internal server error occurred.",
        "correlation_id": correlation_id,
    }
    if settings.environment != "production":
        body["debug"] = str(exc)
    return JSONResponse(status_code=500, content=body)


# ── Middleware registration ────────────────────────────────────────────────
# Starlette executes middleware in LIFO order relative to add_middleware calls.
# We want execution order: CORS → CorrelationId → Logging → RateLimiter → Handler
# So register in reverse order here.

if settings.rate_limit_enabled:
    app.add_middleware(RateLimiterMiddleware, main_app=app)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CorrelationIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)

# ── Prometheus Metrics ────────────────────────────────────────────────────
# Exposes /metrics endpoint with request latency, request counts,
# exception rates, and custom labels (method, handler, status_code).
Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    excluded_handlers=["/metrics", "/health", "/health/ready"],
).instrument(app).expose(app, include_in_schema=False, tags=["observability"])

# ── Routers ───────────────────────────────────────────────────────────────
app.include_router(health.router,       prefix="/api/v1")
app.include_router(auth.router,         prefix="/api/v1")
app.include_router(goals.router,        prefix="/api/v1")
app.include_router(achievements.router, prefix="/api/v1")
app.include_router(checkins.router,     prefix="/api/v1")
app.include_router(admin.router,        prefix="/api/v1")
app.include_router(reports.router,      prefix="/api/v1")
app.include_router(audit.router,        prefix="/api/v1")
app.include_router(analytics.router,    prefix="/api/v1")
app.include_router(escalations.router,  prefix="/api/v1")
app.include_router(system.router,       prefix="/api/v1")
app.include_router(users.router,        prefix="/api/v1")
