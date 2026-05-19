import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.database import async_session_factory, init_db
from app.models.achievement import GoalAchievement
from app.models.audit import AuditLog
from app.models.checkin import CheckinComment, CheckinWindow
from app.models.enums import (
    CycleStatus,
    EscalationEventType,
    EscalationStatus,
    GoalProgress,
    GoalStatus,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationEventType,
    Quarter,
    UomType,
    UserRole,
)
from app.models.escalation import EscalationLog, EscalationRule
from app.models.goal import Goal, GoalCycle, ThrustArea
from app.models.notification import NotificationLog
from app.models.user import User
from app.services.audit import write_audit_log
from app.services.security import hash_password
from app.utils.scoring import compute_progress_score


async def seed() -> None:
    await init_db()
    async with async_session_factory() as session:
        admin = await _get_or_create_user(
            session,
            email="admin@atomquest.app",
            password="Admin@123",
            name="Anika HR",
            role=UserRole.ADMIN,
            department="HR",
        )
        maya = await _get_or_create_user(
            session,
            email="manager@atomquest.app",
            password="Manager@123",
            name="Maya Manager",
            role=UserRole.MANAGER,
            department="Sales",
        )
        rohan = await _get_or_create_user(
            session,
            email="manager.ops@atomquest.app",
            password="Manager@123",
            name="Rohan Ops",
            role=UserRole.MANAGER,
            department="Operations",
        )
        await session.flush()

        eshan = await _get_or_create_user(
            session,
            email="employee@atomquest.app",
            password="Employee@123",
            name="Eshan Employee",
            role=UserRole.EMPLOYEE,
            department="Sales",
            manager_id=maya.id,
        )
        priya = await _get_or_create_user(
            session,
            email="priya.singh@atomquest.app",
            password="Employee@123",
            name="Priya Singh",
            role=UserRole.EMPLOYEE,
            department="Sales",
            manager_id=maya.id,
        )
        omar = await _get_or_create_user(
            session,
            email="omar.khan@atomquest.app",
            password="Employee@123",
            name="Omar Khan",
            role=UserRole.EMPLOYEE,
            department="Operations",
            manager_id=maya.id,
        )
        dev = await _get_or_create_user(
            session,
            email="dev.malhotra@atomquest.app",
            password="Employee@123",
            name="Dev Malhotra",
            role=UserRole.EMPLOYEE,
            department="Growth",
            manager_id=rohan.id,
        )
        nina = await _get_or_create_user(
            session,
            email="nina.joseph@atomquest.app",
            password="Employee@123",
            name="Nina Joseph",
            role=UserRole.EMPLOYEE,
            department="Customer Success",
            manager_id=rohan.id,
        )
        await session.flush()

        previous_cycle = await _get_or_create_cycle(
            session,
            name="FY 2025 Goal Cycle",
            start_date=date(2025, 5, 1),
            end_date=date(2026, 4, 30),
            status=CycleStatus.CLOSED,
            created_by=admin.id,
        )
        cycle = await _get_or_create_cycle(
            session,
            name="FY 2026 Goal Cycle",
            start_date=date(2026, 5, 1),
            end_date=date(2027, 4, 30),
            status=CycleStatus.ACTIVE,
            created_by=admin.id,
        )
        await _normalize_active_cycle(session, keep_cycle_id=cycle.id)

        thrust_areas = {
            "Revenue Growth": await _get_or_create_thrust_area(
                session,
                cycle_id=cycle.id,
                name="Revenue Growth",
                description="Top-line expansion and sell-through performance.",
            ),
            "Customer Experience": await _get_or_create_thrust_area(
                session,
                cycle_id=cycle.id,
                name="Customer Experience",
                description="Retention, service quality, and satisfaction health.",
            ),
            "Operational Excellence": await _get_or_create_thrust_area(
                session,
                cycle_id=cycle.id,
                name="Operational Excellence",
                description="Cycle-time, quality, and governance improvements.",
            ),
            "Capability Building": await _get_or_create_thrust_area(
                session,
                cycle_id=cycle.id,
                name="Capability Building",
                description="Routines, training, and execution cadence.",
            ),
        }

        windows = {
            Quarter.Q1: await _upsert_checkin_window(
                session,
                cycle_id=cycle.id,
                quarter=Quarter.Q1,
                opens_at=date(2026, 7, 1),
                closes_at=date(2026, 7, 31),
            ),
            Quarter.Q2: await _upsert_checkin_window(
                session,
                cycle_id=cycle.id,
                quarter=Quarter.Q2,
                opens_at=date(2026, 10, 1),
                closes_at=date(2026, 10, 31),
            ),
            Quarter.Q3: await _upsert_checkin_window(
                session,
                cycle_id=cycle.id,
                quarter=Quarter.Q3,
                opens_at=date(2027, 1, 1),
                closes_at=date(2027, 1, 31),
            ),
            Quarter.Q4: await _upsert_checkin_window(
                session,
                cycle_id=cycle.id,
                quarter=Quarter.Q4,
                opens_at=date(2027, 3, 1),
                closes_at=date(2027, 4, 30),
            ),
        }
        _ = previous_cycle, windows

        goal_submission_rule = await _get_or_create_rule(
            session,
            event_type=EscalationEventType.GOALS_NOT_SUBMITTED,
            threshold_days=7,
            escalation_level=1,
            description="Escalate employees who have not submitted their goal sheet one week into the cycle.",
        )
        manager_approval_rule = await _get_or_create_rule(
            session,
            event_type=EscalationEventType.MANAGER_NOT_APPROVED,
            threshold_days=3,
            escalation_level=1,
            description="Escalate submitted goals that have not been approved within three days.",
        )
        checkin_rule = await _get_or_create_rule(
            session,
            event_type=EscalationEventType.CHECKIN_NOT_COMPLETED,
            threshold_days=5,
            escalation_level=1,
            description="Escalate incomplete quarterly updates after the review window closes.",
        )

        eshan_goals = [
            await _upsert_goal(
                session,
                employee_id=eshan.id,
                cycle_id=cycle.id,
                thrust_area_id=thrust_areas["Revenue Growth"].id,
                title="Increase renewal pipeline coverage",
                description="Build healthier renewal coverage across the top 20 accounts.",
                uom_type=UomType.NUMERIC_MAX,
                target_value=Decimal("35"),
                target_date=None,
                weightage=30,
                status=GoalStatus.DRAFT,
            ),
            await _upsert_goal(
                session,
                employee_id=eshan.id,
                cycle_id=cycle.id,
                thrust_area_id=thrust_areas["Customer Experience"].id,
                title="Lift NPS for strategic accounts",
                description="Improve relationship quality and executive sentiment.",
                uom_type=UomType.PERCENTAGE_MAX,
                target_value=Decimal("70"),
                target_date=None,
                weightage=25,
                status=GoalStatus.RETURNED,
                returned_reason="Clarify the quarterly plan and make the target more explicit.",
            ),
            await _upsert_goal(
                session,
                employee_id=eshan.id,
                cycle_id=cycle.id,
                thrust_area_id=thrust_areas["Operational Excellence"].id,
                title="Reduce proposal turnaround time",
                description="Shorten the average sales proposal response cycle.",
                uom_type=UomType.NUMERIC_MIN,
                target_value=Decimal("3"),
                target_date=None,
                weightage=20,
                status=GoalStatus.DRAFT,
            ),
            await _upsert_goal(
                session,
                employee_id=eshan.id,
                cycle_id=cycle.id,
                thrust_area_id=thrust_areas["Capability Building"].id,
                title="Launch monthly account review cadence",
                description="Stand up a repeatable review mechanism with account owners and managers.",
                uom_type=UomType.TIMELINE,
                target_value=None,
                target_date=date(2027, 1, 31),
                weightage=25,
                status=GoalStatus.DRAFT,
            ),
        ]

        priya_goals = [
            await _upsert_goal(
                session,
                employee_id=priya.id,
                cycle_id=cycle.id,
                thrust_area_id=thrust_areas["Revenue Growth"].id,
                title="Quarterly upsell bookings",
                description="Drive incremental expansion bookings from the installed base.",
                uom_type=UomType.NUMERIC_MAX,
                target_value=Decimal("18"),
                target_date=None,
                weightage=40,
                status=GoalStatus.SUBMITTED,
                updated_at=datetime(2026, 5, 10, 9, 0, tzinfo=UTC),
            ),
            await _upsert_goal(
                session,
                employee_id=priya.id,
                cycle_id=cycle.id,
                thrust_area_id=thrust_areas["Revenue Growth"].id,
                title="Improve expansion win rate",
                description="Increase close rate for qualified expansion opportunities.",
                uom_type=UomType.PERCENTAGE_MAX,
                target_value=Decimal("32"),
                target_date=None,
                weightage=30,
                status=GoalStatus.SUBMITTED,
                updated_at=datetime(2026, 5, 10, 9, 5, tzinfo=UTC),
            ),
            await _upsert_goal(
                session,
                employee_id=priya.id,
                cycle_id=cycle.id,
                thrust_area_id=thrust_areas["Customer Experience"].id,
                title="Improve executive sponsor coverage",
                description="Maintain active sponsor alignment on the largest renewals.",
                uom_type=UomType.PERCENTAGE_MAX,
                target_value=Decimal("90"),
                target_date=None,
                weightage=30,
                status=GoalStatus.SUBMITTED,
                updated_at=datetime(2026, 5, 10, 9, 10, tzinfo=UTC),
            ),
        ]

        shared_source = await _upsert_goal(
            session,
            employee_id=omar.id,
            cycle_id=cycle.id,
            thrust_area_id=thrust_areas["Revenue Growth"].id,
            title="Shared KPI: Cross-sell conversion",
            description="Lift shared conversion on sourced cross-sell opportunities.",
            uom_type=UomType.PERCENTAGE_MAX,
            target_value=Decimal("14"),
            target_date=None,
            weightage=30,
            status=GoalStatus.LOCKED,
            is_shared=True,
            shared_source_id=None,
            approved_at=datetime(2026, 5, 8, 11, 0, tzinfo=UTC),
            locked_at=datetime(2026, 5, 9, 15, 0, tzinfo=UTC),
            updated_at=datetime(2026, 5, 9, 15, 0, tzinfo=UTC),
        )

        omar_locked = await _upsert_goal(
            session,
            employee_id=omar.id,
            cycle_id=cycle.id,
            thrust_area_id=thrust_areas["Operational Excellence"].id,
            title="Reduce onboarding cycle time",
            description="Drive down elapsed days from signature to production-ready onboarding.",
            uom_type=UomType.NUMERIC_MIN,
            target_value=Decimal("10"),
            target_date=None,
            weightage=40,
            status=GoalStatus.LOCKED,
            approved_at=datetime(2026, 5, 8, 11, 10, tzinfo=UTC),
            locked_at=datetime(2026, 5, 9, 15, 10, tzinfo=UTC),
            updated_at=datetime(2026, 5, 9, 15, 10, tzinfo=UTC),
        )

        omar_approved = await _upsert_goal(
            session,
            employee_id=omar.id,
            cycle_id=cycle.id,
            thrust_area_id=thrust_areas["Capability Building"].id,
            title="QBR program adoption",
            description="Roll out a structured QBR routine across named accounts.",
            uom_type=UomType.PERCENTAGE_MAX,
            target_value=Decimal("90"),
            target_date=None,
            weightage=30,
            status=GoalStatus.APPROVED,
            approved_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
            locked_at=None,
            updated_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
        )

        dev_shared = await _upsert_goal(
            session,
            employee_id=dev.id,
            cycle_id=cycle.id,
            thrust_area_id=thrust_areas["Revenue Growth"].id,
            title="Shared KPI: Cross-sell conversion",
            description="Linked KPI from commercial leadership.",
            uom_type=UomType.PERCENTAGE_MAX,
            target_value=Decimal("14"),
            target_date=None,
            weightage=20,
            status=GoalStatus.LOCKED,
            is_shared=True,
            shared_source_id=shared_source.id,
            approved_at=datetime(2026, 5, 11, 9, 0, tzinfo=UTC),
            locked_at=datetime(2026, 5, 12, 12, 0, tzinfo=UTC),
            updated_at=datetime(2026, 5, 12, 12, 0, tzinfo=UTC),
        )

        dev_goals = [
            dev_shared,
            await _upsert_goal(
                session,
                employee_id=dev.id,
                cycle_id=cycle.id,
                thrust_area_id=thrust_areas["Customer Experience"].id,
                title="Improve attach rate on pilot accounts",
                description="Increase multi-product adoption on pilot customers.",
                uom_type=UomType.PERCENTAGE_MAX,
                target_value=Decimal("22"),
                target_date=None,
                weightage=40,
                status=GoalStatus.LOCKED,
                approved_at=datetime(2026, 5, 11, 9, 10, tzinfo=UTC),
                locked_at=datetime(2026, 5, 12, 12, 10, tzinfo=UTC),
                updated_at=datetime(2026, 5, 12, 12, 10, tzinfo=UTC),
            ),
            await _upsert_goal(
                session,
                employee_id=dev.id,
                cycle_id=cycle.id,
                thrust_area_id=thrust_areas["Operational Excellence"].id,
                title="Close onboarding backlog without reopen",
                description="Resolve all inherited backlog items with zero reopens.",
                uom_type=UomType.ZERO,
                target_value=Decimal("0"),
                target_date=None,
                weightage=40,
                status=GoalStatus.LOCKED,
                approved_at=datetime(2026, 5, 11, 9, 20, tzinfo=UTC),
                locked_at=datetime(2026, 5, 12, 12, 20, tzinfo=UTC),
                updated_at=datetime(2026, 5, 12, 12, 20, tzinfo=UTC),
            ),
        ]

        await session.flush()

        await _upsert_achievement(
            session,
            goal=shared_source,
            quarter=Quarter.Q1,
            planned_value=Decimal("14"),
            actual_value=Decimal("13"),
            completion_date=None,
            status=GoalProgress.ON_TRACK,
        )
        await _upsert_achievement(
            session,
            goal=shared_source,
            quarter=Quarter.Q2,
            planned_value=Decimal("14"),
            actual_value=Decimal("15"),
            completion_date=None,
            status=GoalProgress.COMPLETED,
        )
        await _upsert_achievement(
            session,
            goal=omar_locked,
            quarter=Quarter.Q1,
            planned_value=Decimal("10"),
            actual_value=Decimal("8"),
            completion_date=None,
            status=GoalProgress.ON_TRACK,
        )
        await _upsert_achievement(
            session,
            goal=dev_shared,
            quarter=Quarter.Q1,
            planned_value=Decimal("14"),
            actual_value=Decimal("13"),
            completion_date=None,
            status=GoalProgress.ON_TRACK,
        )
        await _upsert_achievement(
            session,
            goal=dev_goals[1],
            quarter=Quarter.Q1,
            planned_value=Decimal("22"),
            actual_value=Decimal("19"),
            completion_date=None,
            status=GoalProgress.ON_TRACK,
        )
        await _upsert_achievement(
            session,
            goal=dev_goals[2],
            quarter=Quarter.Q1,
            planned_value=Decimal("0"),
            actual_value=Decimal("0"),
            completion_date=None,
            status=GoalProgress.COMPLETED,
        )

        await _upsert_comment(
            session,
            goal_id=shared_source.id,
            manager_id=maya.id,
            quarter=Quarter.Q1,
            comment="Momentum is healthy. Add two named deal checkpoints before month-end.",
        )
        await _upsert_comment(
            session,
            goal_id=omar_locked.id,
            manager_id=maya.id,
            quarter=Quarter.Q1,
            comment="Cycle-time is ahead of plan. Keep variance low during handoff.",
        )
        await _upsert_comment(
            session,
            goal_id=dev_goals[1].id,
            manager_id=rohan.id,
            quarter=Quarter.Q1,
            comment="Attach-rate lift is visible. Tighten follow-through on stalled accounts.",
        )

        goals_not_submitted_log = await _upsert_escalation_log(
            session,
            cycle_id=cycle.id,
            target_user_id=nina.id,
            manager_id=rohan.id,
            rule_id=goal_submission_rule.id,
            event_type=EscalationEventType.GOALS_NOT_SUBMITTED,
            status=EscalationStatus.OPEN,
            detail="Goal sheet has not been submitted for the active cycle.",
        )
        manager_not_approved_log = await _upsert_escalation_log(
            session,
            cycle_id=cycle.id,
            target_user_id=priya.id,
            manager_id=maya.id,
            rule_id=manager_approval_rule.id,
            event_type=EscalationEventType.MANAGER_NOT_APPROVED,
            status=EscalationStatus.OPEN,
            detail="Submitted goals are still pending manager approval after the SLA threshold.",
        )
        resolved_checkin_log = await _upsert_escalation_log(
            session,
            cycle_id=cycle.id,
            target_user_id=dev.id,
            manager_id=rohan.id,
            rule_id=checkin_rule.id,
            event_type=EscalationEventType.CHECKIN_NOT_COMPLETED,
            status=EscalationStatus.RESOLVED,
            detail="Q1 check-in was completed after follow-up.",
            resolved_at=datetime(2026, 5, 15, 14, 30, tzinfo=UTC),
            resolved_by=admin.id,
        )

        for goal in eshan_goals + priya_goals + [shared_source, omar_locked, omar_approved, *dev_goals]:
            await _ensure_audit_log(
                session,
                entity_type="goal",
                entity_id=goal.id,
                action="created",
                changed_by=admin.id,
                new_values={"title": goal.title, "status": goal.status.value},
            )
        for log in [goals_not_submitted_log, manager_not_approved_log]:
            await _ensure_audit_log(
                session,
                entity_type="escalation_log",
                entity_id=log.id,
                action="created",
                changed_by=admin.id,
                new_values={"event_type": log.event_type.value, "status": log.status.value},
            )
        await _ensure_audit_log(
            session,
            entity_type="escalation_log",
            entity_id=resolved_checkin_log.id,
            action="resolved",
            changed_by=admin.id,
            new_values={"event_type": resolved_checkin_log.event_type.value, "status": resolved_checkin_log.status.value},
        )
        await _ensure_audit_log(
            session,
            entity_type="checkin_window",
            entity_id=windows[Quarter.Q1].id,
            action="created",
            changed_by=admin.id,
            new_values={"quarter": Quarter.Q1.value},
        )

        await _upsert_notification_log(
            session,
            cycle_id=cycle.id,
            goal_id=priya_goals[0].id,
            recipient_user_id=maya.id,
            recipient_email=maya.email,
            channel=NotificationChannel.EMAIL,
            event_type=NotificationEventType.GOAL_SUBMITTED,
            status=NotificationDeliveryStatus.SKIPPED_NOT_CONFIGURED,
            subject="[AtomQuest] Goal Sheet Submitted - Priya Singh",
            detail="Priya Singh submitted a goal sheet with 3 goals.",
            error_message="Email channel is not configured.",
        )
        await _upsert_notification_log(
            session,
            cycle_id=cycle.id,
            goal_id=priya_goals[0].id,
            recipient_user_id=maya.id,
            recipient_email=maya.email,
            channel=NotificationChannel.TEAMS,
            event_type=NotificationEventType.GOAL_SUBMITTED,
            status=NotificationDeliveryStatus.SKIPPED_NOT_CONFIGURED,
            subject="[AtomQuest] Goal Sheet Submitted - Priya Singh",
            detail="Priya Singh submitted a goal sheet with 3 goals.",
            error_message="Teams webhook is not configured.",
        )
        await _upsert_notification_log(
            session,
            cycle_id=cycle.id,
            goal_id=shared_source.id,
            recipient_user_id=omar.id,
            recipient_email=omar.email,
            channel=NotificationChannel.EMAIL,
            event_type=NotificationEventType.GOAL_LOCKED,
            status=NotificationDeliveryStatus.FAILED,
            subject="[AtomQuest] Your Goals Are Now Locked - FY 2026 Goal Cycle",
            detail="Omar Khan's goals were locked by Maya Manager.",
            error_message="SMTP relay timed out during demo verification.",
        )
        await _upsert_notification_log(
            session,
            cycle_id=cycle.id,
            escalation_log_id=goals_not_submitted_log.id,
            recipient_user_id=rohan.id,
            recipient_email=rohan.email,
            channel=NotificationChannel.TEAMS,
            event_type=NotificationEventType.ESCALATION_RAISED,
            status=NotificationDeliveryStatus.SENT,
            subject="[AtomQuest] Escalation Alert - GOALS_NOT_SUBMITTED (Nina Joseph)",
            detail="Goal sheet has not been submitted for the active cycle.",
            error_message=None,
        )

        await session.commit()


