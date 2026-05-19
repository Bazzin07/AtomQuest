from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin
from app.models.enums import GoalProgress, Quarter


class GoalAchievement(IdMixin, TimestampMixin, Base):
    __tablename__ = "goal_achievements"
    __table_args__ = (UniqueConstraint("goal_id", "quarter", name="uq_achievement_goal_quarter"),)

    goal_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id"), index=True)
    quarter: Mapped[Quarter] = mapped_column(Enum(Quarter), nullable=False)
    planned_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    actual_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    completion_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[GoalProgress] = mapped_column(Enum(GoalProgress), default=GoalProgress.NOT_STARTED)
    computed_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    goal = relationship("Goal")

