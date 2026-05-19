from decimal import Decimal
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.achievement import GoalAchievement
from app.models.checkin import CheckinComment
from app.models.enums import GoalStatus, UserRole
from app.models.goal import Goal, ThrustArea
from app.models.user import User
from app.schemas.analytics import (
    CompletionHeatmapResponse,
    DistributionBucket,
    DistributionResponse,
    ManagerEffectivenessResponse,
    QoqAnalyticsResponse,
    enum_key,
)
from app.services.cache import JsonCache


def _to_float(value: Decimal | float | int | None) -> float | None:
    return float(value) if value is not None else None


def _cache_key(name: str, cycle_id: UUID, user: User) -> str:
    return f"analytics:{name}:{cycle_id}:{user.role}:{user.id}"


def _employee_scope(stmt, user: User):
    if user.role == UserRole.MANAGER:
        return stmt.where(User.manager_id == user.id)
    if user.role == UserRole.EMPLOYEE:
        return stmt.where(User.id == user.id)
    return stmt


async def _cached(redis: Redis, key: str, producer):
    cache = JsonCache(redis, ttl_seconds=600)
    cached = await cache.get(key)
    if cached is not None:
        return cached
    value = await producer()
    await cache.set(key, value)
    return value


async def qoq_analytics(
    session: AsyncSession, redis: Redis, *, cycle_id: UUID, user: User
) -> dict:
    async def produce() -> dict:
        stmt = (
            select(
                GoalAchievement.quarter,
                User.department,
                func.count(func.distinct(Goal.id)).label("goal_count"),
                func.count(func.distinct(GoalAchievement.id)).label("achievement_count"),
                func.avg(GoalAchievement.computed_score).label("average_score"),
            )
            .join(Goal, GoalAchievement.goal_id == Goal.id)
            .join(User, Goal.employee_id == User.id)
            .where(Goal.cycle_id == cycle_id)
            .group_by(GoalAchievement.quarter, User.department)
            .order_by(GoalAchievement.quarter, User.department)
        )
        stmt = _employee_scope(stmt, user)
        rows = (await session.execute(stmt)).mappings().all()
        response = QoqAnalyticsResponse(
            cycle_id=cycle_id,
            rows=[
                {
                    "quarter": row["quarter"],
                    "department": row["department"],
                    "goal_count": row["goal_count"],
                    "achievement_count": row["achievement_count"],
                    "average_score": _to_float(row["average_score"]),
                }
                for row in rows
            ],
        )
        return response.model_dump(mode="json")

    return await _cached(redis, _cache_key("qoq", cycle_id, user), produce)


async def completion_heatmap(
    session: AsyncSession, redis: Redis, *, cycle_id: UUID, user: User
) -> dict:
    async def produce() -> dict:
        stmt = (
            select(
                GoalAchievement.quarter,
                User.department,
                func.count(func.distinct(Goal.id)).label("total_goals"),
                func.count(func.distinct(GoalAchievement.id)).label("achievement_updates"),
                func.count(func.distinct(CheckinComment.id)).label("manager_comments"),
            )
            .join(Goal, GoalAchievement.goal_id == Goal.id)
            .join(User, Goal.employee_id == User.id)
            .join(
                CheckinComment,
                and_(
                    CheckinComment.goal_id == Goal.id,
                    CheckinComment.quarter == GoalAchievement.quarter,
                ),
                isouter=True,
            )
            .where(Goal.cycle_id == cycle_id)
            .group_by(GoalAchievement.quarter, User.department)
            .order_by(GoalAchievement.quarter, User.department)
        )
        stmt = _employee_scope(stmt, user)
        rows = (await session.execute(stmt)).mappings().all()
        response = CompletionHeatmapResponse(
            cycle_id=cycle_id,
            rows=[
                {
                    "quarter": row["quarter"],
                    "department": row["department"],
                    "total_goals": row["total_goals"],
                    "achievement_updates": row["achievement_updates"],
                    "manager_comments": row["manager_comments"],
                }
                for row in rows
            ],
        )
        return response.model_dump(mode="json")

    return await _cached(redis, _cache_key("completion-heatmap", cycle_id, user), produce)


