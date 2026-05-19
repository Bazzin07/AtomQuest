from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import GoalProgress, Quarter


class AchievementReportRow(BaseModel):
    employee_id: UUID
    employee_name: str
    manager_id: UUID | None
    department: str | None
    goal_id: UUID
    goal_title: str
    quarter: Quarter
    planned_value: Decimal | None
    actual_value: Decimal | None
    status: GoalProgress
    computed_score: Decimal | None

class CompletionDashboardRow(BaseModel):
    employee_id: UUID
    employee_name: str
    manager_id: UUID | None
    total_goals: int
    achievements_completed: int
    manager_comments: int

