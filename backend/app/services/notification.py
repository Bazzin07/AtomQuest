"""
Notification service — B2 (Email) + B3 (Microsoft Teams).

Both channels are opt-in and degrade gracefully:
  - Email: activated when ``notifications_enabled=true`` AND ``smtp_user`` / ``smtp_password`` are set.
  - Teams: activated when ``notifications_enabled=true`` AND ``teams_webhook_url`` is set.

Trigger points (called from routers after DB commit):
  - goal_submitted    → notify manager via email + Teams
  - goal_approved     → notify employee via email + Teams
  - goal_returned     → notify employee via email + Teams
  - goal_locked       → notify employee via email + Teams
  - escalation_raised → notify manager (and optionally HR) via email + Teams

All dispatches are fire-and-forget (``asyncio.create_task``) to avoid adding
latency to the API response. Errors are logged but never bubble to the caller.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from uuid import UUID

import httpx
import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.database import async_session_factory
from app.models.enums import NotificationChannel, NotificationDeliveryStatus, NotificationEventType
from app.models.notification import NotificationLog

logger = structlog.get_logger()

# ── Jinja2 template engine ────────────────────────────────────────────────────
_TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "email"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _render(template_name: str, **ctx) -> str:
    """Render a Jinja2 HTML email template."""
    ctx.setdefault("year", datetime.now(timezone.utc).year)
    ctx.setdefault("app_url", settings.frontend_app_url)
    ctx.setdefault("subject", "AtomQuest Notification")
    return _jinja_env.get_template(template_name).render(**ctx)


@dataclass(slots=True)
class NotificationContext:
    event_type: NotificationEventType
    subject: str
    recipient_email: str | None
    recipient_user_id: UUID | None = None
    cycle_id: UUID | None = None
    goal_id: UUID | None = None
    escalation_log_id: UUID | None = None
    detail: str | None = None


async def _persist_attempt(
    context: NotificationContext,
    *,
    channel: NotificationChannel,
    status: NotificationDeliveryStatus,
    error_message: str | None = None,
) -> None:
    try:
        async with async_session_factory() as session:
            session.add(
                NotificationLog(
                    cycle_id=context.cycle_id,
                    goal_id=context.goal_id,
                    escalation_log_id=context.escalation_log_id,
                    recipient_user_id=context.recipient_user_id,
                    recipient_email=context.recipient_email,
                    channel=channel,
                    event_type=context.event_type,
                    status=status,
                    subject=context.subject,
                    detail=context.detail,
                    error_message=error_message,
                )
            )
            await session.commit()
    except Exception as exc:
        logger.warning(
            "notification_log_persist_failed",
            channel=channel.value,
            event_type=context.event_type.value,
            error=str(exc),
        )


# ── SMTP Email dispatch ───────────────────────────────────────────────────────

async def _send_email(
    to: str | None,
    subject: str,
    html_body: str,
) -> tuple[NotificationDeliveryStatus, str | None]:
    """Send a single HTML email via SMTP."""
    if not settings.email_enabled:
        logger.debug("email_skipped_not_configured", to=to, subject=subject)
        return NotificationDeliveryStatus.SKIPPED_NOT_CONFIGURED, "Email channel is not configured."
    if not to:
        return NotificationDeliveryStatus.FAILED, "Recipient email is missing."
    try:
        import aiosmtplib  # lazy import — optional dep

        msg = MIMEMultipart("alternative")
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=False,
            start_tls=settings.smtp_use_tls,
        )
        logger.info("email_sent", to=to, subject=subject)
        return NotificationDeliveryStatus.SENT, None
    except Exception as exc:
        logger.warning("email_send_failed", to=to, subject=subject, error=str(exc))
        return NotificationDeliveryStatus.FAILED, str(exc)


# ── Teams Adaptive Card dispatch ─────────────────────────────────────────────

def _teams_card(title: str, facts: list[dict], color: str = "accent") -> dict:
    """Build a minimal Teams Adaptive Card payload (Incoming Webhook format)."""
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "msteams": {"width": "Full"},
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "🎯 AtomQuest",
                            "size": "Small",
                            "color": "Accent",
                            "weight": "Lighter",
                        },
                        {
                            "type": "TextBlock",
                            "text": title,
                            "size": "Medium",
                            "weight": "Bolder",
                            "wrap": True,
                        },
                        {
                            "type": "FactSet",
                            "facts": facts,
                        },
                    ],
                },
            }
        ],
    }


async def _send_teams(
    title: str,
    facts: list[dict],
) -> tuple[NotificationDeliveryStatus, str | None]:
    """POST an Adaptive Card to the configured Teams incoming webhook."""
    if not settings.teams_enabled:
        logger.debug("teams_skipped_not_configured", title=title)
        return NotificationDeliveryStatus.SKIPPED_NOT_CONFIGURED, "Teams webhook is not configured."
    try:
        card = _teams_card(title, facts)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.teams_webhook_url, json=card)
            resp.raise_for_status()
        logger.info("teams_card_sent", title=title)
        return NotificationDeliveryStatus.SENT, None
    except Exception as exc:
        logger.warning("teams_card_failed", title=title, error=str(exc))
        return NotificationDeliveryStatus.FAILED, str(exc)


# ── Public notification helpers ───────────────────────────────────────────────

def _fire(coro) -> None:
    """Schedule a coroutine as a background task (fire-and-forget)."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        # No running loop (e.g. sync test context) — run synchronously
        asyncio.run(coro)


