"""add trigger_source to remediation tasks

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("trigger_source", sa.String(length=32), nullable=True))

    op.execute(
        "UPDATE remediation_tasks SET trigger_source = 'manual_api' "
        "WHERE github_delivery_id LIKE 'api:%'"
    )
    op.execute(
        "UPDATE remediation_tasks SET trigger_source = 'scan' "
        "WHERE github_delivery_id LIKE 'manual:%'"
    )
    op.execute(
        "UPDATE remediation_tasks SET trigger_source = 'github_webhook' "
        "WHERE trigger_source IS NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        batch_op.drop_column("trigger_source")
