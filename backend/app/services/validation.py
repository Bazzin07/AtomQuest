from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import GoalStatus
from app.models.goal import Goal


async def validate_goal_sheet(session: AsyncSession, employee_id: UUID, cycle_id: UUID) -> None:
    stmt: Select = select(func.count(Goal.id), func.coalesce(func.sum(Goal.weightage), 0)).where(
        Goal.employee_id == employee_id,
        Goal.cycle_id == cycle_id,
        Goal.status.in_([GoalStatus.DRAFT, GoalStatus.RETURNED, GoalStatus.SUBMITTED]),
    )
    count, total_weightage = (await session.execute(stmt)).one()

    if count == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "At least one goal is required")
    if count > 8:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Maximum 8 goals allowed")
    if int(total_weightage) != 100:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Total goal weightage must equal 100")


def ensure_unlocked(goal: Goal) -> None:
    """Raise 409 if the goal is in a manager-confirmed or locked state."""
    if goal.status in {GoalStatus.APPROVED, GoalStatus.LOCKED}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Goal is approved or locked and cannot be edited by the employee. "
            "Contact your manager or admin.",
        )