async def _dispatch_email(context: NotificationContext, html_body: str) -> None:
    status, error = await _send_email(context.recipient_email, context.subject, html_body)
    await _persist_attempt(
        context,
        channel=NotificationChannel.EMAIL,
        status=status,
        error_message=error,
    )


async def _dispatch_teams(context: NotificationContext, facts: list[dict]) -> None:
    status, error = await _send_teams(context.subject, facts)
    await _persist_attempt(
        context,
        channel=NotificationChannel.TEAMS,
        status=status,
        error_message=error,
    )


async def notify_goal_submitted(
    *,
    cycle_id: UUID,
    manager_email: str,
    manager_user_id: UUID | None,
    manager_name: str,
    employee_name: str,
    department: str,
    cycle_name: str,
    goal_count: int,
) -> None:
    """Notify manager that an employee's goal sheet has been submitted."""
    subject = f"[AtomQuest] Goal Sheet Submitted — {employee_name}"
    html = _render(
        "goal_submitted.html",
        subject=subject,
        manager_name=manager_name,
        employee_name=employee_name,
        department=department or "—",
        cycle_name=cycle_name,
        goal_count=goal_count,
    )
    facts = [
        {"title": "Employee", "value": employee_name},
        {"title": "Department", "value": department or "—"},
        {"title": "Cycle", "value": cycle_name},
        {"title": "Goals", "value": str(goal_count)},
        {"title": "Status", "value": "SUBMITTED — awaiting your review"},
    ]
    context = NotificationContext(
        event_type=NotificationEventType.GOAL_SUBMITTED,
        subject=subject,
        recipient_email=manager_email,
        recipient_user_id=manager_user_id,
        cycle_id=cycle_id,
        detail=f"{employee_name} submitted a goal sheet with {goal_count} goals.",
    )
    _fire(_dispatch_email(context, html))
    _fire(_dispatch_teams(context, facts))


async def notify_goal_approved(
    *,
    goal_id: UUID,
    cycle_id: UUID,
    employee_email: str,
    employee_user_id: UUID | None,
    employee_name: str,
    manager_name: str,
    cycle_name: str,
    approved_at: datetime | None = None,
) -> None:
    """Notify employee that their goal sheet was approved."""
    subject = f"[AtomQuest] Your Goals Are Approved — {cycle_name}"
    ts = (approved_at or datetime.now(timezone.utc)).strftime("%d %b %Y, %H:%M UTC")
    html = _render(
        "goal_approved.html",
        subject=subject,
        employee_name=employee_name,
        manager_name=manager_name,
        cycle_name=cycle_name,
        approved_at=ts,
    )
    facts = [
        {"title": "Approved By", "value": manager_name},
        {"title": "Cycle", "value": cycle_name},
        {"title": "Approved At", "value": ts},
        {"title": "Status", "value": "APPROVED ✅"},
    ]
    context = NotificationContext(
        event_type=NotificationEventType.GOAL_APPROVED,
        subject=subject,
        recipient_email=employee_email,
        recipient_user_id=employee_user_id,
        cycle_id=cycle_id,
        goal_id=goal_id,
        detail=f"{employee_name}'s goal sheet was approved by {manager_name}.",
    )
    _fire(_dispatch_email(context, html))
    _fire(_dispatch_teams(context, facts))


