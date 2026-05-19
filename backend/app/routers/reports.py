import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from openpyxl import Workbook
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_redis, require_role
from app.models.achievement import GoalAchievement
from app.models.checkin import CheckinComment
from app.models.enums import UserRole
from app.models.goal import Goal
from app.models.user import User
from app.services.cache import JsonCache

router = APIRouter(prefix="/reports", tags=["reports"])

_REPORT_CACHE_TTL = 600  # 10 minutes


@router.get("/achievement")
async def achievement_report(
    cycle_id: UUID,
    format: str = "csv",
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> Response:
    rows = (
        await session.execute(
            select(User, Goal, GoalAchievement)
            .join(Goal, Goal.employee_id == User.id)
            .join(GoalAchievement, GoalAchievement.goal_id == Goal.id, isouter=True)
            .where(Goal.cycle_id == cycle_id)
            .order_by(User.name, Goal.title)
        )
    ).all()

    headers = [
        "employee",
        "department",
        "goal_title",
        "quarter",
        "planned_value",
        "actual_value",
        "status",
        "computed_score",
    ]
    report_rows = [
        [
            employee.name,
            employee.department,
            goal.title,
            achievement.quarter if achievement else "",
            achievement.planned_value if achievement else "",
            achievement.actual_value if achievement else "",
            achievement.status if achievement else "",
            achievement.computed_score if achievement else "",
        ]
        for employee, goal, achievement in rows
    ]

    if format == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Achievement Report"
        sheet.append(headers)
        for row in report_rows:
            sheet.append([str(value) if value is not None else "" for value in row])
        output = io.BytesIO()
        workbook.save(output)
        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=achievement_report.xlsx"},
        )

    if format != "csv":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "format must be csv or xlsx")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(report_rows)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=achievement_report.csv"},
    )


@router.get("/completion")
async def completion_dashboard(
    cycle_id: UUID,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> list[dict]:
    """Completion dashboard with Redis cache (10-min TTL)."""
    cache = JsonCache(redis, ttl_seconds=_REPORT_CACHE_TTL)
    cache_key = f"report:completion:{cycle_id}"

    cached = await cache.get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    rows = (
        await session.execute(
            select(
                User.id,
                User.name,
                User.manager_id,
                func.count(func.distinct(Goal.id)).label("total_goals"),
                func.count(func.distinct(GoalAchievement.id)).label("achievement_updates"),
                func.count(func.distinct(CheckinComment.id)).label("manager_comments"),
            )
            .join(Goal, Goal.employee_id == User.id)
            .join(GoalAchievement, GoalAchievement.goal_id == Goal.id, isouter=True)
            .join(CheckinComment, CheckinComment.goal_id == Goal.id, isouter=True)
            .where(Goal.cycle_id == cycle_id)
            .group_by(User.id, User.name, User.manager_id)
        )
    ).mappings().all()
    result = [dict(row) for row in rows]
    await cache.set(cache_key, result)
    return result