async def distribution(session: AsyncSession, redis: Redis, *, cycle_id: UUID, user: User) -> dict:
    async def produce() -> dict:
        goal_status_stmt = (
            select(Goal.status, func.count(Goal.id).label("count"))
            .join(User, Goal.employee_id == User.id)
            .where(Goal.cycle_id == cycle_id)
            .group_by(Goal.status)
        )
        progress_stmt = (
            select(GoalAchievement.status, func.count(GoalAchievement.id).label("count"))
            .join(Goal, GoalAchievement.goal_id == Goal.id)
            .join(User, Goal.employee_id == User.id)
            .where(Goal.cycle_id == cycle_id)
            .group_by(GoalAchievement.status)
        )
        thrust_stmt = (
            select(ThrustArea.name, func.count(Goal.id).label("count"))
            .join(Goal, Goal.thrust_area_id == ThrustArea.id)
            .join(User, Goal.employee_id == User.id)
            .where(Goal.cycle_id == cycle_id)
            .group_by(ThrustArea.name)
        )
        uom_stmt = (
            select(Goal.uom_type, func.count(Goal.id).label("count"))
            .join(User, Goal.employee_id == User.id)
            .where(Goal.cycle_id == cycle_id)
            .group_by(Goal.uom_type)
        )
        statements = [
            _employee_scope(goal_status_stmt, user),
            _employee_scope(progress_stmt, user),
            _employee_scope(thrust_stmt, user),
            _employee_scope(uom_stmt, user),
        ]
        goal_rows, progress_rows, thrust_rows, uom_rows = [
            (await session.execute(stmt)).all() for stmt in statements
        ]
        response = DistributionResponse(
            cycle_id=cycle_id,
            goal_status=[DistributionBucket(key=enum_key(key), count=count) for key, count in goal_rows],
            progress_status=[
                DistributionBucket(key=enum_key(key), count=count) for key, count in progress_rows
            ],
            thrust_area=[DistributionBucket(key=enum_key(key), count=count) for key, count in thrust_rows],
            uom_type=[DistributionBucket(key=enum_key(key), count=count) for key, count in uom_rows],
        )
        return response.model_dump(mode="json")

    return await _cached(redis, _cache_key("distribution", cycle_id, user), produce)


async def manager_effectiveness(
    session: AsyncSession, redis: Redis, *, cycle_id: UUID, user: User
) -> dict:
    async def produce() -> dict:
        manager = aliased(User)
        employee = aliased(User)

        # Main aggregation query
        stmt = (
            select(
                manager.id.label("manager_id"),
                manager.name.label("manager_name"),
                manager.department.label("department"),
                func.count(func.distinct(employee.id)).label("team_members"),
                func.count(func.distinct(Goal.id)).label("total_goals"),
                func.count(func.distinct(Goal.id)).filter(Goal.status == GoalStatus.LOCKED).label(
                    "approved_goals"
                ),
                func.count(func.distinct(Goal.id)).filter(Goal.status == GoalStatus.RETURNED).label(
                    "goals_returned"
                ),
                func.count(func.distinct(GoalAchievement.id)).label("achievement_updates"),
                func.count(func.distinct(CheckinComment.id)).label("manager_comments"),
                func.avg(GoalAchievement.computed_score).label("average_score"),
                # Average days from submission to approval (non-NULL approved_at only)
                func.avg(
                    func.extract(
                        "epoch",
                        Goal.approved_at - Goal.updated_at,
                    ) / 86400.0
                ).filter(Goal.approved_at.isnot(None)).label("approval_turnaround_avg_days"),
            )
            .select_from(manager)
            .join(employee, employee.manager_id == manager.id)
            .join(Goal, Goal.employee_id == employee.id)
            .join(GoalAchievement, GoalAchievement.goal_id == Goal.id, isouter=True)
            .join(CheckinComment, CheckinComment.goal_id == Goal.id, isouter=True)
            .where(manager.role == UserRole.MANAGER, Goal.cycle_id == cycle_id)
            .group_by(manager.id, manager.name, manager.department)
            .order_by(manager.name)
        )
        if user.role == UserRole.MANAGER:
            stmt = stmt.where(manager.id == user.id)
        rows = (await session.execute(stmt)).mappings().all()

        # Fetch overdue checkin escalation counts per manager
        from app.models.enums import EscalationEventType, EscalationStatus
        from app.models.escalation import EscalationLog

        overdue_stmt = (
            select(
                EscalationLog.manager_id.label("manager_id"),
                func.count(EscalationLog.id).label("overdue_count"),
            )
            .where(
                EscalationLog.cycle_id == cycle_id,
                EscalationLog.status == EscalationStatus.OPEN,
                EscalationLog.event_type == EscalationEventType.CHECKIN_NOT_COMPLETED,
            )
            .group_by(EscalationLog.manager_id)
        )
        overdue_rows = {
            row["manager_id"]: row["overdue_count"]
            for row in (await session.execute(overdue_stmt)).mappings().all()
        }

        response = ManagerEffectivenessResponse(
            cycle_id=cycle_id,
            rows=[
                {
                    "manager_id": row["manager_id"],
                    "manager_name": row["manager_name"],
                    "department": row["department"],
                    "team_members": row["team_members"],
                    "total_goals": row["total_goals"],
                    "approved_goals": row["approved_goals"],
                    "goals_returned": row["goals_returned"],
                    "return_rate_percent": round(
                        (row["goals_returned"] / row["total_goals"]) * 100, 2
                    ) if row["total_goals"] else 0.0,
                    "achievement_updates": row["achievement_updates"],
                    "manager_comments": row["manager_comments"],
                    "average_score": _to_float(row["average_score"]),
                    "checkin_coverage_percent": round(
                        (row["manager_comments"] / row["total_goals"]) * 100, 2
                    ) if row["total_goals"] else 0.0,
                    "approval_turnaround_avg_days": _to_float(row["approval_turnaround_avg_days"]),
                    "overdue_checkins": overdue_rows.get(row["manager_id"], 0),
                }
                for row in rows
            ],
        )
        return response.model_dump(mode="json")

    return await _cached(redis, _cache_key("manager-effectiveness", cycle_id, user), produce)


