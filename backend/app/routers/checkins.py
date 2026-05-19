from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import ensure_manager_access, get_db, require_role
from app.models.achievement import GoalAchievement
from app.models.checkin import CheckinComment
from app.models.enums import Quarter, UserRole
from app.models.goal import Goal
from app.models.user import User
from app.schemas.checkin import CheckinCommentCreate, CheckinCommentRead, TeamCheckinRow
from app.services.audit import write_audit_log
from app.services.time_windows import ensure_checkin_window_open

router = APIRouter(prefix="/checkins", tags=["checkins"])


@router.get("/team", response_model=list[TeamCheckinRow])
async def team_checkins(
    cycle_id: UUID,
    quarter: Quarter,
    session: AsyncSession = Depends(get_db),
    manager: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> list[TeamCheckinRow]:
    stmt = (
        select(User, Goal, GoalAchievement, CheckinComment)
        .join(Goal, Goal.employee_id == User.id)
        .join(
            GoalAchievement,
            and_(GoalAchievement.goal_id == Goal.id, GoalAchievement.quarter == quarter),
            isouter=True,
        )
        .join(
            CheckinComment,
            and_(CheckinComment.goal_id == Goal.id, CheckinComment.quarter == quarter),
            isouter=True,
        )
        .where(Goal.cycle_id == cycle_id)
        .order_by(User.name, Goal.title)
    )
    if manager.role == UserRole.MANAGER:
        stmt = stmt.where(User.manager_id == manager.id)

    rows = (await session.execute(stmt)).all()
    return [
        TeamCheckinRow(
            employee_id=employee.id,
            employee_name=employee.name,
            goal_id=goal.id,
            goal_title=goal.title,
            quarter=quarter,
            planned_value=achievement.planned_value if achievement else None,
            actual_value=achievement.actual_value if achievement else None,
            achievement_status=achievement.status if achievement else None,
            computed_score=achievement.computed_score if achievement else None,
            manager_comment=comment.comment if comment else None,
        )
        for employee, goal, achievement, comment in rows
    ]


@router.post("/{goal_id}", response_model=CheckinCommentRead)
async def post_checkin_comment(
    goal_id: UUID,
    payload: CheckinCommentCreate,
    session: AsyncSession = Depends(get_db),
    manager: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> CheckinComment:
    goal = await session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    await ensure_manager_access(session, manager, goal.employee_id)
    await ensure_checkin_window_open(
        session,
        cycle_id=goal.cycle_id,
        quarter=payload.quarter,
        user=manager,
    )

    comment = await session.scalar(
        select(CheckinComment).where(
            CheckinComment.goal_id == goal_id,
            CheckinComment.manager_id == manager.id,
            CheckinComment.quarter == payload.quarter,
        )
    )
    if not comment:
        comment = CheckinComment(goal_id=goal_id, manager_id=manager.id, quarter=payload.quarter)
        session.add(comment)
    comment.comment = payload.comment
    await write_audit_log(
        session,
        entity_type="checkin_comment",
        entity_id=goal_id,
        action="upserted",
        changed_by=manager.id,
        new_values=payload.model_dump(),
    )
    await session.commit()
    await session.refresh(comment)
    return comment
