"""Add notification log persistence.

Revision ID: 0004_notification_logs
Revises: 0003_approved_state
Create Date: 2026-05-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_notification_logs"
down_revision: str | None = "0003_approved_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

notification_channel = sa.Enum("EMAIL", "TEAMS", name="notificationchannel")
notification_event_type = sa.Enum(
    "GOAL_SUBMITTED",
    "GOAL_APPROVED",
    "GOAL_RETURNED",
    "GOAL_LOCKED",
    "ESCALATION_RAISED",
    name="notificationeventtype",
)
notification_delivery_status = sa.Enum(
    "SENT",
    "SKIPPED_NOT_CONFIGURED",
    "FAILED",
    name="notificationdeliverystatus",
)


def upgrade() -> None:
    notification_channel.create(op.get_bind(), checkfirst=True)
    notification_event_type.create(op.get_bind(), checkfirst=True)
    notification_delivery_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "notification_logs",
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("escalation_log_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recipient_email", sa.String(length=320), nullable=True),
        sa.Column("channel", notification_channel, nullable=False),
        sa.Column("event_type", notification_event_type, nullable=False),
        sa.Column("status", notification_delivery_status, nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.ForeignKeyConstraint(["cycle_id"], ["goal_cycles.id"]),
        sa.ForeignKeyConstraint(["escalation_log_id"], ["escalation_logs.id"]),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notification_logs_attempted_at"), "notification_logs", ["attempted_at"], unique=False)
    op.create_index(op.f("ix_notification_logs_channel"), "notification_logs", ["channel"], unique=False)
    op.create_index(op.f("ix_notification_logs_cycle_id"), "notification_logs", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_notification_logs_escalation_log_id"), "notification_logs", ["escalation_log_id"], unique=False)
    op.create_index(op.f("ix_notification_logs_event_type"), "notification_logs", ["event_type"], unique=False)
    op.create_index(op.f("ix_notification_logs_goal_id"), "notification_logs", ["goal_id"], unique=False)
    op.create_index(op.f("ix_notification_logs_recipient_user_id"), "notification_logs", ["recipient_user_id"], unique=False)
    op.create_index(op.f("ix_notification_logs_status"), "notification_logs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_logs_status"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_recipient_user_id"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_goal_id"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_event_type"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_escalation_log_id"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_cycle_id"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_channel"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_attempted_at"), table_name="notification_logs")
    op.drop_table("notification_logs")

    notification_delivery_status.drop(op.get_bind(), checkfirst=True)
    notification_event_type.drop(op.get_bind(), checkfirst=True)
    notification_channel.drop(op.get_bind(), checkfirst=True)
