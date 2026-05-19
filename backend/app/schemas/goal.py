from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import GoalStatus, UomType
from app.schemas.common import ORMModel


class GoalCreate(BaseModel):
    cycle_id: UUID
    thrust_area_id: UUID | None = None
    title: str = Field(min_length=3, max_length=300)
    description: str | None = None
    uom_type: UomType
    target_value: Decimal | None = None
    target_date: date | None = None
    weightage: int = Field(ge=10, le=100)

    @model_validator(mode="after")
    def validate_target(self) -> "GoalCreate":
        if self.uom_type == UomType.TIMELINE and self.target_date is None:
            raise ValueError("Timeline goals require target_date")
        if self.uom_type != UomType.TIMELINE and self.target_value is None:
            raise ValueError("Numeric, percentage, and zero goals require target_value")
        return self


class GoalUpdate(BaseModel):
    thrust_area_id: UUID | None = None
    title: str | None = Field(default=None, min_length=3, max_length=300)
    description: str | None = None
    uom_type: UomType | None = None
    target_value: Decimal | None = None
    target_date: date | None = None
    weightage: int | None = Field(default=None, ge=10, le=100)


class GoalRead(ORMModel):
    id: UUID
    employee_id: UUID
    cycle_id: UUID
    thrust_area_id: UUID | None = None
    title: str
    description: str | None = None
    uom_type: UomType
    target_value: Decimal | None = None
    target_date: date | None = None
    weightage: int
    version: int
    status: GoalStatus
    is_shared: bool
    shared_source_id: UUID | None = None
    approved_at: datetime | None = None
    locked_at: datetime | None = None
    returned_reason: str | None = None


class GoalSubmitRequest(BaseModel):
    cycle_id: UUID


class GoalReturnRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class ManagerGoalEdit(BaseModel):
    target_value: Decimal | None = None
    target_date: date | None = None
    weightage: int | None = Field(default=None, ge=10, le=100)


class SharedGoalCreate(GoalCreate):
    employee_ids: list[UUID] = Field(min_length=1)