async def manager_scorecard(
    session: AsyncSession, redis: Redis, *, cycle_id: UUID, manager_id: UUID
) -> dict:
    """
    Per-manager deep-drill scorecard (B6).
    Returns aggregate stats + per-employee breakdown for the given manager.
    """
    from app.models.enums import EscalationEventType, EscalationStatus
    from app.models.escalation import EscalationLog
    from app.schemas.analytics import ManagerScorecardResponse

    cache = JsonCache(redis, ttl_seconds=600)
    cache_key = f"analytics:scorecard:{cycle_id}:{manager_id}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    mgr = await session.get(User, manager_id)
    if not mgr or mgr.role != UserRole.MANAGER:
        raise ValueError("Manager not found")

    employee_alias = aliased(User)

    # Team aggregate
    agg = (
        await session.execute(
            select(
                func.count(func.distinct(employee_alias.id)).label("team_members"),
                func.count(func.distinct(Goal.id)).label("total_goals"),
                func.count(func.distinct(Goal.id)).filter(Goal.status == GoalStatus.LOCKED).label("approved_goals"),
                func.count(func.distinct(Goal.id)).filter(Goal.status == GoalStatus.RETURNED).label("goals_returned"),
                func.count(func.distinct(GoalAchievement.id)).label("achievement_updates"),
                func.count(func.distinct(CheckinComment.id)).label("manager_comments"),
                func.avg(GoalAchievement.computed_score).label("average_score"),
                func.avg(
                    func.extract("epoch", Goal.approved_at - Goal.updated_at) / 86400.0
                ).filter(Goal.approved_at.isnot(None)).label("approval_turnaround_avg_days"),
            )
            .select_from(employee_alias)
            .join(Goal, Goal.employee_id == employee_alias.id)
            .join(GoalAchievement, GoalAchievement.goal_id == Goal.id, isouter=True)
            .join(CheckinComment, CheckinComment.goal_id == Goal.id, isouter=True)
            .where(employee_alias.manager_id == manager_id, Goal.cycle_id == cycle_id)
        )
    ).mappings().one_or_none()

    agg = dict(agg) if agg else {}

    # Overdue checkins
    overdue_count = await session.scalar(
        select(func.count(EscalationLog.id)).where(
            EscalationLog.cycle_id == cycle_id,
            EscalationLog.manager_id == manager_id,
            EscalationLog.status == EscalationStatus.OPEN,
            EscalationLog.event_type == EscalationEventType.CHECKIN_NOT_COMPLETED,
        )
    ) or 0

    # Per-employee breakdown
    emp_rows = (
        await session.execute(
            select(
                employee_alias.id.label("employee_id"),
                employee_alias.name.label("employee_name"),
                employee_alias.department.label("department"),
                func.count(func.distinct(Goal.id)).label("total_goals"),
                func.count(func.distinct(Goal.id)).filter(Goal.status == GoalStatus.LOCKED).label("approved_goals"),
                func.avg(GoalAchievement.computed_score).label("average_score"),
            )
            .select_from(employee_alias)
            .join(Goal, Goal.employee_id == employee_alias.id)
            .join(GoalAchievement, GoalAchievement.goal_id == Goal.id, isouter=True)
            .where(employee_alias.manager_id == manager_id, Goal.cycle_id == cycle_id)
            .group_by(employee_alias.id, employee_alias.name, employee_alias.department)
            .order_by(employee_alias.name)
        )
    ).mappings().all()

    total = agg.get("total_goals") or 0
    returned = agg.get("goals_returned") or 0
    comments = agg.get("manager_comments") or 0

    result = ManagerScorecardResponse(
        manager_id=manager_id,
        manager_name=mgr.name,
        department=mgr.department,
        cycle_id=cycle_id,
        team_members=agg.get("team_members") or 0,
        total_goals=total,
        approved_goals=agg.get("approved_goals") or 0,
        goals_returned=returned,
        return_rate_percent=round((returned / total) * 100, 2) if total else 0.0,
        average_score=_to_float(agg.get("average_score")),
        checkin_coverage_percent=round((comments / total) * 100, 2) if total else 0.0,
        approval_turnaround_avg_days=_to_float(agg.get("approval_turnaround_avg_days")),
        overdue_checkins=overdue_count,
        team_breakdown=[
            {
                "employee_id": str(r["employee_id"]),
                "employee_name": r["employee_name"],
                "department": r["department"],
                "total_goals": r["total_goals"],
                "approved_goals": r["approved_goals"],
                "average_score": _to_float(r["average_score"]),
            }
            for r in emp_rows
        ],
    )
    serialized = result.model_dump(mode="json")
    await cache.set(cache_key, serialized)
    return serialized
