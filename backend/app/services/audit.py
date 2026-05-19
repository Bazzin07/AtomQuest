"""
Audit log service.

Every state-mutating operation (goal CRUD, approvals, achievement writes)
calls ``write_audit_log`` to produce an immutable governance trail.

The ip_address field captures the caller's real IP for compliance tracing.
It is optional so the function can be called from contexts without a Request
object (e.g., background jobs, seed scripts, tests).
"""
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def write_audit_log(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: UUID,
    action: str,
    changed_by: UUID,
    old_values: dict | None = None,
    new_values: dict | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Append an immutable audit record to the current session.

    The record is written inside the caller's transaction so it is
    automatically rolled back if the parent operation fails — ensuring
    audit trail consistency with business state.

    Args:
        session:     Active SQLAlchemy async session.
        entity_type: Domain object type string (e.g., "goal", "achievement").
        entity_id:   UUID of the affected record.
        action:      Verb string (e.g., "created", "approved", "locked").
        changed_by:  UUID of the user who triggered the action.
        old_values:  Snapshot of fields before the change (optional).
        new_values:  Snapshot of fields after the change (optional).
        reason:      Human-readable explanation (e.g., return reason).
        ip_address:  Caller's IP from ``request.client.host`` (optional).
    """
    session.add(
        AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changed_by=changed_by,
            old_values=jsonable_encoder(old_values) if old_values is not None else None,
            new_values=jsonable_encoder(new_values) if new_values is not None else None,
            reason=reason,
            ip_address=ip_address,
        )
    )
