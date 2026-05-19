"""
Structured request/response logging middleware — pure ASGI implementation.

Pure ASGI avoids Starlette's BaseHTTPMiddleware task-group pattern which
causes asyncpg "Future attached to different loop" errors in testing.

Log fields emitted:
  - event: "request_started" / "request_finished" / "request_unhandled_exception"
  - method, path, status_code
  - duration_ms  (wall-clock milliseconds for the full handler)
  - correlation_id (from structlog context, bound by CorrelationIdMiddleware)

Health-check endpoints are excluded to avoid log noise.
"""
import time

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send

logger = structlog.get_logger(__name__)

_SILENT_PATHS = frozenset({"/api/v1/health", "/api/v1/health/ready", "/metrics"})


class RequestLoggingMiddleware:
    """Pure ASGI structured request/response logger."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _SILENT_PATHS:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        query = scope.get("query_string", b"").decode() or None

        logger.info("request_started", method=method, path=path, query=query)

        start = time.perf_counter()
        status_code = 500

        async def send_capturing_status(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_capturing_status)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "request_unhandled_exception",
                method=method,
                path=path,
                duration_ms=duration_ms,
                exc_info=True,
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log_fn = logger.warning if status_code >= 400 else logger.info
        log_fn(
            "request_finished",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
