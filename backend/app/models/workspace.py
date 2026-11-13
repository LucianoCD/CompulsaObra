"""Modelos SQLAlchemy 2.0 para Workspace y User."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.comparison import ComparisonRun
    from app.models.requisition import Requisition
    from app.models.vendor import ProductAlias, Vendor


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    owner_role: Mapped[str] = mapped_column(
        sa.String(30), nullable=False, default="ESTIMATOR"
    )  # 'BUYER' | 'ESTIMATOR'
    is_demo: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relaciones
    users: Mapped[List["User"]] = relationship(
        "User", back_populates="workspace", cascade="all, delete-orphan"
    )
    vendors: Mapped[List["Vendor"]] = relationship(
        "Vendor", back_populates="workspace", cascade="all, delete-orphan"
    )
    requisitions: Mapped[List["Requisition"]] = relationship(
        "Requisition", back_populates="workspace", cascade="all, delete-orphan"
    )
    comparison_runs: Mapped[List["ComparisonRun"]] = relationship(
        "ComparisonRun", back_populates="workspace", cascade="all, delete-orphan"
    )
    aliases: Mapped[List["ProductAlias"]] = relationship(
        "ProductAlias", back_populates="workspace", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(sa.String(180), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        sa.String(30),
        sa.CheckConstraint("role IN ('BUYER', 'ESTIMATOR', 'ADMIN')", name="chk_user_role"),
        nullable=False,
        default="ESTIMATOR",
    )
    email_verified: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False
    )
    verification_token_hash: Mapped[Optional[str]] = mapped_column(
        sa.String(64), nullable=True
    )
    verification_token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    verification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="users")
