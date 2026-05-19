from datetime import datetime
from uuid import UUID

from app.schemas.common import ORMModel


class AuditLogRead(ORMModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    changed_by: UUID
    changed_by_name: str | None = None
    old_values: dict | None = None
    new_values: dict | None = None
    reason: str | None = None
    created_at: datetime
