"""phase 5 devin advanced integration fields

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("remediation_outcome", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("root_cause", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("implementation_summary", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("structured_result_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("blocker", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("playbook_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("acu_source", sa.String(length=32), nullable=True))
        batch_op.add_column(
            sa.Column("acu_verified", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        batch_op.drop_column("acu_verified")
        batch_op.drop_column("acu_source")
        batch_op.drop_column("playbook_id")
        batch_op.drop_column("blocker")
        batch_op.drop_column("structured_result_json")
        batch_op.drop_column("implementation_summary")
        batch_op.drop_column("root_cause")
        batch_op.drop_column("remediation_outcome")