async def _get_or_create_user(
    session,
    *,
    email: str,
    password: str,
    name: str,
    role: UserRole,
    department: str,
    manager_id=None,
) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user:
        user.name = name
        user.role = role
        user.department = department
        user.manager_id = manager_id
        user.is_active = True
        return user
    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name,
        role=role,
        department=department,
        manager_id=manager_id,
    )
    session.add(user)
    return user


async def _get_or_create_cycle(
    session,
    *,
    name: str,
    start_date: date,
    end_date: date,
    status: CycleStatus,
    created_by,
) -> GoalCycle:
    cycle = await session.scalar(select(GoalCycle).where(GoalCycle.name == name).limit(1))
    if not cycle:
        cycle = GoalCycle(name=name, start_date=start_date, end_date=end_date, status=status, created_by=created_by)
        session.add(cycle)
        await session.flush()
        return cycle
    cycle.start_date = start_date
    cycle.end_date = end_date
    cycle.status = status
    cycle.created_by = created_by
    return cycle


async def _normalize_active_cycle(session, *, keep_cycle_id) -> None:
    active_cycles = list((await session.scalars(select(GoalCycle).where(GoalCycle.status == CycleStatus.ACTIVE))).all())
    for cycle in active_cycles:
        if cycle.id != keep_cycle_id:
            cycle.status = CycleStatus.CLOSED


