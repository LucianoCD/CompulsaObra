"""Modelos SQLAlchemy 2.0 para Requisition y RequisitionItem."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from decimal import Decimal
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Requisition(Base):
    __tablename__ = "requisitions"
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('DRAFT_EXTRACTED', 'NEEDS_CLARIFICATION', 'READY_TO_COMPARE', 'COMPARED', 'LOCKED_BUDGET')",
            name="chk_requisition_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    client_name: Mapped[Optional[str]] = mapped_column(sa.String(140), nullable=True)
    source_type: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, default="TEXT"
    )  # 'IMAGE' | 'TEXT' | 'SPREADSHEET'
    raw_input_text: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    status: Mapped[str] = mapped_column(
        sa.String(30), nullable=False, default="DRAFT_EXTRACTED", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relaciones
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="requisitions")
    items: Mapped[List["RequisitionItem"]] = relationship(
        "RequisitionItem",
        back_populates="requisition",
        cascade="all, delete-orphan",
        order_by="RequisitionItem.line_order",
    )
    comparison_runs: Mapped[List["ComparisonRun"]] = relationship(
        "ComparisonRun", back_populates="requisition", cascade="all, delete-orphan"
    )


class RequisitionItem(Base):
    __tablename__ = "requisition_items"
    __table_args__ = (
        sa.UniqueConstraint("requisition_id", "line_order", name="uq_requisition_line_order"),
        sa.CheckConstraint("quantity > 0", name="chk_requisition_item_quantity_positive"),
        sa.CheckConstraint(
            "completeness IN ('complete', 'missing_critical_attribute', 'user_resolved')",
            name="chk_requisition_item_completeness",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    requisition_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("requisitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    line_order: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    raw_line: Mapped[str] = mapped_column(sa.Text, nullable=False)
    requested_term: Mapped[str] = mapped_column(sa.String(200), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    requested_unit: Mapped[str] = mapped_column(sa.String(40), nullable=False, default="UN")
    diameter_inch: Mapped[Optional[str]] = mapped_column(sa.String(20), nullable=True)
    diameter_mm: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(8, 2), nullable=True)
    length_m: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(8, 2), nullable=True)
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(8, 2), nullable=True)
    material_type: Mapped[Optional[str]] = mapped_column(sa.String(60), nullable=True)
    completeness: Mapped[str] = mapped_column(
        sa.String(40), nullable=False, default="complete", index=True
    )
    clarification_prompt: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)

    # Relaciones
    requisition: Mapped["Requisition"] = relationship("Requisition", back_populates="items")
    matches: Mapped[List["ComparisonItemMatch"]] = relationship(
        "ComparisonItemMatch", back_populates="requisition_item", cascade="all, delete-orphan"
    )
