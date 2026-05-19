"""Add APPROVED goal status + approved_at column.

Revision ID: 0003_approved_state
Revises: 0002_escalation_bonus
Create Date: 2026-05-17

Changes:
  1. Adds 'APPROVED' to the goal_status PostgreSQL ENUM.
  2. Adds approved_at (nullable timestamptz) column to goals table.

Safe to run on live data — adding an enum variant and a nullable column
are non-destructive operations in PostgreSQL.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_approved_state"
down_revision = "0002_escalation_bonus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add APPROVED to the PostgreSQL enum type.
    # PostgreSQL requires ALTER TYPE to add values; this is a safe, backwards-
    # compatible operation — existing rows keep their current values unchanged.
    op.execute("ALTER TYPE goalstatus ADD VALUE IF NOT EXISTS 'APPROVED' BEFORE 'RETURNED'")

    # Step 2: Add approved_at timestamp column.
    # Nullable so existing rows (which have never been through APPROVED state)
    # remain valid without a backfill.
    op.add_column(
        "goals",
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # Remove the approved_at column.
    op.drop_column("goals", "approved_at")

    # NOTE: PostgreSQL does NOT support removing enum values.
    # The 'APPROVED' value will remain in the enum type after downgrade.
    # If you need to fully remove it, recreate the enum type manually.