async def _get_or_create_thrust_area(
    session,
    *,
    cycle_id,
    name: str,
    description: str,
) -> ThrustArea:
    area = await session.scalar(
        select(ThrustArea).where(ThrustArea.cycle_id == cycle_id, ThrustArea.name == name).limit(1)
    )
    if not area:
        area = ThrustArea(cycle_id=cycle_id, name=name, description=description)
        session.add(area)
        await session.flush()
        return area
    area.description = description
    return area


async def _upsert_checkin_window(
    session,
    *,
    cycle_id,
    quarter: Quarter,
    opens_at: date,
    closes_at: date,
) -> CheckinWindow:
    window = await session.scalar(
        select(CheckinWindow).where(CheckinWindow.cycle_id == cycle_id, CheckinWindow.quarter == quarter).limit(1)
    )
    if not window:
        window = CheckinWindow(cycle_id=cycle_id, quarter=quarter, opens_at=opens_at, closes_at=closes_at)
        session.add(window)
        await session.flush()
        return window
    window.opens_at = opens_at
    window.closes_at = closes_at
    return window


async def _get_or_create_rule(
    session,
    *,
    event_type: EscalationEventType,
    threshold_days: int,
    escalation_level: int,
    description: str,
) -> EscalationRule:
    rule = await session.scalar(
        select(EscalationRule).where(
            EscalationRule.event_type == event_type,
            EscalationRule.threshold_days == threshold_days,
            EscalationRule.escalation_level == escalation_level,
        )
    )
    if not rule:
        rule = EscalationRule(
            event_type=event_type,
            threshold_days=threshold_days,
            escalation_level=escalation_level,
            is_active=True,
            description=description,
        )
        session.add(rule)
        await session.flush()
        return rule
    rule.description = description
    rule.is_active = True
    return rule


