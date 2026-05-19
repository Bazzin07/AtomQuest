from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, IdMixin, TimestampMixin
from app.models.enums import CycleStatus, GoalStatus, UomType


class GoalCycle(IdMixin, Base):
    __tablename__ = "goal_cycles"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[CycleStatus] = mapped_column(Enum(CycleStatus), default=CycleStatus.ACTIVE)
    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ThrustArea(IdMixin, Base):
    __tablename__ = "thrust_areas"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cycle_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("goal_cycles.id"), nullable=False)


class Goal(IdMixin, TimestampMixin, Base):
    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint("weightage >= 10 AND weightage <= 100", name="ck_goal_weightage_range"),
    )

    employee_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    cycle_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("goal_cycles.id"), index=True)
    thrust_area_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("thrust_areas.id"))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    uom_type: Mapped[UomType] = mapped_column(Enum(UomType), nullable=False)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    target_date: Mapped[date | None] = mapped_column(Date)
    weightage: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[GoalStatus] = mapped_column(Enum(GoalStatus), default=GoalStatus.DRAFT)
    is_shared: Mapped[bool] = mapped_column(default=False, nullable=False)
    shared_source_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id"))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    returned_reason: Mapped[str | None] = mapped_column(Text)

    employee = relationship("User")
    cycle = relationship("GoalCycle")
    thrust_area = relationship("ThrustArea")

