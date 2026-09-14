"""devin session insights fields

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INSIGHTS_COLUMNS = (
    sa.Column("session_size", sa.String(length=8), nullable=True),
    sa.Column("num_user_messages", sa.Integer(), nullable=True),
    sa.Column("num_devin_messages", sa.Integer(), nullable=True),
    sa.Column("insights_status", sa.String(length=32), nullable=True),
    sa.Column("insights_json", sa.Text(), nullable=True),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("remediation_tasks")}
    missing = [column for column in INSIGHTS_COLUMNS if column.name not in existing]
    if not missing:
        return
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        for column in missing:
            batch_op.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        for column in INSIGHTS_COLUMNS:
            batch_op.drop_column(column.name)