async def _upsert_goal(
    session,
    *,
    employee_id,
    cycle_id,
    thrust_area_id,
    title: str,
    description: str,
    uom_type: UomType,
    target_value: Decimal | None,
    target_date: date | None,
    weightage: int,
    status: GoalStatus,
    is_shared: bool = False,
    shared_source_id=None,
    approved_at: datetime | None = None,
    locked_at: datetime | None = None,
    returned_reason: str | None = None,
    updated_at: datetime | None = None,
) -> Goal:
    goal = await session.scalar(
        select(Goal).where(
            Goal.employee_id == employee_id,
            Goal.cycle_id == cycle_id,
            Goal.title == title,
        ).limit(1)
    )
    if not goal:
        goal = Goal(
            employee_id=employee_id,
            cycle_id=cycle_id,
            thrust_area_id=thrust_area_id,
            title=title,
            description=description,
            uom_type=uom_type,
            target_value=target_value,
            target_date=target_date,
            weightage=weightage,
            status=status,
            is_shared=is_shared,
            shared_source_id=shared_source_id,
            approved_at=approved_at,
            locked_at=locked_at,
            returned_reason=returned_reason,
        )
        session.add(goal)
        await session.flush()
    else:
        goal.thrust_area_id = thrust_area_id
        goal.description = description
        goal.uom_type = uom_type
        goal.target_value = target_value
        goal.target_date = target_date
        goal.weightage = weightage
        goal.status = status
        goal.is_shared = is_shared
        goal.shared_source_id = shared_source_id
        goal.approved_at = approved_at
        goal.locked_at = locked_at
        goal.returned_reason = returned_reason
    if updated_at:
        goal.updated_at = updated_at
        goal.created_at = min(goal.created_at or updated_at, updated_at)
    return goal


