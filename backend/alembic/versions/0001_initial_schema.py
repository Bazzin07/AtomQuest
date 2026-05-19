"""Initial AtomQuest schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = sa.Enum("EMPLOYEE", "MANAGER", "ADMIN", name="userrole")
goal_status = sa.Enum("DRAFT", "SUBMITTED", "RETURNED", "LOCKED", name="goalstatus")
uom_type = sa.Enum(
    "NUMERIC_MIN",
    "NUMERIC_MAX",
    "PERCENTAGE_MIN",
    "PERCENTAGE_MAX",
    "TIMELINE",
    "ZERO",
    name="uomtype",
)
quarter = sa.Enum("Q1", "Q2", "Q3", "Q4", name="quarter")
goal_progress = sa.Enum("NOT_STARTED", "ON_TRACK", "COMPLETED", name="goalprogress")
cycle_status = sa.Enum("ACTIVE", "CLOSED", name="cyclestatus")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    user_role.create(op.get_bind(), checkfirst=True)
    goal_status.create(op.get_bind(), checkfirst=True)
    uom_type.create(op.get_bind(), checkfirst=True)
    quarter.create(op.get_bind(), checkfirst=True)
    goal_progress.create(op.get_bind(), checkfirst=True)
    cycle_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    op.create_table(
        "goal_cycles",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", cycle_status, nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "thrust_areas",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.ForeignKeyConstraint(["cycle_id"], ["goal_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "checkin_windows",
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quarter", quarter, nullable=False),
        sa.Column("opens_at", sa.Date(), nullable=False),
        sa.Column("closes_at", sa.Date(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.ForeignKeyConstraint(["cycle_id"], ["goal_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "quarter", name="uq_checkin_window_cycle_quarter"),
    )

    op.create_table(
        "goals",
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thrust_area_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("uom_type", uom_type, nullable=False),
        sa.Column("target_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("weightage", sa.Integer(), nullable=False),
        sa.Column("status", goal_status, nullable=True),
        sa.Column("is_shared", sa.Boolean(), nullable=False),
        sa.Column("shared_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("returned_reason", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("weightage >= 10 AND weightage <= 100", name="ck_goal_weightage_range"),
        sa.ForeignKeyConstraint(["cycle_id"], ["goal_cycles.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["shared_source_id"], ["goals.id"]),
        sa.ForeignKeyConstraint(["thrust_area_id"], ["thrust_areas.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_goals_cycle_id"), "goals", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_goals_employee_id"), "goals", ["employee_id"], unique=False)

    op.create_table(
        "goal_achievements",
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quarter", quarter, nullable=False),
        sa.Column("planned_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("completion_date", sa.Date(), nullable=True),
        sa.Column("status", goal_progress, nullable=True),
        sa.Column("computed_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("goal_id", "quarter", name="uq_achievement_goal_quarter"),
    )
    op.create_index(op.f("ix_goal_achievements_goal_id"), "goal_achievements", ["goal_id"], unique=False)

    op.create_table(
        "checkin_comments",
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quarter", quarter, nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("goal_id", "manager_id", "quarter", name="uq_checkin_comment"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("old_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_entity_id"), "audit_logs", ["entity_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_entity_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("checkin_comments")
    op.drop_index(op.f("ix_goal_achievements_goal_id"), table_name="goal_achievements")
    op.drop_table("goal_achievements")
    op.drop_index(op.f("ix_goals_employee_id"), table_name="goals")
    op.drop_index(op.f("ix_goals_cycle_id"), table_name="goals")
    op.drop_table("goals")
    op.drop_table("checkin_windows")
    op.drop_table("thrust_areas")
    op.drop_table("goal_cycles")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    cycle_status.drop(op.get_bind(), checkfirst=True)
    goal_progress.drop(op.get_bind(), checkfirst=True)
    quarter.drop(op.get_bind(), checkfirst=True)
    uom_type.drop(op.get_bind(), checkfirst=True)
    goal_status.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)

