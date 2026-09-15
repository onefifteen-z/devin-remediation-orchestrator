"""add ci_passed_at, completion_reason, and COMPLETED status support

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ci_passed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("completion_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        batch_op.drop_column("completion_reason")
        batch_op.drop_column("ci_passed_at")