async def _upsert_achievement(
    session,
    *,
    goal: Goal,
    quarter: Quarter,
    planned_value: Decimal | None,
    actual_value: Decimal | None,
    completion_date: date | None,
    status: GoalProgress,
) -> GoalAchievement:
    achievement = await session.scalar(
        select(GoalAchievement).where(
            GoalAchievement.goal_id == goal.id,
            GoalAchievement.quarter == quarter,
        ).limit(1)
    )
    score = compute_progress_score(goal.uom_type, goal.target_value, actual_value, goal.target_date, completion_date)
    if not achievement:
        achievement = GoalAchievement(
            goal_id=goal.id,
            quarter=quarter,
            planned_value=planned_value,
            actual_value=actual_value,
            completion_date=completion_date,
            status=status,
            computed_score=score,
        )
        session.add(achievement)
        await session.flush()
        return achievement
    achievement.planned_value = planned_value
    achievement.actual_value = actual_value
    achievement.completion_date = completion_date
    achievement.status = status
    achievement.computed_score = score
    return achievement


async def _upsert_comment(
    session,
    *,
    goal_id,
    manager_id,
    quarter: Quarter,
    comment: str,
) -> CheckinComment:
    existing = await session.scalar(
        select(CheckinComment).where(
            CheckinComment.goal_id == goal_id,
            CheckinComment.manager_id == manager_id,
            CheckinComment.quarter == quarter,
        ).limit(1)
    )
    if not existing:
        existing = CheckinComment(goal_id=goal_id, manager_id=manager_id, quarter=quarter, comment=comment)
        session.add(existing)
        await session.flush()
        return existing
    existing.comment = comment
    return existing


