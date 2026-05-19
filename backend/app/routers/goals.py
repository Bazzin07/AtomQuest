"""
Goals router — full CRUD + state machine transitions.

Endpoints:
  GET  /goals                     Employee: my goals (with optional Redis cache)
  GET  /goals/{id}                Read one accessible goal
  POST /goals                     Create a goal (max 8 per cycle)
  PUT  /goals/{id}                Employee edit with optimistic locking
  POST /goals/submit              Bulk submit DRAFT/RETURNED goals for approval
  GET  /goals/team                Manager: all team goals
  POST /goals/{id}/approve        SUBMITTED → APPROVED
  POST /goals/{id}/lock           APPROVED  → LOCKED
  PUT  /goals/{id}/manager-edit   Manager inline edit (SUBMITTED only)
  POST /goals/{id}/return         SUBMITTED → RETURNED
  POST /goals/shared              Push shared KPI to multiple employees

Optimistic locking:
  PUT /goals/{id} accepts an optional `If-Match: <version>` header.
  If provided and it doesn't match the current version, a 409 Conflict
  is returned. This prevents last-write-wins concurrency bugs.

Cache strategy (Redis cache-aside):
  GET /goals?cycle_id=X caches per-employee per-cycle with 5-min TTL.
  Any state-mutating operation invalidates the affected cache keys.
"""
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import ensure_manager_access, get_current_user, get_db, get_redis, require_role
from app.models.enums import GoalStatus, UserRole
from app.models.goal import Goal
from app.models.user import User
from app.schemas.common import Message
from app.schemas.goal import (
    GoalCreate,
    GoalRead,
    GoalReturnRequest,
    GoalSubmitRequest,
    GoalUpdate,
    ManagerGoalEdit,
    SharedGoalCreate,
)
from app.services.audit import write_audit_log
from app.services.cache import JsonCache
from app.services.notification import (
    notify_goal_approved,
    notify_goal_locked,
    notify_goal_returned,
    notify_goal_submitted,
)
from app.services.validation import ensure_unlocked, validate_goal_sheet

router = APIRouter(prefix="/goals", tags=["goals"])

_GOAL_CACHE_TTL = 300  # 5 minutes


def _goal_cache_key(employee_id: UUID, cycle_id: UUID | None) -> str:
    return f"goals:employee:{employee_id}:cycle:{cycle_id}"


def _team_cache_key(manager_id: UUID, cycle_id: UUID | None) -> str:
    return f"goals:team:{manager_id}:cycle:{cycle_id}"


async def _invalidate_goal_cache(redis: Redis, employee_id: UUID, cycle_id: UUID | None) -> None:
    """Invalidate the goal list cache for the given employee+cycle."""
    try:
        key = _goal_cache_key(employee_id, cycle_id)
        await redis.delete(key)
    except RedisError:
        pass  # Cache miss on next GET is acceptable


async def _invalidate_team_cache(redis: Redis, manager_id: UUID | None, cycle_id: UUID | None) -> None:
    """Invalidate team goal list cache for the manager."""
    if manager_id is None:
        return
    try:
        await redis.delete(_team_cache_key(manager_id, cycle_id))
    except RedisError:
        pass


@router.get("", response_model=list[GoalRead])
async def my_goals(
    cycle_id: UUID | None = None,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: User = Depends(get_current_user),
) -> list[Goal]:
    """Return the authenticated employee's goals, with Redis cache-aside."""
    cache = JsonCache(redis, ttl_seconds=_GOAL_CACHE_TTL)
    cache_key = _goal_cache_key(user.id, cycle_id)

    cached = await cache.get(cache_key)
    if cached is not None:
        # Return list of Pydantic-validated objects from cache
        return [GoalRead.model_validate(g) for g in cached]  # type: ignore[return-value]

    stmt = select(Goal).where(Goal.employee_id == user.id).order_by(Goal.created_at)
    if cycle_id:
        stmt = stmt.where(Goal.cycle_id == cycle_id)
    goals = list((await session.scalars(stmt)).all())

    # Populate cache
    await cache.set(cache_key, [GoalRead.model_validate(g).model_dump(mode="json") for g in goals])
    return goals


