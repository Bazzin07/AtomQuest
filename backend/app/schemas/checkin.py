from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import GoalProgress, Quarter
from app.schemas.common import ORMModel


class CheckinCommentCreate(BaseModel):
    quarter: Quarter
    comment: str = Field(min_length=3, max_length=5000)


class CheckinCommentRead(ORMModel):
    id: UUID
    goal_id: UUID
    manager_id: UUID
    quarter: Quarter
    comment: str


class CheckinWindowRead(ORMModel):
    id: UUID
    cycle_id: UUID
    quarter: Quarter
    opens_at: date
    closes_at: date


class TeamCheckinRow(BaseModel):
    employee_id: UUID
    employee_name: str
    goal_id: UUID
    goal_title: str
    quarter: Quarter
    planned_value: Decimal | None = None
    actual_value: Decimal | None = None
    achievement_status: GoalProgress | None = None
    computed_score: Decimal | None = None
    manager_comment: str | None = None
