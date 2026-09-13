"""add CI failure metadata columns

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("failure_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("ci_classification_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("ci_check_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("ci_check_url", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("ci_conclusion", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("ci_failure_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column(
                "ci_repair_attempts",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(sa.Column("last_ci_check_run_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("ci_repair_message_sent_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("ci_repair_verified_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "ci_non_code_failure_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("remediation_tasks", schema=None) as batch_op:
        batch_op.drop_column("ci_non_code_failure_count")
        batch_op.drop_column("ci_repair_verified_at")
        batch_op.drop_column("ci_repair_message_sent_at")
        batch_op.drop_column("last_ci_check_run_id")
        batch_op.drop_column("ci_repair_attempts")
        batch_op.drop_column("ci_failure_at")
        batch_op.drop_column("ci_conclusion")
        batch_op.drop_column("ci_check_url")
        batch_op.drop_column("ci_check_name")
        batch_op.drop_column("ci_classification_reason")
        batch_op.drop_column("failure_type")
