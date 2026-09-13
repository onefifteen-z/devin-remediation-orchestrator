"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "remediation_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("github_delivery_id", sa.String(length=64), nullable=False),
        sa.Column("github_repository", sa.String(length=255), nullable=False),
        sa.Column("github_issue_number", sa.Integer(), nullable=False),
        sa.Column("github_issue_url", sa.String(length=512), nullable=False),
        sa.Column("issue_title", sa.String(length=512), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("devin_session_id", sa.String(length=128), nullable=True),
        sa.Column("devin_session_url", sa.String(length=512), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "RECEIVED",
                "SESSION_CREATED",
                "RUNNING",
                "PR_OPENED",
                "CI_FAILED",
                "READY_FOR_REVIEW",
                "MERGED",
                "FAILED",
                "ESCALATED",
                name="taskstatus",
            ),
            nullable=False,
        ),
        sa.Column("pr_url", sa.String(length=512), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
        sa.Column("acu_used", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_remediation_tasks_github_delivery_id"),
        "remediation_tasks",
        ["github_delivery_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_remediation_tasks_status"),
        "remediation_tasks",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_remediation_tasks_status"), table_name="remediation_tasks")
    op.drop_index(
        op.f("ix_remediation_tasks_github_delivery_id"),
        table_name="remediation_tasks",
    )
    op.drop_table("remediation_tasks")
