from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin
from app.models.enums import Quarter


class CheckinWindow(IdMixin, Base):
    __tablename__ = "checkin_windows"
    __table_args__ = (UniqueConstraint("cycle_id", "quarter", name="uq_checkin_window_cycle_quarter"),)

    cycle_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("goal_cycles.id"))
    quarter: Mapped[Quarter] = mapped_column(Enum(Quarter), nullable=False)
    opens_at: Mapped[date] = mapped_column(Date, nullable=False)
    closes_at: Mapped[date] = mapped_column(Date, nullable=False)


class CheckinComment(IdMixin, TimestampMixin, Base):
    __tablename__ = "checkin_comments"
    __table_args__ = (UniqueConstraint("goal_id", "manager_id", "quarter", name="uq_checkin_comment"),)

    goal_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id"))
    manager_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    quarter: Mapped[Quarter] = mapped_column(Enum(Quarter), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)

    goal = relationship("Goal")
    manager = relationship("User")