@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
async def create_goal(
    payload: GoalCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: User = Depends(get_current_user),
) -> Goal:
    """Create a new goal. Max 8 goals per cycle enforced."""
    existing_count = await session.scalar(
        select(func.count(Goal.id)).where(
            Goal.employee_id == user.id,
            Goal.cycle_id == payload.cycle_id,
        )
    )
    if existing_count >= 8:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Maximum 8 goals allowed per cycle")

    goal = Goal(employee_id=user.id, **payload.model_dump())
    session.add(goal)
    await session.flush()  # Populate goal.id before audit log

    await write_audit_log(
        session,
        entity_type="goal",
        entity_id=goal.id,
        action="created",
        changed_by=user.id,
        new_values=payload.model_dump(mode="json"),
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    await session.refresh(goal)
    await _invalidate_goal_cache(redis, user.id, payload.cycle_id)
    await _invalidate_team_cache(redis, user.manager_id, payload.cycle_id)
    return goal


@router.put("/{goal_id}", response_model=GoalRead)
@router.patch("/{goal_id}", response_model=GoalRead)
async def update_goal(
    goal_id: UUID,
    payload: GoalUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: User = Depends(get_current_user),
    if_match: int | None = Header(default=None, alias="if-match"),
) -> Goal:
    """
    Update a goal. Employee-only. Blocked on APPROVED/LOCKED.

    Supports optimistic concurrency control via the ``If-Match`` header.
    Pass the current ``version`` value returned by GET /goals. If the goal
    was modified concurrently, a 409 Conflict is returned.
    """
    goal = await session.get(Goal, goal_id)
    if not goal or goal.employee_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    ensure_unlocked(goal)

    # Optimistic locking — check version if caller provided If-Match header
    if if_match is not None and goal.version != if_match:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Goal was modified by another request (current version={goal.version}, "
            f"your version={if_match}). Fetch the latest and retry.",
        )

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return goal

    if goal.shared_source_id and any(k in updates for k in {"title", "target_value", "target_date"}):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Shared goal recipients may only edit weightage")

    old_values = {key: str(getattr(goal, key)) for key in updates}
    for key, value in updates.items():
        setattr(goal, key, value)
    goal.version += 1

    await write_audit_log(
        session,
        entity_type="goal",
        entity_id=goal.id,
        action="updated",
        changed_by=user.id,
        old_values=old_values,
        new_values={k: str(v) for k, v in updates.items()},
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    await session.refresh(goal)
    await _invalidate_goal_cache(redis, user.id, goal.cycle_id)
    await _invalidate_team_cache(redis, user.manager_id, goal.cycle_id)
    return goal


@router.delete("/{goal_id}", response_model=Message)
async def delete_goal(
    goal_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: User = Depends(get_current_user),
) -> Message:
    """Delete an employee-owned goal while it is still editable."""
    goal = await session.get(Goal, goal_id)
    if not goal or goal.employee_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    ensure_unlocked(goal)

    await write_audit_log(
        session,
        entity_type="goal",
        entity_id=goal.id,
        action="deleted",
        changed_by=user.id,
        old_values={
            "title": goal.title,
            "weightage": goal.weightage,
            "status": goal.status,
        },
        ip_address=request.client.host if request.client else None,
    )
    cycle_id = goal.cycle_id
    await session.delete(goal)
    await session.commit()
    await _invalidate_goal_cache(redis, user.id, cycle_id)
    await _invalidate_team_cache(redis, user.manager_id, cycle_id)
    return Message(message="Goal deleted")


@router.post("/submit", response_model=Message)
async def submit_goal_sheet(
    payload: GoalSubmitRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: User = Depends(get_current_user),
) -> Message:
    """Bulk submit all DRAFT/RETURNED goals for the given cycle."""
    await validate_goal_sheet(session, user.id, payload.cycle_id)
    goals = (
        await session.scalars(
            select(Goal).where(
                Goal.employee_id == user.id,
                Goal.cycle_id == payload.cycle_id,
                Goal.status.in_([GoalStatus.DRAFT, GoalStatus.RETURNED]),
            )
        )
    ).all()
    for goal in goals:
        goal.status = GoalStatus.SUBMITTED
        goal.returned_reason = None
        await write_audit_log(
            session,
            entity_type="goal",
            entity_id=goal.id,
            action="submitted",
            changed_by=user.id,
            ip_address=request.client.host if request.client else None,
        )
    await session.commit()
    await _invalidate_goal_cache(redis, user.id, payload.cycle_id)
    await _invalidate_team_cache(redis, user.manager_id, payload.cycle_id)
    # Notify manager (fire-and-forget) — load manager info for email
    try:
        await session.refresh(user)
        if user.manager_id:
            manager_user = await session.get(User, user.manager_id)
            if manager_user:
                await notify_goal_submitted(
                    cycle_id=payload.cycle_id,
                    manager_email=manager_user.email,
                    manager_user_id=manager_user.id,
                    manager_name=manager_user.name,
                    employee_name=user.name,
                    department=user.department or "",
                    cycle_name=str(payload.cycle_id),
                    goal_count=len(goals),
                )
    except Exception:  # noqa: BLE001
        pass  # Notification failure must never break the API response
    return Message(message="Goal sheet submitted for manager approval")


@router.get("/team", response_model=list[GoalRead])
async def team_goals(
    cycle_id: UUID | None = None,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    manager: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> list[Goal]:
    """Return all goals for the manager's direct reports (or all goals for admin), with Redis cache."""
    # Admins see all goals — don't cache (too broad; varies by filter)
    if manager.role != UserRole.ADMIN:
        cache = JsonCache(redis, ttl_seconds=_GOAL_CACHE_TTL)
        cache_key = _team_cache_key(manager.id, cycle_id)
        cached = await cache.get(cache_key)
        if cached is not None:
            return [GoalRead.model_validate(g) for g in cached]  # type: ignore[return-value]

    stmt = (
        select(Goal)
        .join(User, Goal.employee_id == User.id)
        .order_by(Goal.created_at)
    )
    if manager.role == UserRole.MANAGER:
        stmt = stmt.where(User.manager_id == manager.id)
    if cycle_id:
        stmt = stmt.where(Goal.cycle_id == cycle_id)
    goals = list((await session.scalars(stmt)).all())

    if manager.role != UserRole.ADMIN:
        cache_key = _team_cache_key(manager.id, cycle_id)
        await cache.set(cache_key, [GoalRead.model_validate(g).model_dump(mode="json") for g in goals])
    return goals


@router.get("/{goal_id}", response_model=GoalRead)
async def get_goal(
    goal_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Goal:
    """Return a single goal if the user owns it or can review the employee."""
    goal = await session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    if goal.employee_id == user.id:
        return goal
    if user.role in {UserRole.MANAGER, UserRole.ADMIN}:
        await ensure_manager_access(session, user, goal.employee_id)
        return goal
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")


@router.post("/{goal_id}/approve", response_model=Message)
async def approve_goal(
    goal_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    manager: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> Message:
    """
    Manager approves a submitted goal: SUBMITTED → APPROVED.

    An APPROVED goal is confirmed by the manager but not yet immutably locked.
    Use POST /goals/{id}/lock to finalize.
    """
    goal = await session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    await ensure_manager_access(session, manager, goal.employee_id)
    if goal.status != GoalStatus.SUBMITTED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Only SUBMITTED goals can be approved (current status: {goal.status})",
        )
    goal.status = GoalStatus.APPROVED
    goal.approved_at = datetime.now(UTC)
    await write_audit_log(
        session,
        entity_type="goal",
        entity_id=goal.id,
        action="approved",
        changed_by=manager.id,
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    await _invalidate_goal_cache(redis, goal.employee_id, goal.cycle_id)
    await _invalidate_team_cache(redis, manager.id, goal.cycle_id)
    # Notify employee (fire-and-forget)
    try:
        employee_user = await session.get(User, goal.employee_id)
        from app.models.goal import GoalCycle
        cycle_obj = await session.get(GoalCycle, goal.cycle_id)
        if employee_user:
            await notify_goal_approved(
                goal_id=goal.id,
                cycle_id=goal.cycle_id,
                employee_email=employee_user.email,
                employee_user_id=employee_user.id,
                employee_name=employee_user.name,
                manager_name=manager.name,
                cycle_name=cycle_obj.name if cycle_obj else str(goal.cycle_id),
                approved_at=goal.approved_at,
            )
    except Exception:  # noqa: BLE001
        pass
    return Message(message="Goal approved")


@router.post("/{goal_id}/lock", response_model=Message)
async def lock_goal(
    goal_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    manager: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> Message:
    """
    Final immutable lock: APPROVED → LOCKED.

    Once locked a goal cannot be edited by the employee or manager.
    Only an admin can unlock via POST /admin/goals/{id}/unlock.
    """
    goal = await session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    await ensure_manager_access(session, manager, goal.employee_id)
    if goal.status != GoalStatus.APPROVED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Only APPROVED goals can be locked (current status: {goal.status}). "
            "Use /approve first.",
        )
    goal.status = GoalStatus.LOCKED
    goal.locked_at = datetime.now(UTC)
    await write_audit_log(
        session,
        entity_type="goal",
        entity_id=goal.id,
        action="locked",
        changed_by=manager.id,
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    await _invalidate_goal_cache(redis, goal.employee_id, goal.cycle_id)
    await _invalidate_team_cache(redis, manager.id, goal.cycle_id)
    # Notify employee (fire-and-forget)
    try:
        employee_user = await session.get(User, goal.employee_id)
        from app.models.goal import GoalCycle
        cycle_obj = await session.get(GoalCycle, goal.cycle_id)
        if employee_user:
            await notify_goal_locked(
                goal_id=goal.id,
                cycle_id=goal.cycle_id,
                employee_email=employee_user.email,
                employee_user_id=employee_user.id,
                employee_name=employee_user.name,
                manager_name=manager.name,
                cycle_name=cycle_obj.name if cycle_obj else str(goal.cycle_id),
                locked_at=goal.locked_at,
            )
    except Exception:  # noqa: BLE001
        pass
    return Message(message="Goal locked for the quarter")


@router.put("/{goal_id}/manager-edit", response_model=GoalRead)
async def manager_edit_goal(
    goal_id: UUID,
    payload: ManagerGoalEdit,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    manager: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> Goal:
    """Inline manager edit of a submitted goal (target value, date, weightage)."""
    goal = await session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    await ensure_manager_access(session, manager, goal.employee_id)
    if goal.status != GoalStatus.SUBMITTED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only SUBMITTED goals can be edited by manager")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return goal
    old_values = {key: str(getattr(goal, key)) for key in updates}
    for key, value in updates.items():
        setattr(goal, key, value)
    goal.version += 1
    await write_audit_log(
        session,
        entity_type="goal",
        entity_id=goal.id,
        action="manager_edited",
        changed_by=manager.id,
        old_values=old_values,
        new_values={k: str(v) for k, v in updates.items()},
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    await session.refresh(goal)
    await _invalidate_goal_cache(redis, goal.employee_id, goal.cycle_id)
    await _invalidate_team_cache(redis, manager.id, goal.cycle_id)
    return goal


@router.post("/{goal_id}/return", response_model=Message)
async def return_goal(
    goal_id: UUID,
    payload: GoalReturnRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    manager: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> Message:
    """Return a submitted goal to the employee for rework."""
    goal = await session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    await ensure_manager_access(session, manager, goal.employee_id)
    if goal.status != GoalStatus.SUBMITTED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only SUBMITTED goals can be returned")
    goal.status = GoalStatus.RETURNED
    goal.returned_reason = payload.reason
    await write_audit_log(
        session,
        entity_type="goal",
        entity_id=goal.id,
        action="returned",
        changed_by=manager.id,
        reason=payload.reason,
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    await _invalidate_goal_cache(redis, goal.employee_id, goal.cycle_id)
    await _invalidate_team_cache(redis, manager.id, goal.cycle_id)
    # Notify employee (fire-and-forget)
    try:
        employee_user = await session.get(User, goal.employee_id)
        from app.models.goal import GoalCycle
        cycle_obj = await session.get(GoalCycle, goal.cycle_id)
        if employee_user:
            await notify_goal_returned(
                goal_id=goal.id,
                cycle_id=goal.cycle_id,
                employee_email=employee_user.email,
                employee_user_id=employee_user.id,
                employee_name=employee_user.name,
                manager_name=manager.name,
                cycle_name=cycle_obj.name if cycle_obj else str(goal.cycle_id),
                goal_title=goal.title,
                reason=payload.reason,
            )
    except Exception:  # noqa: BLE001
        pass
    return Message(message="Goal returned for rework")


@router.post("/shared", response_model=list[GoalRead], status_code=status.HTTP_201_CREATED)
async def create_shared_goals(
    payload: SharedGoalCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> list[Goal]:
    """
    Push a shared KPI goal to multiple employees.

    The first goal created becomes the 'source'. Subsequent goals reference
    it via shared_source_id. Achievement updates on the source automatically
    propagate to all linked goals.
    """
    created: list[Goal] = []
    source_goal: Goal | None = None
    for employee_id in payload.employee_ids:
        if user.role == UserRole.MANAGER:
            await ensure_manager_access(session, user, employee_id)
        goal = Goal(
            employee_id=employee_id,
            cycle_id=payload.cycle_id,
            thrust_area_id=payload.thrust_area_id,
            title=payload.title,
            description=payload.description,
            uom_type=payload.uom_type,
            target_value=payload.target_value,
            target_date=payload.target_date,
            weightage=payload.weightage,
            is_shared=True,
            shared_source_id=source_goal.id if source_goal else None,
        )
        session.add(goal)
        await session.flush()
        source_goal = source_goal or goal
        await write_audit_log(
            session,
            entity_type="goal",
            entity_id=goal.id,
            action="shared_created",
            changed_by=user.id,
            new_values={"employee_id": str(employee_id), "title": payload.title},
            ip_address=request.client.host if request.client else None,
        )
        created.append(goal)
    await session.commit()
    for goal in created:
        await session.refresh(goal)
        await _invalidate_goal_cache(redis, goal.employee_id, goal.cycle_id)
    await _invalidate_team_cache(redis, user.id, payload.cycle_id)
    return created