async def _upsert_escalation_log(
    session,
    *,
    cycle_id,
    target_user_id,
    manager_id,
    rule_id,
    event_type: EscalationEventType,
    status: EscalationStatus,
    detail: str,
    resolved_at: datetime | None = None,
    resolved_by=None,
) -> EscalationLog:
    log = await session.scalar(
        select(EscalationLog).where(
            EscalationLog.cycle_id == cycle_id,
            EscalationLog.target_user_id == target_user_id,
            EscalationLog.rule_id == rule_id,
            EscalationLog.event_type == event_type,
        ).limit(1)
    )
    if not log:
        log = EscalationLog(
            cycle_id=cycle_id,
            target_user_id=target_user_id,
            manager_id=manager_id,
            rule_id=rule_id,
            event_type=event_type,
            status=status,
            detail=detail,
            resolved_at=resolved_at,
            resolved_by=resolved_by,
        )
        session.add(log)
        await session.flush()
        return log
    log.manager_id = manager_id
    log.status = status
    log.detail = detail
    log.resolved_at = resolved_at
    log.resolved_by = resolved_by
    return log


async def _ensure_audit_log(
    session,
    *,
    entity_type: str,
    entity_id,
    action: str,
    changed_by,
    old_values: dict | None = None,
    new_values: dict | None = None,
    reason: str | None = None,
) -> None:
    existing = await session.scalar(
        select(AuditLog).where(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
            AuditLog.action == action,
            AuditLog.changed_by == changed_by,
        ).limit(1)
    )
    if existing:
        return
    await write_audit_log(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changed_by=changed_by,
        old_values=old_values,
        new_values=new_values,
        reason=reason,
    )


