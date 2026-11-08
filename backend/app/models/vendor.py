"""Modelos SQLAlchemy 2.0 para Vendor, PriceList, VendorProduct y ProductAlias."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from decimal import Decimal
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects import postgresql

from app.core.database import Base

JSON_TYPE = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")
TSVECTOR_TYPE = postgresql.TSVECTOR().with_variant(sa.Text(), "sqlite")


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(140), nullable=False)
    locality: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    whatsapp_phone: Mapped[Optional[str]] = mapped_column(sa.String(30), nullable=True)
    is_public_directory: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, index=True
    )
    cash_discount_pct: Mapped[Decimal] = mapped_column(
        sa.Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    estimate_delivery_fee_ars: Mapped[Decimal] = mapped_column(
        sa.Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    acopio_config_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=lambda: {
            "enabled": False,
            "min_down_payment_pct": 100.0,
            "freeze_days": 30,
            "max_withdrawal_days": 60,
            "min_notice_hours": 24,
        },
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relaciones
    workspace: Mapped[Optional["Workspace"]] = relationship("Workspace", back_populates="vendors")
    price_lists: Mapped[List["PriceList"]] = relationship(
        "PriceList", back_populates="vendor", cascade="all, delete-orphan"
    )
    products: Mapped[List["VendorProduct"]] = relationship(
        "VendorProduct", back_populates="vendor", cascade="all, delete-orphan"
    )
    matches: Mapped[List["ComparisonItemMatch"]] = relationship(
        "ComparisonItemMatch", back_populates="vendor", cascade="all, delete-orphan"
    )


class PriceList(Base):
    __tablename__ = "price_lists"
    __table_args__ = (
        sa.UniqueConstraint("vendor_id", "version_number", name="uq_vendor_price_list_version"),
        sa.CheckConstraint("version_number >= 1", name="chk_price_list_version_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    source_filename: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    valid_until: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    row_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True, index=True)

    # Relaciones
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="price_lists")
    products: Mapped[List["VendorProduct"]] = relationship(
        "VendorProduct", back_populates="price_list", cascade="all, delete-orphan"
    )


class VendorProduct(Base):
    __tablename__ = "vendor_products"
    __table_args__ = (
        sa.CheckConstraint(
            "price_cash_ars > 0 AND price_list_ars > 0",
            name="chk_vendor_product_positive_prices",
        ),
        sa.Index(
            "idx_vendor_products_dim",
            "vendor_id",
            "diameter_mm",
            "length_m",
            "weight_kg",
        ),
        sa.Index(
            "idx_vendor_products_trgm",
            "normalized_description",
            postgresql_using="gin",
            postgresql_ops={"normalized_description": "gin_trgm_ops"},
        ),
        sa.Index(
            "idx_vendor_products_fts",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    price_list_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("price_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(sa.String(80), nullable=False, index=True)
    raw_description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    normalized_description: Mapped[str] = mapped_column(sa.Text, nullable=False, index=True)
    brand: Mapped[Optional[str]] = mapped_column(sa.String(80), nullable=True)
    brand_tier: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="STANDARD")
    category: Mapped[Optional[str]] = mapped_column(sa.String(80), nullable=True)
    sale_unit: Mapped[str] = mapped_column(sa.String(30), nullable=False, default="UN")
    price_cash_ars: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2), nullable=False)
    price_list_ars: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2), nullable=False)
    stock_available: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    diameter_mm: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(8, 2), nullable=True)
    length_m: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(8, 2), nullable=True)
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(8, 2), nullable=True)
    material_type: Mapped[Optional[str]] = mapped_column(sa.String(60), nullable=True)
    row_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR_TYPE, nullable=True)

    # Relaciones
    price_list: Mapped["PriceList"] = relationship("PriceList", back_populates="products")
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="products")


class ProductAlias(Base):
    __tablename__ = "product_aliases"
    __table_args__ = (
        sa.UniqueConstraint(
            "workspace_id", "vendor_id", "alias_term", name="uq_workspace_vendor_alias"
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
    vendor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    alias_term: Mapped[str] = mapped_column(sa.String(180), nullable=False, index=True)
    canonical_term: Mapped[str] = mapped_column(sa.String(180), nullable=False)
    target_vendor_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("vendor_products.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relaciones
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="aliases")
    target_product: Mapped[Optional["VendorProduct"]] = relationship("VendorProduct")
