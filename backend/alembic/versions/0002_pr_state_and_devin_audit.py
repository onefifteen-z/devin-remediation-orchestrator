"""add pr_state and devin audit fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pr_state", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("devin_status", sa.String(length=32), nullable=True))
        batch_op.add_column(
            sa.Column("devin_status_detail", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(sa.Column("devin_origin", sa.String(length=32), nullable=True))
        batch_op.add_column(
            sa.Column("devin_service_user_id", sa.String(length=128), nullable=True)
        )
        batch_op.add_column(sa.Column("devin_tags", sa.Text(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_repo_issue",
            ["github_repository", "github_issue_number"],
        )


def downgrade() -> None:
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        batch_op.drop_constraint("uq_repo_issue", type_="unique")
        batch_op.drop_column("devin_tags")
        batch_op.drop_column("devin_service_user_id")
        batch_op.drop_column("devin_origin")
        batch_op.drop_column("devin_status_detail")
        batch_op.drop_column("devin_status")
        batch_op.drop_column("pr_state")
