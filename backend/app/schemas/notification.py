from datetime import datetime
from uuid import UUID

from app.models.enums import NotificationChannel, NotificationDeliveryStatus, NotificationEventType
from app.schemas.common import ORMModel


class NotificationLogRead(ORMModel):
    id: UUID
    cycle_id: UUID | None = None
    goal_id: UUID | None = None
    escalation_log_id: UUID | None = None
    recipient_user_id: UUID | None = None
    recipient_email: str | None = None
    channel: NotificationChannel
    event_type: NotificationEventType
    status: NotificationDeliveryStatus
    subject: str
    detail: str | None = None
    error_message: str | None = None
    attempted_at: datetime
