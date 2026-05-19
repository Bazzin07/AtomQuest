from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, IdMixin, TimestampMixin
from app.models.enums import EscalationEventType, EscalationStatus


class EscalationRule(IdMixin, TimestampMixin, Base):
    __tablename__ = "escalation_rules"
    __table_args__ = (
        UniqueConstraint("event_type", "threshold_days", "escalation_level", name="uq_escalation_rule"),
    )

    event_type: Mapped[EscalationEventType] = mapped_column(Enum(EscalationEventType), nullable=False)
    threshold_days: Mapped[int] = mapped_column(Integer, nullable=False)
    escalation_level: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class EscalationLog(IdMixin, Base):
    __tablename__ = "escalation_logs"
    __table_args__ = (
        Index(
            "uq_open_escalation_log",
            "cycle_id",
            "target_user_id",
            "rule_id",
            "event_type",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
        ),
    )

    cycle_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("goal_cycles.id"), index=True)
    target_user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    manager_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    rule_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("escalation_rules.id"))
    event_type: Mapped[EscalationEventType] = mapped_column(Enum(EscalationEventType), nullable=False)
    status: Mapped[EscalationStatus] = mapped_column(
        Enum(EscalationStatus), default=EscalationStatus.OPEN, nullable=False
    )
    detail: Mapped[str | None] = mapped_column(String(500))
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    cycle = relationship("GoalCycle")
    target_user = relationship("User", foreign_keys=[target_user_id])
    manager = relationship("User", foreign_keys=[manager_id])
    rule = relationship("EscalationRule")
