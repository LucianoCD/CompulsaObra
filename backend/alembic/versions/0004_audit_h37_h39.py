"""Add requisition versioning and comparison run staleness tracking (H-39).

Revision ID: 0004_audit_h37_h39
Revises: 0003_audit_h27_h36
Create Date: 2026-11-14 02:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0004_audit_h37_h39"
down_revision: Union[str, None] = "0003_audit_h27_h36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "requisitions",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "comparison_runs",
        sa.Column("requisition_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "comparison_runs",
        sa.Column("requisition_version_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "comparison_runs",
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    with op.batch_alter_table("comparison_runs") as batch_op:
        batch_op.drop_column("is_stale")
        batch_op.drop_column("requisition_version_hash")
        batch_op.drop_column("requisition_version")
    with op.batch_alter_table("requisitions") as batch_op:
        batch_op.drop_column("version")
