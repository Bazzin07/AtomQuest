from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.achievement import GoalAchievement
from app.models.checkin import CheckinComment, CheckinWindow
from app.models.enums import EscalationEventType, EscalationStatus, GoalStatus, UserRole
from app.models.escalation import EscalationLog, EscalationRule
from app.models.goal import Goal, GoalCycle
from app.models.user import User


@dataclass
class EscalationEvaluation:
    evaluated_rules: int
    created_logs: int
    existing_open_logs: int
    skipped_inactive_or_not_due: int
    logs: list[EscalationLog]


def escalation_key(
    *, cycle_id: UUID, target_user_id: UUID, rule_id: UUID, event_type: EscalationEventType
) -> tuple[UUID, UUID, UUID, EscalationEventType]:
    return (cycle_id, target_user_id, rule_id, event_type)


def escalation_log_visible_to(user: User, log: EscalationLog) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    return user.role == UserRole.MANAGER and log.manager_id == user.id


async def _existing_open_keys(
    session: AsyncSession, *, cycle_id: UUID
) -> set[tuple[UUID, UUID, UUID, EscalationEventType]]:
    rows = (
        await session.execute(
            select(
                EscalationLog.cycle_id,
                EscalationLog.target_user_id,
                EscalationLog.rule_id,
                EscalationLog.event_type,
            ).where(EscalationLog.cycle_id == cycle_id, EscalationLog.status == EscalationStatus.OPEN)
        )
    ).all()
    return {
        escalation_key(
            cycle_id=cycle_id,
            target_user_id=target_user_id,
            rule_id=rule_id,
            event_type=event_type,
        )
        for cycle_id, target_user_id, rule_id, event_type in rows
    }


async def evaluate_escalations(
    session: AsyncSession, *, cycle_id: UUID, as_of: date | None = None
) -> EscalationEvaluation:
    cycle = await session.get(GoalCycle, cycle_id)
    if not cycle:
        raise ValueError("Cycle not found")

    as_of = as_of or datetime.now(UTC).date()
    rules = (
        await session.scalars(
            select(EscalationRule).where(EscalationRule.is_active.is_(True)).order_by(
                EscalationRule.event_type, EscalationRule.escalation_level
            )
        )
    ).all()
    existing_keys = await _existing_open_keys(session, cycle_id=cycle_id)
    known_keys = set(existing_keys)
    created: list[EscalationLog] = []
    skipped = 0

    employee_rows = (
        await session.execute(
            select(User.id, User.manager_id).where(
                User.role == UserRole.EMPLOYEE,
                User.is_active.is_(True),
            )
        )
    ).all()

    submitted_employee_ids = set(
        await session.scalars(
            select(Goal.employee_id)
            .where(Goal.cycle_id == cycle_id, Goal.status.in_([GoalStatus.SUBMITTED, GoalStatus.LOCKED]))
            .distinct()
        )
    )

    submitted_goals = (
        await session.execute(
            select(Goal.employee_id, User.manager_id, Goal.updated_at, Goal.title)
            .join(User, Goal.employee_id == User.id)
            .where(Goal.cycle_id == cycle_id, Goal.status == GoalStatus.SUBMITTED)
        )
    ).all()

    checkin_candidates_by_threshold: dict[int, list[tuple[UUID, UUID | None, str]]] = {}

    def add_log(
        *,
        rule: EscalationRule,
        target_user_id: UUID,
        manager_id: UUID | None,
        detail: str,
    ) -> None:
        key = escalation_key(
            cycle_id=cycle_id,
            target_user_id=target_user_id,
            rule_id=rule.id,
            event_type=rule.event_type,
        )
        if key in known_keys:
            return
        known_keys.add(key)
        log = EscalationLog(
            cycle_id=cycle_id,
            target_user_id=target_user_id,
            manager_id=manager_id,
            rule_id=rule.id,
            event_type=rule.event_type,
            status=EscalationStatus.OPEN,
            detail=detail,
        )
        session.add(log)
        created.append(log)

    for rule in rules:
        due_date = cycle.start_date + timedelta(days=rule.threshold_days)
        if rule.event_type == EscalationEventType.GOALS_NOT_SUBMITTED:
            if due_date > as_of:
                skipped += 1
                continue
            for employee_id, manager_id in employee_rows:
                if employee_id not in submitted_employee_ids:
                    add_log(
                        rule=rule,
                        target_user_id=employee_id,
                        manager_id=manager_id,
                        detail="Goal sheet has not been submitted for the cycle.",
                    )
            continue

        if rule.event_type == EscalationEventType.MANAGER_NOT_APPROVED:
            created_before = as_of - timedelta(days=rule.threshold_days)
            matched = False
            for employee_id, manager_id, updated_at, goal_title in submitted_goals:
                if updated_at and updated_at.date() <= created_before:
                    matched = True
                    add_log(
                        rule=rule,
                        target_user_id=employee_id,
                        manager_id=manager_id,
                        detail=f"Submitted goal awaits manager approval: {goal_title}",
                    )
            if not matched:
                skipped += 1
            continue

        if rule.event_type == EscalationEventType.CHECKIN_NOT_COMPLETED:
            if rule.threshold_days not in checkin_candidates_by_threshold:
                checkin_candidates_by_threshold[rule.threshold_days] = await _checkin_candidates(
                    session,
                    cycle_id=cycle_id,
                    as_of=as_of,
                    threshold_days=rule.threshold_days,
                )
            candidates = checkin_candidates_by_threshold[rule.threshold_days]
            if not candidates:
                skipped += 1
                continue
            for employee_id, manager_id, detail in candidates:
                add_log(
                    rule=rule,
                    target_user_id=employee_id,
                    manager_id=manager_id,
                    detail=detail,
                )

    await session.flush()
    return EscalationEvaluation(
        evaluated_rules=len(rules),
        created_logs=len(created),
        existing_open_logs=len(existing_keys),
        skipped_inactive_or_not_due=skipped,
        logs=created,
    )


async def _checkin_candidates(
    session: AsyncSession, *, cycle_id: UUID, as_of: date, threshold_days: int
) -> list[tuple[UUID, UUID | None, str]]:
    windows = (
        await session.scalars(select(CheckinWindow).where(CheckinWindow.cycle_id == cycle_id))
    ).all()
    due_windows = [
        window for window in windows if window.closes_at + timedelta(days=threshold_days) <= as_of
    ]
    candidates: list[tuple[UUID, UUID | None, str]] = []
    for window in due_windows:
        rows = (
            await session.execute(
                select(Goal.employee_id, User.manager_id, Goal.title)
                .join(User, Goal.employee_id == User.id)
                .join(
                    GoalAchievement,
                    and_(
                        GoalAchievement.goal_id == Goal.id,
                        GoalAchievement.quarter == window.quarter,
                    ),
                    isouter=True,
                )
                .join(
                    CheckinComment,
                    and_(
                        CheckinComment.goal_id == Goal.id,
                        CheckinComment.quarter == window.quarter,
                    ),
                    isouter=True,
                )
                .where(
                    Goal.cycle_id == cycle_id,
                    Goal.status == GoalStatus.LOCKED,
                    or_(GoalAchievement.id.is_(None), CheckinComment.id.is_(None)),
                )
            )
        ).all()
        for employee_id, manager_id, goal_title in rows:
            candidates.append(
                (
                    employee_id,
                    manager_id,
                    f"{window.quarter} check-in is incomplete for goal: {goal_title}",
                )
            )
    return candidates
