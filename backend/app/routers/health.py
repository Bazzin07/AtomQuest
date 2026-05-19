"""
Health check endpoints.

GET /health       — Liveness probe: fast ping, no external dependencies.
GET /health/ready — Readiness probe: verifies DB and Redis are reachable.
                    Used by Docker healthchecks and load balancer probes.
"""
from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_redis

router = APIRouter(tags=["health"])

_API_VERSION = "1.0.0"


@router.get("/health")
async def health() -> dict:
    """Liveness probe — no external dependencies, always fast."""
    return {"status": "ok", "version": _API_VERSION}


@router.get("/health/ready")
async def ready(
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict:
    """
    Readiness probe — validates DB and Redis connectivity.

    Returns status for each dependency individually so orchestrators
    can identify which subsystem is degraded.
    """
    db_status = "ok"
    redis_status = "ok"
    overall = "ready"

    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"
        overall = "degraded"

    try:
        await redis.ping()
    except Exception as exc:
        redis_status = f"error: {exc}"
        overall = "degraded"

    return {
        "status": overall,
        "version": _API_VERSION,
        "dependencies": {
            "postgres": db_status,
            "redis": redis_status,
        },
    }
