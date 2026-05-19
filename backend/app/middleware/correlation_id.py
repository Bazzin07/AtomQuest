"""
Correlation ID middleware — pure ASGI implementation.

Pure ASGI avoids Starlette's BaseHTTPMiddleware task-group pattern which
causes asyncpg "Future attached to different loop" errors in testing.

Behaviour is identical to the previous BaseHTTPMiddleware version:
  1. Reads X-Correlation-ID from the incoming request (upstream pass-through).
  2. Generates a fresh UUID v4 if none is present.
  3. Binds correlation_id into the structlog context.
  4. Echoes the ID back in the response header.
"""
import uuid

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send

CORRELATION_ID_HEADER = "X-Correlation-ID"
_HEADER_BYTES = CORRELATION_ID_HEADER.lower().encode()


class CorrelationIdMiddleware:
    """Pure ASGI correlation ID injector."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Extract existing correlation ID from request headers
        headers = dict(scope.get("headers", []))
        correlation_id = (
            headers.get(_HEADER_BYTES, b"").decode() or str(uuid.uuid4())
        )

        # Bind to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            method=scope.get("method", ""),
            path=scope.get("path", ""),
        )

        async def send_with_correlation(message):
            if message["type"] == "http.response.start":
                # Inject header into the response
                existing = list(message.get("headers", []))
                existing.append(
                    (_HEADER_BYTES, correlation_id.encode())
                )
                message = {**message, "headers": existing}
            await send(message)

        await self.app(scope, receive, send_with_correlation)
