from uuid import UUID

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_redis, require_role
from app.models.enums import UserRole
from app.models.user import User
from app.services.analytics import (
    completion_heatmap,
    distribution,
    manager_effectiveness,
    manager_scorecard,
    qoq_analytics,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/qoq")
async def qoq(
    cycle_id: UUID,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> dict:
    return await qoq_analytics(session, redis, cycle_id=cycle_id, user=user)


@router.get("/completion-heatmap")
async def heatmap(
    cycle_id: UUID,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> dict:
    return await completion_heatmap(session, redis, cycle_id=cycle_id, user=user)


@router.get("/distribution")
async def distribution_endpoint(
    cycle_id: UUID,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> dict:
    return await distribution(session, redis, cycle_id=cycle_id, user=user)


@router.get("/manager-effectiveness")
async def manager_effectiveness_endpoint(
    cycle_id: UUID,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> dict:
    return await manager_effectiveness(session, redis, cycle_id=cycle_id, user=user)


@router.get("/manager-scorecard/{manager_id}", summary="Per-manager deep-drill scorecard (B6)")
async def manager_scorecard_endpoint(
    manager_id: UUID,
    cycle_id: UUID,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> dict:
    """
    Returns a detailed scorecard for a single manager:
    - Aggregate KPIs (approval rate, turnaround time, return rate, checkin coverage)
    - Overdue check-in escalation count
    - Per-employee breakdown table
    """
    # Managers can only view their own scorecard; admins can view any
    if user.role == UserRole.MANAGER and user.id != manager_id:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only view your own scorecard")
    try:
        return await manager_scorecard(session, redis, cycle_id=cycle_id, manager_id=manager_id)
    except ValueError as exc:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
