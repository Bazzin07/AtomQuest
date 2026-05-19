"""Add analytics escalation bonus tables.

Revision ID: 0002_escalation_bonus
Revises: 0001_initial_schema
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_escalation_bonus"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

escalation_event_type = sa.Enum(
    "GOALS_NOT_SUBMITTED",
    "MANAGER_NOT_APPROVED",
    "CHECKIN_NOT_COMPLETED",
    name="escalationeventtype",
)
escalation_status = sa.Enum("OPEN", "RESOLVED", name="escalationstatus")


def upgrade() -> None:
    escalation_event_type.create(op.get_bind(), checkfirst=True)
    escalation_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "escalation_rules",
        sa.Column("event_type", escalation_event_type, nullable=False),
        sa.Column("threshold_days", sa.Integer(), nullable=False),
        sa.Column("escalation_level", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_type", "threshold_days", "escalation_level", name="uq_escalation_rule"
        ),
    )

    op.create_table(
        "escalation_logs",
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", escalation_event_type, nullable=False),
        sa.Column("status", escalation_status, nullable=False),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.ForeignKeyConstraint(["cycle_id"], ["goal_cycles.id"]),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["escalation_rules.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_escalation_logs_cycle_id"), "escalation_logs", ["cycle_id"], unique=False)
    op.create_index(
        op.f("ix_escalation_logs_manager_id"), "escalation_logs", ["manager_id"], unique=False
    )
    op.create_index(
        op.f("ix_escalation_logs_target_user_id"),
        "escalation_logs",
        ["target_user_id"],
        unique=False,
    )
    op.create_index(
        "uq_open_escalation_log",
        "escalation_logs",
        ["cycle_id", "target_user_id", "rule_id", "event_type"],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
    )


def downgrade() -> None:
    op.drop_index("uq_open_escalation_log", table_name="escalation_logs")
    op.drop_index(op.f("ix_escalation_logs_target_user_id"), table_name="escalation_logs")
    op.drop_index(op.f("ix_escalation_logs_manager_id"), table_name="escalation_logs")
    op.drop_index(op.f("ix_escalation_logs_cycle_id"), table_name="escalation_logs")
    op.drop_table("escalation_logs")
    op.drop_table("escalation_rules")

    escalation_status.drop(op.get_bind(), checkfirst=True)
    escalation_event_type.drop(op.get_bind(), checkfirst=True)
