"""github issue labels

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ISSUE_LABEL_COLUMNS = (sa.Column("issue_labels", sa.Text(), nullable=True),)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("remediation_tasks")}
    missing = [column for column in ISSUE_LABEL_COLUMNS if column.name not in existing]
    if not missing:
        return
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        for column in missing:
            batch_op.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        for column in ISSUE_LABEL_COLUMNS:
            batch_op.drop_column(column.name)
