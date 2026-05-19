from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import CycleStatus, Quarter
from app.schemas.common import ORMModel


class GoalCycleCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    start_date: date
    end_date: date
    status: CycleStatus = CycleStatus.ACTIVE


class GoalCycleRead(ORMModel):
    id: UUID
    name: str
    start_date: date
    end_date: date
    status: CycleStatus


class ThrustAreaCreate(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    description: str | None = None
    cycle_id: UUID


class ThrustAreaRead(ORMModel):
    id: UUID
    name: str
    description: str | None = None
    cycle_id: UUID


class CheckinWindowCreate(BaseModel):
    cycle_id: UUID
    quarter: Quarter
    opens_at: date
    closes_at: date


class CheckinWindowUpdate(BaseModel):
    opens_at: date | None = None
    closes_at: date | None = None
