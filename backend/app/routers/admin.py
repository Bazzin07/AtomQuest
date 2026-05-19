from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_redis, require_role
from app.models.enums import GoalStatus, UserRole
from app.models.checkin import CheckinWindow
from app.models.goal import Goal, GoalCycle, ThrustArea
from app.models.notification import NotificationLog
from app.models.user import User
from app.schemas.admin import (
    CheckinWindowCreate,
    CheckinWindowUpdate,
    GoalCycleCreate,
    GoalCycleRead,
    ThrustAreaCreate,
    ThrustAreaRead,
)
from app.schemas.checkin import CheckinWindowRead
from app.schemas.common import Message
from app.schemas.notification import NotificationLogRead
from app.services.audit import write_audit_log

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/cycles", response_model=list[GoalCycleRead])
async def list_cycles(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER, UserRole.EMPLOYEE)),
) -> list[GoalCycle]:
    return list((await session.scalars(select(GoalCycle).order_by(GoalCycle.start_date.desc()))).all())


@router.post("/cycles", response_model=GoalCycleRead, status_code=status.HTTP_201_CREATED)
async def create_cycle(
    payload: GoalCycleCreate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> GoalCycle:
    cycle = GoalCycle(created_by=admin.id, **payload.model_dump())
    session.add(cycle)
    await session.commit()
    await session.refresh(cycle)
    return cycle


@router.get("/thrust-areas", response_model=list[ThrustAreaRead])
async def list_thrust_areas(
    cycle_id: UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER, UserRole.EMPLOYEE)),
) -> list[ThrustArea]:
    return list(
        (
            await session.scalars(
                select(ThrustArea).where(ThrustArea.cycle_id == cycle_id).order_by(ThrustArea.name)
            )
        ).all()
    )


@router.post("/thrust-areas", response_model=ThrustAreaRead, status_code=status.HTTP_201_CREATED)
async def create_thrust_area(
    payload: ThrustAreaCreate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.ADMIN)),
) -> ThrustArea:
    thrust_area = ThrustArea(**payload.model_dump())
    session.add(thrust_area)
    await session.commit()
    await session.refresh(thrust_area)
    return thrust_area


@router.get("/checkin-windows", response_model=list[CheckinWindowRead])
async def list_checkin_windows(
    cycle_id: UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER, UserRole.EMPLOYEE)),
) -> list[CheckinWindow]:
    return list(
        (
            await session.scalars(
                select(CheckinWindow)
                .where(CheckinWindow.cycle_id == cycle_id)
                .order_by(CheckinWindow.opens_at)
            )
        ).all()
    )


@router.post(
    "/checkin-windows", response_model=CheckinWindowRead, status_code=status.HTTP_201_CREATED
)
async def create_checkin_window(
    payload: CheckinWindowCreate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> CheckinWindow:
    window = CheckinWindow(**payload.model_dump())
    session.add(window)
    await session.flush()
    await write_audit_log(
        session,
        entity_type="checkin_window",
        entity_id=window.id,
        action="created",
        changed_by=admin.id,
        new_values=payload.model_dump(mode="json"),
    )
    await session.commit()
    await session.refresh(window)
    return window


@router.patch("/checkin-windows/{window_id}", response_model=CheckinWindowRead)
async def update_checkin_window(
    window_id: UUID,
    payload: CheckinWindowUpdate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> CheckinWindow:
    window = await session.get(CheckinWindow, window_id)
    if not window:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Check-in window not found")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return window

    old_values = {
        "opens_at": window.opens_at,
        "closes_at": window.closes_at,
    }
    for field, value in updates.items():
        setattr(window, field, value)

    await write_audit_log(
        session,
        entity_type="checkin_window",
        entity_id=window.id,
        action="updated",
        changed_by=admin.id,
        old_values=old_values,
        new_values=updates,
    )
    await session.commit()
    await session.refresh(window)
    return window


@router.post("/goals/{goal_id}/unlock", response_model=Message)
async def unlock_goal(
    goal_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> Message:
    """Admin-only: unlock a LOCKED goal, returning it to RETURNED status for correction."""
    goal = await session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    if goal.status != GoalStatus.LOCKED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Only LOCKED goals can be unlocked (current status: {goal.status})",
        )
    employee = await session.get(User, goal.employee_id)
    goal.status = GoalStatus.RETURNED
    goal.locked_at = None
    goal.returned_reason = f"Unlocked by admin {admin.id} at {datetime.now(UTC).isoformat()}"
    await write_audit_log(
        session,
        entity_type="goal",
        entity_id=goal.id,
        action="admin_unlocked",
        changed_by=admin.id,
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    # Invalidate the employee's goal list cache so stale LOCKED status is not served
    try:
        keys = [f"goals:employee:{goal.employee_id}:cycle:{goal.cycle_id}"]
        if employee and employee.manager_id:
            keys.append(f"goals:team:{employee.manager_id}:cycle:{goal.cycle_id}")
        await redis.delete(*keys)
    except Exception:
        pass  # Cache miss is acceptable — never block on cache errors
    return Message(message="Goal unlocked for editing")


@router.get("/notifications", response_model=list[NotificationLogRead])
async def list_notification_logs(
    channel: str | None = None,
    event_type: str | None = None,
    status_filter: str | None = None,
    page: int = 1,
    size: int = 50,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.ADMIN)),
) -> list[NotificationLog]:
    page = max(page, 1)
    size = min(max(size, 1), 200)
    stmt = (
        select(NotificationLog)
        .order_by(NotificationLog.attempted_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    if channel:
        stmt = stmt.where(NotificationLog.channel == channel)
    if event_type:
        stmt = stmt.where(NotificationLog.event_type == event_type)
    if status_filter:
        stmt = stmt.where(NotificationLog.status == status_filter)
    return list((await session.scalars(stmt)).all())
