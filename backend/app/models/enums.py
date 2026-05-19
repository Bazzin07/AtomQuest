from enum import StrEnum


class UserRole(StrEnum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


class GoalStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"   # Manager approved; awaiting final sheet lock
    RETURNED = "RETURNED"
    LOCKED = "LOCKED"       # Admin/system final lock; immutable for reporting


class UomType(StrEnum):
    NUMERIC_MIN = "NUMERIC_MIN"
    NUMERIC_MAX = "NUMERIC_MAX"
    PERCENTAGE_MIN = "PERCENTAGE_MIN"
    PERCENTAGE_MAX = "PERCENTAGE_MAX"
    TIMELINE = "TIMELINE"
    ZERO = "ZERO"


class Quarter(StrEnum):
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


class GoalProgress(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    ON_TRACK = "ON_TRACK"
    COMPLETED = "COMPLETED"


class CycleStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class EscalationEventType(StrEnum):
    GOALS_NOT_SUBMITTED = "GOALS_NOT_SUBMITTED"
    MANAGER_NOT_APPROVED = "MANAGER_NOT_APPROVED"
    CHECKIN_NOT_COMPLETED = "CHECKIN_NOT_COMPLETED"


class EscalationStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class NotificationChannel(StrEnum):
    EMAIL = "EMAIL"
    TEAMS = "TEAMS"


class NotificationEventType(StrEnum):
    GOAL_SUBMITTED = "GOAL_SUBMITTED"
    GOAL_APPROVED = "GOAL_APPROVED"
    GOAL_RETURNED = "GOAL_RETURNED"
    GOAL_LOCKED = "GOAL_LOCKED"
    ESCALATION_RAISED = "ESCALATION_RAISED"


class NotificationDeliveryStatus(StrEnum):
    SENT = "SENT"
    SKIPPED_NOT_CONFIGURED = "SKIPPED_NOT_CONFIGURED"
    FAILED = "FAILED"
