from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import EscalationEventType, EscalationStatus
from app.schemas.common import ORMModel


class EscalationRuleCreate(BaseModel):
    event_type: EscalationEventType
    threshold_days: int = Field(ge=0, le=365)
    escalation_level: int = Field(ge=1, le=5)
    is_active: bool = True
    description: str | None = Field(default=None, max_length=1000)


class EscalationRuleUpdate(BaseModel):
    threshold_days: int | None = Field(default=None, ge=0, le=365)
    escalation_level: int | None = Field(default=None, ge=1, le=5)
    is_active: bool | None = None
    description: str | None = Field(default=None, max_length=1000)


class EscalationRuleRead(ORMModel):
    id: UUID
    event_type: EscalationEventType
    threshold_days: int
    escalation_level: int
    is_active: bool
    description: str | None
    created_at: datetime
    updated_at: datetime


class EscalationLogRead(ORMModel):
    id: UUID
    cycle_id: UUID
    target_user_id: UUID
    manager_id: UUID | None
    rule_id: UUID
    event_type: EscalationEventType
    status: EscalationStatus
    detail: str | None
    triggered_at: datetime
    resolved_at: datetime | None
    resolved_by: UUID | None


class EscalationEvaluationResult(BaseModel):
    cycle_id: UUID
    evaluated_rules: int
    created_logs: int
    existing_open_logs: int
    skipped_inactive_or_not_due: int
    logs: list[EscalationLogRead]
