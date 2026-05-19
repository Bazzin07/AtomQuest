from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_role
from app.models.audit import AuditLog
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.audit import AuditLogRead

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogRead])
async def list_audit_logs(
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    page: int = 1,
    size: int = 50,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.ADMIN)),
) -> list[AuditLogRead]:
    page = max(page, 1)
    size = min(max(size, 1), 200)
    stmt = (
        select(AuditLog, User.name)
        .join(User, AuditLog.changed_by == User.id)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    rows = (await session.execute(stmt)).all()
    return [
        AuditLogRead(
            id=audit.id,
            entity_type=audit.entity_type,
            entity_id=audit.entity_id,
            action=audit.action,
            changed_by=audit.changed_by,
            changed_by_name=changed_by_name,
            old_values=audit.old_values,
            new_values=audit.new_values,
            reason=audit.reason,
            created_at=audit.created_at,
        )
        for audit, changed_by_name in rows
    ]