async def notify_goal_returned(
    *,
    goal_id: UUID,
    cycle_id: UUID,
    employee_email: str,
    employee_user_id: UUID | None,
    employee_name: str,
    manager_name: str,
    cycle_name: str,
    goal_title: str,
    reason: str | None,
) -> None:
    """Notify employee that a goal was returned for revision."""
    subject = f"[AtomQuest] Goal Returned for Revision — {goal_title}"
    html = _render(
        "goal_returned.html",
        subject=subject,
        employee_name=employee_name,
        manager_name=manager_name,
        cycle_name=cycle_name,
        goal_title=goal_title,
        reason=reason or "",
    )
    facts = [
        {"title": "Goal", "value": goal_title},
        {"title": "Returned By", "value": manager_name},
        {"title": "Cycle", "value": cycle_name},
        {"title": "Reason", "value": reason or "—"},
        {"title": "Status", "value": "RETURNED — please revise"},
    ]
    context = NotificationContext(
        event_type=NotificationEventType.GOAL_RETURNED,
        subject=subject,
        recipient_email=employee_email,
        recipient_user_id=employee_user_id,
        cycle_id=cycle_id,
        goal_id=goal_id,
        detail=reason or f"{goal_title} was returned for revision.",
    )
    _fire(_dispatch_email(context, html))
    _fire(_dispatch_teams(context, facts))


async def notify_goal_locked(
    *,
    goal_id: UUID,
    cycle_id: UUID,
    employee_email: str,
    employee_user_id: UUID | None,
    employee_name: str,
    manager_name: str,
    cycle_name: str,
    locked_at: datetime | None = None,
) -> None:
    """Notify employee that their goals have been locked."""
    subject = f"[AtomQuest] Your Goals Are Now Locked — {cycle_name}"
    ts = (locked_at or datetime.now(timezone.utc)).strftime("%d %b %Y, %H:%M UTC")
    html = _render(
        "goal_locked.html",
        subject=subject,
        employee_name=employee_name,
        manager_name=manager_name,
        cycle_name=cycle_name,
        locked_at=ts,
    )
    facts = [
        {"title": "Locked By", "value": manager_name},
        {"title": "Cycle", "value": cycle_name},
        {"title": "Locked At", "value": ts},
        {"title": "Status", "value": "LOCKED 🔒"},
    ]
    context = NotificationContext(
        event_type=NotificationEventType.GOAL_LOCKED,
        subject=subject,
        recipient_email=employee_email,
        recipient_user_id=employee_user_id,
        cycle_id=cycle_id,
        goal_id=goal_id,
        detail=f"{employee_name}'s goals were locked by {manager_name}.",
    )
    _fire(_dispatch_email(context, html))
    _fire(_dispatch_teams(context, facts))


async def notify_escalation(
    *,
    cycle_id: UUID,
    escalation_log_id: UUID | None,
    recipient_email: str,
    recipient_user_id: UUID | None,
    recipient_name: str,
    target_name: str,
    cycle_name: str,
    event_type: str,
    threshold_days: int,
    escalation_level: int,
    detail: str,
) -> None:
    """Notify manager / HR about a new escalation."""
    subject = f"[AtomQuest] Escalation Alert — {event_type} ({target_name})"
    html = _render(
        "escalation_alert.html",
        subject=subject,
        recipient_name=recipient_name,
        target_name=target_name,
        cycle_name=cycle_name,
        event_type=event_type,
        threshold_days=threshold_days,
        escalation_level=escalation_level,
        detail=detail,
    )
    facts = [
        {"title": "Employee", "value": target_name},
        {"title": "Cycle", "value": cycle_name},
        {"title": "Event", "value": event_type},
        {"title": "Overdue by", "value": f"{threshold_days} days"},
        {"title": "Level", "value": str(escalation_level)},
        {"title": "Detail", "value": detail},
    ]
    context = NotificationContext(
        event_type=NotificationEventType.ESCALATION_RAISED,
        subject=subject,
        recipient_email=recipient_email,
        recipient_user_id=recipient_user_id,
        cycle_id=cycle_id,
        escalation_log_id=escalation_log_id,
        detail=detail,
    )
    _fire(_dispatch_email(context, html))
    _fire(_dispatch_teams(context, facts))
