from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import ensure_manager_access, get_current_user, get_db
from app.models.achievement import GoalAchievement
from app.models.goal import Goal
from app.models.user import User
from app.schemas.achievement import AchievementRead, AchievementUpsert
from app.services.audit import write_audit_log
from app.services.time_windows import ensure_checkin_window_open
from app.utils.scoring import compute_progress_score

router = APIRouter(prefix="/achievements", tags=["achievements"])


@router.get("", response_model=list[AchievementRead])
async def list_achievements(
    goal_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[GoalAchievement]:
    goal = await session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    if goal.employee_id != user.id:
        await ensure_manager_access(session, user, goal.employee_id)
    return list(
        (
            await session.scalars(
                select(GoalAchievement).where(GoalAchievement.goal_id == goal_id)
            )
        ).all()
    )


@router.put("/{goal_id}", response_model=AchievementRead)
async def upsert_achievement(
    goal_id: UUID,
    payload: AchievementUpsert,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GoalAchievement:
    goal = await session.get(Goal, goal_id)
    if not goal or goal.employee_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    await ensure_checkin_window_open(
        session,
        cycle_id=goal.cycle_id,
        quarter=payload.quarter,
        user=user,
    )

    achievement = await session.scalar(
        select(GoalAchievement).where(
            GoalAchievement.goal_id == goal_id,
            GoalAchievement.quarter == payload.quarter,
        )
    )
    if not achievement:
        achievement = GoalAchievement(goal_id=goal_id, quarter=payload.quarter)
        session.add(achievement)

    achievement_values = payload.model_dump(exclude={"quarter"})
    for key, value in achievement_values.items():
        setattr(achievement, key, value)
    achievement.computed_score = compute_progress_score(
        goal.uom_type,
        goal.target_value,
        achievement.actual_value,
        goal.target_date,
        achievement.completion_date,
    )
    await write_audit_log(
        session,
        entity_type="achievement",
        entity_id=goal_id,
        action="upserted",
        changed_by=user.id,
        new_values=payload.model_dump(mode="json"),
        ip_address=request.client.host if request.client else None,
    )

    if goal.is_shared and goal.shared_source_id is None:
        linked_goals = (
            await session.scalars(select(Goal).where(Goal.shared_source_id == goal.id))
        ).all()
        for linked_goal in linked_goals:
            linked_achievement = await session.scalar(
                select(GoalAchievement).where(
                    GoalAchievement.goal_id == linked_goal.id,
                    GoalAchievement.quarter == payload.quarter,
                )
            )
            if not linked_achievement:
                linked_achievement = GoalAchievement(goal_id=linked_goal.id, quarter=payload.quarter)
                session.add(linked_achievement)
            for key, value in achievement_values.items():
                setattr(linked_achievement, key, value)
            linked_achievement.computed_score = achievement.computed_score

    await session.commit()
    await session.refresh(achievement)
    return achievement
