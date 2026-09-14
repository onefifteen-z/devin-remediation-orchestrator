"""phase 6 task_kind for production metrics

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("remediation_tasks")}
    if "task_kind" not in columns:
        with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "task_kind",
                    sa.String(length=32),
                    nullable=False,
                    server_default="remediation",
                )
            )

    op.execute(
        """
        UPDATE remediation_tasks
        SET task_kind = 'smoke_test'
        WHERE lower(issue_title) LIKE '%smoke test%'
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        batch_op.drop_column("task_kind")
