"""
Redis-backed sliding window rate limiter — pure ASGI implementation.

Pure ASGI avoids Starlette's BaseHTTPMiddleware task-group pattern which
causes asyncpg "Future attached to different loop" errors in testing.

Uses a sorted set per (role, IP) key in Redis. Each request adds its
timestamp as both member and score; old entries outside the window are
pruned atomically via a pipeline. This is an exact sliding window —
no fixed-bucket rounding.

Role-based limits (requests / window_seconds):
  EMPLOYEE  → 100 / 60 s
  MANAGER   → 200 / 60 s
  ADMIN     → 500 / 60 s
  anonymous → 30  / 60 s  (login endpoint, health check, etc.)

When Redis is unavailable the middleware PASSES the request through so a
cache failure never brings the API down (fail-open strategy).
"""
import base64
import json
import time
from typing import Tuple

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.types import ASGIApp, Receive, Scope, Send

logger = structlog.get_logger(__name__)

# (limit, window_seconds)
_ROLE_LIMITS: dict[str, Tuple[int, int]] = {
    "EMPLOYEE":  (100, 60),
    "MANAGER":   (200, 60),
    "ADMIN":     (500, 60),
    "anonymous": (30,  60),
}

# Paths that bypass rate limiting entirely
_BYPASS_PATHS = frozenset({
    "/api/v1/health", "/api/v1/health/ready",
    "/docs", "/openapi.json", "/metrics",
})


class RateLimiterMiddleware:
    """
    Sliding window rate limiter. Requires the Redis connection pool to be
    available as ``app.state.redis``.
    """

    def __init__(self, app: ASGIApp, main_app=None) -> None:
        self.app = app
        self._main_app = main_app  # Reference to the FastAPI app for state access

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _BYPASS_PATHS:
            await self.app(scope, receive, send)
            return

        # Get Redis — prefer injected main_app, fall back to scope["app"]
        redis = None
        if self._main_app is not None:
            redis = getattr(getattr(self._main_app, "state", None), "redis", None)
        if redis is None:
            app_ref = scope.get("app")
            if app_ref is not None:
                redis = getattr(getattr(app_ref, "state", None), "redis", None)

        if redis is None:
            # Redis not yet initialised or unavailable — pass through (fail open)
            await self.app(scope, receive, send)
            return

        role = _extract_role_from_headers(scope.get("headers", []))
        limit, window = _ROLE_LIMITS.get(role, _ROLE_LIMITS["anonymous"])
        client_ip = _get_client_ip(scope)
        rate_key = f"rate:{role}:{client_ip}"

        try:
            allowed = await _check_sliding_window(redis, rate_key, limit, window)
        except RedisError:
            logger.warning("rate_limiter_redis_error", path=path)
            await self.app(scope, receive, send)
            return

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                role=role,
                client_ip=client_ip,
                path=path,
            )
            body = json.dumps({"detail": "Too many requests. Please slow down."}).encode()
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"retry-after", str(window).encode()),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)


async def _check_sliding_window(redis: Redis, key: str, limit: int, window: int) -> bool:
    """
    Atomically:
      1. Remove all entries older than `window` seconds.
      2. Add current timestamp.
      3. Count remaining entries.
      4. Set TTL to expire the key automatically.
    Returns True if the request is within the limit.
    """
    now = time.time()
    cutoff = now - window
    member = str(now)

    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, cutoff)
    pipe.zadd(key, {member: now})
    pipe.zcard(key)
    pipe.expire(key, window)
    results = await pipe.execute()
    count: int = results[2]
    return count <= limit


def _get_client_ip(scope: Scope) -> str:
    # Check X-Forwarded-For first (proxy/LB)
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-for":
            return value.decode().split(",")[0].strip()
    client = scope.get("client")
    if client:
        return client[0]
    return "unknown"


def _extract_role_from_headers(headers: list) -> str:
    """
    Fast, no-DB role extraction from Bearer token payload.
    JWT is: header.payload.sig — payload is base64url-encoded JSON.
    Reads `role` claim without verifying signature (only for rate-limit
    bucketing — actual auth verification happens in get_current_user).
    """
    for name, value in headers:
        if name == b"authorization":
            auth = value.decode()
            if not auth.startswith("Bearer "):
                return "anonymous"
            token = auth[7:]
            try:
                parts = token.split(".")
                if len(parts) != 3:
                    return "anonymous"
                payload_b64 = parts[1] + "=="
                payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                return payload.get("role", "anonymous")
            except Exception:
                return "anonymous"
    return "anonymous"
