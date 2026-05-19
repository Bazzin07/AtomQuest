from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, IdMixin
from app.models.enums import NotificationChannel, NotificationDeliveryStatus, NotificationEventType


class NotificationLog(IdMixin, Base):
    __tablename__ = "notification_logs"

    cycle_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("goal_cycles.id"), index=True)
    goal_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id"), index=True)
    escalation_log_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("escalation_logs.id"), index=True)
    recipient_user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    recipient_email: Mapped[str | None] = mapped_column(String(320))
    channel: Mapped[NotificationChannel] = mapped_column(Enum(NotificationChannel), nullable=False, index=True)
    event_type: Mapped[NotificationEventType] = mapped_column(Enum(NotificationEventType), nullable=False, index=True)
    status: Mapped[NotificationDeliveryStatus] = mapped_column(Enum(NotificationDeliveryStatus), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    cycle = relationship("GoalCycle")
    goal = relationship("Goal")
    escalation_log = relationship("EscalationLog")
    recipient_user = relationship("User")
