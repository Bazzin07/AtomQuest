"""
Authentication router.

Endpoints:
  POST /auth/login    → email+password → JWT access token
  GET  /auth/me       → current user info (requires valid JWT)
  POST /auth/refresh  → re-issue a fresh JWT for the same user
  POST /auth/logout   → blacklist the current token in Redis (immediate revocation)

Token blacklist strategy:
  On logout the raw Bearer token is added to Redis with a TTL equal to the
  JWT's remaining lifetime. The ``get_current_user`` dependency checks this
  blacklist on every authenticated request. Entries expire automatically so
  the blacklist never grows unbounded.

  On /refresh, the old token is also blacklisted (token rotation), preventing
  replay of revoked tokens.
"""
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_user, get_db, get_redis
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.services.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_BLACKLIST_PREFIX = "blacklist:"
_SESSION_PREFIX = "session:"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_bearer(request: Request) -> str:
    """Extract raw JWT from Authorization header. Returns '' if absent."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return ""


def _remaining_ttl(token: str) -> int:
    """Return remaining seconds until JWT expiry, floored at 1."""
    try:
        claims = decode_access_token(token)
        exp = claims.get("exp")
        if exp:
            remaining = int(exp - datetime.now(UTC).timestamp())
            return max(remaining, 1)
    except Exception:
        pass
    return settings.token_blacklist_ttl_seconds


async def _blacklist_token(redis: Redis, token: str) -> None:
    """Add token to Redis blacklist and purge its session cache entry."""
    if not token:
        return
    ttl = _remaining_ttl(token)
    try:
        pipe = redis.pipeline()
        pipe.set(f"{_BLACKLIST_PREFIX}{token}", "1", ex=ttl)
        pipe.delete(f"{_SESSION_PREFIX}{token}")
        await pipe.execute()
    except RedisError as exc:
        logger.warning("redis_blacklist_write_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email + password, return a signed JWT."""
    user = await session.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token = create_access_token(str(user.id), {"role": user.role})
    logger.info("user_logged_in", user_id=str(user.id), role=user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user's profile."""
    return user


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    """
    Issue a fresh access token for the current user without re-entering credentials.

    Immediately blacklists the old token (token rotation) so it cannot be
    replayed after a new one is issued.
    """
    old_token = _extract_bearer(request)

    # Issue new token first so the user is never left without a valid token
    new_token = create_access_token(str(user.id), {"role": user.role})

    # Blacklist old token (fire-and-forget; Redis failure is non-fatal)
    await _blacklist_token(redis, old_token)
    logger.info("token_rotated", user_id=str(user.id))

    return TokenResponse(access_token=new_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> None:
    """
    Immediately invalidate the current Bearer token.

    The token is added to the Redis blacklist with a TTL equal to its
    remaining JWT lifetime so the entry self-cleans after natural expiry.
    The session cache entry is also purged.
    """
    token = _extract_bearer(request)
    await _blacklist_token(redis, token)
    logger.info("user_logged_out", user_id=str(user.id))


@router.get("/microsoft/start")
async def microsoft_sso_start() -> dict[str, str]:
    if not settings.microsoft_sso_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Microsoft SSO is not configured for this environment.",
        )

    params = urlencode(
        {
            "client_id": settings.microsoft_client_id,
            "response_type": "code",
            "redirect_uri": settings.microsoft_redirect_uri,
            "response_mode": "query",
            "scope": "openid profile email User.Read",
        }
    )
    auth_url = (
        f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}"
        f"/oauth2/v2.0/authorize?{params}"
    )
    return {"authorization_url": auth_url}


@router.get("/microsoft/callback")
async def microsoft_sso_callback(
    code: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
    session: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """
    OAuth 2.0 authorization-code callback from Azure Active Directory.

    Azure redirects here after the user authenticates.  We exchange the
    authorization code for tokens, fetch the user's profile from Graph,
    look up (or provision) their local account, issue an AtomQuest JWT,
    and redirect the browser to the frontend with the token in the URL
    fragment so it is never logged by server infrastructure.

    Error path: any failure redirects to the frontend login page with
    ``?sso_error=<reason>`` so the UI can display a friendly message.
    """
    if not settings.microsoft_sso_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Microsoft SSO is not configured for this environment.",
        )

    frontend_base = settings.frontend_app_url.rstrip("/")

    # ── Azure returned an error ───────────────────────────────────────────
    if error:
        detail = error_description or error
        logger.warning("microsoft_sso_callback_error", error=error, detail=detail)
        return RedirectResponse(
            url=f"{frontend_base}/login?sso_error={error}",
            status_code=302,
        )

    if not code:
        return RedirectResponse(
            url=f"{frontend_base}/login?sso_error=missing_code",
            status_code=302,
        )

    # ── Exchange authorization code for access + id tokens ────────────────
    token_url = (
        f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}"
        "/oauth2/v2.0/token"
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(
                token_url,
                data={
                    "client_id": settings.microsoft_client_id,
                    "client_secret": settings.microsoft_client_secret,
                    "code": code,
                    "redirect_uri": settings.microsoft_redirect_uri,
                    "grant_type": "authorization_code",
                    "scope": "openid profile email User.Read",
                },
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
    except Exception as exc:
        logger.error("microsoft_token_exchange_failed", error=str(exc))
        return RedirectResponse(
            url=f"{frontend_base}/login?sso_error=token_exchange_failed",
            status_code=302,
        )

    ms_access_token = token_data.get("access_token", "")
    if not ms_access_token:
        return RedirectResponse(
            url=f"{frontend_base}/login?sso_error=no_access_token",
            status_code=302,
        )

    # ── Fetch user profile from Microsoft Graph ───────────────────────────
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            graph_resp = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {ms_access_token}"},
                params={"$select": "id,mail,userPrincipalName,displayName"},
            )
            graph_resp.raise_for_status()
            profile = graph_resp.json()
    except Exception as exc:
        logger.error("microsoft_graph_fetch_failed", error=str(exc))
        return RedirectResponse(
            url=f"{frontend_base}/login?sso_error=graph_fetch_failed",
            status_code=302,
        )

    # ``mail`` can be None for some account types; fall back to UPN.
    ms_email: str | None = profile.get("mail") or profile.get("userPrincipalName")
    ms_name: str = profile.get("displayName") or (ms_email or "Unknown")

    if not ms_email:
        return RedirectResponse(
            url=f"{frontend_base}/login?sso_error=no_email_in_profile",
            status_code=302,
        )

    # ── Look up user in AtomQuest DB ──────────────────────────────────────
    user: User | None = await session.scalar(
        select(User).where(User.email == ms_email)
    )
    if not user:
        # SSO users must be pre-provisioned by an admin.  We do not auto-create
        # accounts to avoid uncontrolled access; return a friendly error.
        logger.warning("microsoft_sso_user_not_found", email=ms_email)
        return RedirectResponse(
            url=f"{frontend_base}/login?sso_error=user_not_provisioned",
            status_code=302,
        )

    # ── Issue AtomQuest JWT and redirect to frontend ───────────────────────
    aq_token = create_access_token(str(user.id), {"role": user.role})
    logger.info(
        "microsoft_sso_login_success",
        user_id=str(user.id),
        role=user.role,
        name=ms_name,
    )
    # Pass the JWT in the URL fragment — never logged by reverse proxies.
    return RedirectResponse(
        url=f"{frontend_base}/auth/callback#token={aq_token}",
        status_code=302,
    )
