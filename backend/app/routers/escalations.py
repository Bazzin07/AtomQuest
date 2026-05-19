from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_role
from app.models.enums import EscalationStatus, UserRole
from app.models.escalation import EscalationLog, EscalationRule
from app.models.user import User
from app.schemas.escalation import (
    EscalationEvaluationResult,
    EscalationLogRead,
    EscalationRuleCreate,
    EscalationRuleRead,
    EscalationRuleUpdate,
)
from app.services.audit import write_audit_log
from app.services.escalation import evaluate_escalations
from app.services.notification import notify_escalation

router = APIRouter(prefix="/escalations", tags=["escalations"])


@router.get("/rules", response_model=list[EscalationRuleRead])
async def list_rules(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> list[EscalationRule]:
    return list(
        await session.scalars(
            select(EscalationRule).order_by(EscalationRule.event_type, EscalationRule.escalation_level)
        )
    )


@router.post("/rules", response_model=EscalationRuleRead, status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: EscalationRuleCreate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> EscalationRule:
    existing = await session.scalar(
        select(EscalationRule).where(
            EscalationRule.event_type == payload.event_type,
            EscalationRule.threshold_days == payload.threshold_days,
            EscalationRule.escalation_level == payload.escalation_level,
        )
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Matching escalation rule already exists")
    rule = EscalationRule(**payload.model_dump())
    session.add(rule)
    await session.flush()
    await write_audit_log(
        session,
        entity_type="escalation_rule",
        entity_id=rule.id,
        action="created",
        changed_by=admin.id,
        new_values=payload.model_dump(),
    )
    await session.commit()
    await session.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=EscalationRuleRead)
async def update_rule(
    rule_id: UUID,
    payload: EscalationRuleUpdate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> EscalationRule:
    rule = await session.get(EscalationRule, rule_id)
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Escalation rule not found")
    old_values = {
        "threshold_days": rule.threshold_days,
        "escalation_level": rule.escalation_level,
        "is_active": rule.is_active,
        "description": rule.description,
    }
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(rule, field, value)
    await write_audit_log(
        session,
        entity_type="escalation_rule",
        entity_id=rule.id,
        action="updated",
        changed_by=admin.id,
        old_values=old_values,
        new_values=updates,
    )
    await session.commit()
    await session.refresh(rule)
    return rule


@router.post("/evaluate", response_model=EscalationEvaluationResult)
async def evaluate(
    cycle_id: UUID,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> EscalationEvaluationResult:
    try:
        result = await evaluate_escalations(session, cycle_id=cycle_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    for log in result.logs:
        await write_audit_log(
            session,
            entity_type="escalation_log",
            entity_id=log.id,
            action="created",
            changed_by=admin.id,
            new_values={
                "cycle_id": log.cycle_id,
                "target_user_id": log.target_user_id,
                "manager_id": log.manager_id,
                "rule_id": log.rule_id,
                "event_type": log.event_type,
            },
        )
    await session.commit()
    for log in result.logs:
        await session.refresh(log)

    # Fire escalation notifications (fire-and-forget)
    for log in result.logs:
        try:
            target = await session.get(__import__("app.models.user", fromlist=["User"]).User, log.target_user_id)
            mgr = await session.get(__import__("app.models.user", fromlist=["User"]).User, log.manager_id) if log.manager_id else None
            rule = await session.get(__import__("app.models.escalation", fromlist=["EscalationRule"]).EscalationRule, log.rule_id)
            cycle = await session.get(__import__("app.models.goal", fromlist=["GoalCycle"]).GoalCycle, log.cycle_id)
            recipient = mgr or admin
            await notify_escalation(
                cycle_id=log.cycle_id,
                escalation_log_id=log.id,
                recipient_email=recipient.email,
                recipient_user_id=recipient.id,
                recipient_name=recipient.name,
                target_name=target.name if target else str(log.target_user_id),
                cycle_name=cycle.name if cycle else str(log.cycle_id),
                event_type=log.event_type.value if hasattr(log.event_type, "value") else str(log.event_type),
                threshold_days=rule.threshold_days if rule else 0,
                escalation_level=rule.escalation_level if rule else 1,
                detail=log.detail or "",
            )
        except Exception:  # noqa: BLE001
            pass

    return EscalationEvaluationResult(
        cycle_id=cycle_id,
        evaluated_rules=result.evaluated_rules,
        created_logs=result.created_logs,
        existing_open_logs=result.existing_open_logs,
        skipped_inactive_or_not_due=result.skipped_inactive_or_not_due,
        logs=result.logs,
    )


@router.get("/logs", response_model=list[EscalationLogRead])
async def list_logs(
    cycle_id: UUID | None = None,
    status_filter: EscalationStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
) -> list[EscalationLog]:
    stmt = select(EscalationLog).order_by(EscalationLog.triggered_at.desc()).limit(limit).offset(offset)
    if cycle_id:
        stmt = stmt.where(EscalationLog.cycle_id == cycle_id)
    if status_filter:
        stmt = stmt.where(EscalationLog.status == status_filter)
    if user.role == UserRole.MANAGER:
        stmt = stmt.where(EscalationLog.manager_id == user.id)
    return list(await session.scalars(stmt))


@router.patch("/logs/{log_id}/resolve", response_model=EscalationLogRead)
async def resolve_log(
    log_id: UUID,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> EscalationLog:
    log = await session.get(EscalationLog, log_id)
    if not log:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Escalation log not found")
    if log.status == EscalationStatus.RESOLVED:
        return log
    log.status = EscalationStatus.RESOLVED
    log.resolved_at = datetime.now(UTC)
    log.resolved_by = admin.id
    await write_audit_log(
        session,
        entity_type="escalation_log",
        entity_id=log.id,
        action="resolved",
        changed_by=admin.id,
        old_values={"status": EscalationStatus.OPEN},
        new_values={"status": EscalationStatus.RESOLVED, "resolved_by": admin.id},
    )
    await session.commit()
    await session.refresh(log)
    return log
