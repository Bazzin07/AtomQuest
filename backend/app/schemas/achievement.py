from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import GoalProgress, Quarter
from app.schemas.common import ORMModel


class AchievementUpsert(BaseModel):
    quarter: Quarter
    planned_value: Decimal | None = None
    actual_value: Decimal | None = None
    completion_date: date | None = None
    status: GoalProgress = GoalProgress.NOT_STARTED


class AchievementRead(ORMModel):
    id: UUID
    goal_id: UUID
    quarter: Quarter
    planned_value: Decimal | None = None
    actual_value: Decimal | None = None
    completion_date: date | None = None
    status: GoalProgress
    computed_score: Decimal | None = None

