"""Modelos SQLAlchemy 2.0 para ComparisonRun y ComparisonItemMatch."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from decimal import Decimal
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects import postgresql

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.requisition import Requisition, RequisitionItem
    from app.models.vendor import Vendor, VendorProduct
    from app.models.workspace import Workspace

JSON_TYPE = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


class ComparisonRun(Base):
    __tablename__ = "comparison_runs"
    __table_args__ = (
        sa.CheckConstraint(
            "payment_modality IN ('CASH', 'LIST', 'ACOPIO')",
            name="chk_comparison_payment_modality",
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
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_modality: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, default="CASH"
    )  # 'CASH' | 'LIST' | 'ACOPIO'
    markup_pct: Mapped[Decimal] = mapped_column(
        sa.Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    best_single_vendor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("vendors.id", ondelete="SET NULL"),
        nullable=True,
    )
    best_single_total_ars: Mapped[Optional[Decimal]] = mapped_column(
        sa.Numeric(14, 2), nullable=True
    )
    split_cart_total_ars: Mapped[Optional[Decimal]] = mapped_column(
        sa.Numeric(14, 2), nullable=True
    )
    split_cart_savings_ars: Mapped[Optional[Decimal]] = mapped_column(
        sa.Numeric(14, 2), nullable=True
    )
    comparison_matrix_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON_TYPE, nullable=False, default=dict
    )
    public_share_token: Mapped[str] = mapped_column(
        sa.String(128), unique=True, nullable=False, index=True
    )
    is_locked: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, index=True
    )
    locked_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    locked_strategy: Mapped[Optional[str]] = mapped_column(
        sa.String(20), nullable=True
    )
    locked_single_vendor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), nullable=True
    )
    locked_snapshot_hash: Mapped[Optional[str]] = mapped_column(
        sa.String(64), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relaciones
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="comparison_runs")
    requisition: Mapped["Requisition"] = relationship("Requisition", back_populates="comparison_runs")
    best_single_vendor: Mapped[Optional["Vendor"]] = relationship("Vendor")
    matches: Mapped[List["ComparisonItemMatch"]] = relationship(
        "ComparisonItemMatch",
        back_populates="comparison_run",
        cascade="all, delete-orphan",
    )


class ComparisonItemMatch(Base):
    __tablename__ = "comparison_item_matches"
    __table_args__ = (
        sa.CheckConstraint(
            "match_status IN ('EXACT_MATCH', 'AMBIGUOUS_CANDIDATES', 'OUT_OF_STOCK', 'NOT_CARRIED')",
            name="chk_item_match_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    comparison_run_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("comparison_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requisition_item_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("requisition_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vendor_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("vendor_products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    match_status: Mapped[str] = mapped_column(
        sa.String(30), nullable=False, default="NOT_CARRIED"
    )  # 'EXACT_MATCH' | 'AMBIGUOUS_CANDIDATES' | 'OUT_OF_STOCK' | 'NOT_CARRIED'
    unit_price_applied_ars: Mapped[Optional[Decimal]] = mapped_column(
        sa.Numeric(14, 2), nullable=True
    )
    line_subtotal_ars: Mapped[Optional[Decimal]] = mapped_column(
        sa.Numeric(14, 2), nullable=True
    )
    similarity_score: Mapped[Optional[Decimal]] = mapped_column(
        sa.Numeric(5, 4), nullable=True
    )
    is_selected_for_split_cart: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False
    )

    # Relaciones
    comparison_run: Mapped["ComparisonRun"] = relationship("ComparisonRun", back_populates="matches")
    requisition_item: Mapped["RequisitionItem"] = relationship("RequisitionItem", back_populates="matches")
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="matches")
    vendor_product: Mapped[Optional["VendorProduct"]] = relationship("VendorProduct")