async def _upsert_notification_log(
    session,
    *,
    cycle_id=None,
    goal_id=None,
    escalation_log_id=None,
    recipient_user_id=None,
    recipient_email: str | None,
    channel: NotificationChannel,
    event_type: NotificationEventType,
    status: NotificationDeliveryStatus,
    subject: str,
    detail: str | None,
    error_message: str | None,
) -> NotificationLog:
    log = await session.scalar(
        select(NotificationLog).where(
            NotificationLog.channel == channel,
            NotificationLog.event_type == event_type,
            NotificationLog.subject == subject,
            NotificationLog.recipient_email == recipient_email,
        ).limit(1)
    )
    if not log:
        log = NotificationLog(
            cycle_id=cycle_id,
            goal_id=goal_id,
            escalation_log_id=escalation_log_id,
            recipient_user_id=recipient_user_id,
            recipient_email=recipient_email,
            channel=channel,
            event_type=event_type,
            status=status,
            subject=subject,
            detail=detail,
            error_message=error_message,
        )
        session.add(log)
        await session.flush()
        return log

    log.cycle_id = cycle_id
    log.goal_id = goal_id
    log.escalation_log_id = escalation_log_id
    log.recipient_user_id = recipient_user_id
    log.status = status
    log.detail = detail
    log.error_message = error_message
    return log


if __name__ == "__main__":
    asyncio.run(seed())
