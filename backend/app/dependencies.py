"""
FastAPI dependency injection providers.

get_db          → yields an async SQLAlchemy session
get_redis       → yields a Redis connection (from app.state pool)
get_current_user → validates JWT, checks Redis session cache, falls back to DB
require_role    → RBAC guard factory
ensure_manager_access → verifies an employee belongs to the requesting manager
"""
from collections.abc import AsyncGenerator
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db_session
from app.models.enums import UserRole
from app.models.user import User
from app.services.security import decode_access_token

logger = structlog.get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# ---------------------------------------------------------------------------
# Session cache key helpers
# ---------------------------------------------------------------------------
_SESSION_PREFIX = "session:"
_BLACKLIST_PREFIX = "blacklist:"


def _session_key(token: str) -> str:
    return f"{_SESSION_PREFIX}{token}"


def _blacklist_key(token: str) -> str:
    return f"{_BLACKLIST_PREFIX}{token}"


# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


# ---------------------------------------------------------------------------
# Redis connection — taken from app.state pool set at startup
# ---------------------------------------------------------------------------
async def get_redis(request: Request) -> AsyncGenerator[Redis, None]:
    """
    Yields the shared Redis connection pool stored on app.state.
    Falls back to creating a one-shot connection if the pool is not
    yet initialised (e.g. during tests or early startup).
    """
    redis: Redis | None = getattr(request.app.state, "redis", None)
    if redis is not None:
        yield redis
        return
    # Fallback: create a transient connection (test / cold-start safety)
    conn = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield conn
    finally:
        await conn.aclose()


# ---------------------------------------------------------------------------
# Authentication — Redis-cached session
# ---------------------------------------------------------------------------
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    """
    Authenticates a request using the Bearer JWT.

    Cache strategy (Redis-first):
      1. Check Redis token blacklist → 401 if token was explicitly logged out.
      2. Check Redis session cache → return cached User JSON if present.
         This avoids a DB hit on every authenticated request.
      3. Verify JWT signature and decode claims.
      4. Fetch User from PostgreSQL (only on cache MISS).
      5. Write User JSON to Redis with TTL = session_ttl_seconds.

    On any Redis error the middleware fails open (DB fallback) so a Redis
    outage never blocks authenticated users.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Step 1 — token blacklist check (logout invalidation)
    try:
        is_blacklisted = await redis.exists(_blacklist_key(token))
        if is_blacklisted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except RedisError:
        logger.warning("redis_blacklist_check_failed", token_prefix=token[:12])

    # Step 2 — Redis session cache lookup
    try:
        cached = await redis.get(_session_key(token))
        if cached:
            from app.schemas.auth import UserRead
            user_data = UserRead.model_validate_json(cached)
            # Re-fetch a lightweight User-like object from data
            # We need the actual ORM User for downstream FK operations.
            user = await session.get(User, user_data.id)
            if user and user.is_active:
                logger.debug("auth_cache_hit", user_id=str(user.id))
                return user
            # Cache stale (user deactivated between writes) — fall through
    except RedisError:
        logger.warning("redis_session_cache_read_failed", token_prefix=token[:12])
    except Exception:
        pass  # Malformed cache value — fall through to DB

    # Step 3 — JWT decode
    try:
        payload = decode_access_token(token)
        user_id = UUID(str(payload.get("sub")))
    except (JWTError, TypeError, ValueError):
        raise credentials_error from None

    # Step 4 — DB fetch
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise credentials_error

    # Step 5 — populate Redis session cache
    try:
        from app.schemas.auth import UserRead
        user_json = UserRead.model_validate(user).model_dump_json()
        await redis.set(
            _session_key(token),
            user_json,
            ex=settings.session_ttl_seconds,
        )
        logger.debug("auth_cache_miss_written", user_id=str(user.id))
    except RedisError:
        logger.warning("redis_session_cache_write_failed", user_id=str(user.id))

    return user


# ---------------------------------------------------------------------------
# RBAC helpers
# ---------------------------------------------------------------------------
def require_role(*roles: UserRole):
    """
    Dependency factory that restricts an endpoint to specific roles.
    Usage: ``Depends(require_role(UserRole.MANAGER, UserRole.ADMIN))``
    """
    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return checker


async def ensure_manager_access(
    session: AsyncSession, manager: User, employee_id: UUID
) -> None:
    """
    Verifies that `employee_id` reports to `manager`.
    ADMIN role bypasses this check.
    """
    if manager.role == UserRole.ADMIN:
        return
    employee = await session.scalar(select(User).where(User.id == employee_id))
    if not employee or employee.manager_id != manager.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Employee is not in manager's team"
        )
