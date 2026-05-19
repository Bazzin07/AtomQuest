from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_role
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/team", response_model=list[UserRead])
async def team_users(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> list[User]:
    stmt = (
        select(User)
        .where(User.role == UserRole.EMPLOYEE, User.is_active.is_(True))
        .order_by(User.name)
    )
    if user.role == UserRole.MANAGER:
        stmt = stmt.where(User.manager_id == user.id)
    return list((await session.scalars(stmt)).all())
