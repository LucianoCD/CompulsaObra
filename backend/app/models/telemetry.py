"""Modelos de telemetría verificable y contadores persistentes de seguridad."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

JSON_TYPE = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


class TractionEvent(Base):
    """Registro auditable de eventos de uso real en espacios no-demo (H-23, H-30)."""

    __tablename__ = "traction_events"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(
        sa.String(64), nullable=False, index=True
    )
    workspace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    comparison_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("comparison_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requisition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("requisitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON_TYPE, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class AuthSecurityCounter(Base):
    """Respaldo persistente en BD para rate limiting y lockouts cuando no hay Redis (H-34)."""

    __tablename__ = "auth_security_counters"

    counter_key: Mapped[str] = mapped_column(
        sa.String(255), primary_key=True
    )
    count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0
    )
    window_expires_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    blocked_until: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
