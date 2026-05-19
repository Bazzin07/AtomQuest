from uuid import UUID

from pydantic import BaseModel

from app.models.enums import GoalProgress, GoalStatus, Quarter, UomType


class QoqAnalyticsRow(BaseModel):
    quarter: Quarter
    department: str | None
    goal_count: int
    achievement_count: int
    average_score: float | None


class QoqAnalyticsResponse(BaseModel):
    cycle_id: UUID
    rows: list[QoqAnalyticsRow]


class CompletionHeatmapRow(BaseModel):
    quarter: Quarter
    department: str | None
    total_goals: int
    achievement_updates: int
    manager_comments: int


class CompletionHeatmapResponse(BaseModel):
    cycle_id: UUID
    rows: list[CompletionHeatmapRow]


class DistributionBucket(BaseModel):
    key: str
    count: int


class DistributionResponse(BaseModel):
    cycle_id: UUID
    goal_status: list[DistributionBucket]
    progress_status: list[DistributionBucket]
    thrust_area: list[DistributionBucket]
    uom_type: list[DistributionBucket]


class ManagerEffectivenessRow(BaseModel):
    manager_id: UUID
    manager_name: str
    department: str | None
    team_members: int
    total_goals: int
    approved_goals: int
    goals_returned: int
    return_rate_percent: float
    achievement_updates: int
    manager_comments: int
    average_score: float | None
    checkin_coverage_percent: float
    approval_turnaround_avg_days: float | None
    """Average calendar days from goal submission to approval (None if no approvals yet)."""
    overdue_checkins: int
    """Count of open escalation logs of type CHECKIN_NOT_COMPLETED for this manager's team."""


class ManagerEffectivenessResponse(BaseModel):
    cycle_id: UUID
    rows: list[ManagerEffectivenessRow]


class ManagerScorecardResponse(BaseModel):
    """Per-manager deep-drill scorecard (B6)."""
    manager_id: UUID
    manager_name: str
    department: str | None
    cycle_id: UUID
    team_members: int
    total_goals: int
    approved_goals: int
    goals_returned: int
    return_rate_percent: float
    average_score: float | None
    checkin_coverage_percent: float
    approval_turnaround_avg_days: float | None
    overdue_checkins: int
    # Per-employee breakdown
    team_breakdown: list[dict]


def enum_key(value: GoalProgress | GoalStatus | Quarter | UomType | str | None) -> str:
    if value is None:
        return "UNSPECIFIED"
    return value.value if hasattr(value, "value") else str(value)
