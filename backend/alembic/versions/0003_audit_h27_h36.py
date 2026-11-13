"""Harden verification tokens, comparison run locking, traction events, and persistent rate limit counters (H-28, H-29, H-30, H-31, H-32, H-34).

Revision ID: 0003_audit_h27_h36
Revises: 0002_audit_h01_h26
Create Date: 2026-11-13 03:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_audit_h27_h36"
down_revision: Union[str, None] = "0002_audit_h01_h26"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON_TYPE = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("verification_token")
        batch_op.add_column(sa.Column("verification_token_hash", sa.String(64), nullable=True))
        batch_op.add_column(
            sa.Column("verification_token_expires_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("verification_sent_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.add_column(
        "comparison_runs",
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "comparison_runs",
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "comparison_runs",
        sa.Column("locked_strategy", sa.String(20), nullable=True),
    )
    op.add_column(
        "comparison_runs",
        sa.Column("locked_single_vendor_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.add_column(
        "comparison_runs",
        sa.Column("locked_snapshot_hash", sa.String(64), nullable=True),
    )
    op.create_index("ix_comparison_runs_is_locked", "comparison_runs", ["is_locked"], unique=False)

    op.create_table(
        "traction_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column(
            "workspace_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "comparison_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("comparison_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "requisition_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("requisitions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metadata_json", JSON_TYPE, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_traction_events_event_type", "traction_events", ["event_type"], unique=False)
    op.create_index("ix_traction_events_workspace_id", "traction_events", ["workspace_id"], unique=False)
    op.create_index("ix_traction_events_user_id", "traction_events", ["user_id"], unique=False)
    op.create_index("ix_traction_events_comparison_run_id", "traction_events", ["comparison_run_id"], unique=False)
    op.create_index("ix_traction_events_created_at", "traction_events", ["created_at"], unique=False)

    op.create_table(
        "auth_security_counters",
        sa.Column("counter_key", sa.String(255), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("auth_security_counters")

    op.drop_index("ix_traction_events_created_at", table_name="traction_events")
    op.drop_index("ix_traction_events_comparison_run_id", table_name="traction_events")
    op.drop_index("ix_traction_events_user_id", table_name="traction_events")
    op.drop_index("ix_traction_events_workspace_id", table_name="traction_events")
    op.drop_index("ix_traction_events_event_type", table_name="traction_events")
    op.drop_table("traction_events")

    op.drop_index("ix_comparison_runs_is_locked", table_name="comparison_runs")
    with op.batch_alter_table("comparison_runs") as batch_op:
        batch_op.drop_column("locked_snapshot_hash")
        batch_op.drop_column("locked_single_vendor_id")
        batch_op.drop_column("locked_strategy")
        batch_op.drop_column("locked_at")
        batch_op.drop_column("is_locked")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("verification_sent_at")
        batch_op.drop_column("verification_token_expires_at")
        batch_op.drop_column("verification_token_hash")
        batch_op.add_column(sa.Column("verification_token", sa.String(128), nullable=True))
