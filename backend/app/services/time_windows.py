from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkin import CheckinWindow
from app.models.enums import Quarter
from app.models.user import User
from app.models.enums import UserRole


async def ensure_checkin_window_open(
    session: AsyncSession,
    *,
    cycle_id: UUID,
    quarter: Quarter,
    user: User,
    today: date | None = None,
) -> None:
    if user.role == UserRole.ADMIN:
        return

    window = await session.scalar(
        select(CheckinWindow).where(
            CheckinWindow.cycle_id == cycle_id,
            CheckinWindow.quarter == quarter,
        )
    )
    if not window:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Check-in window is not configured")

    current_date = today or datetime.now(UTC).date()
    if not window.opens_at <= current_date <= window.closes_at:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Check-in window is not active")
