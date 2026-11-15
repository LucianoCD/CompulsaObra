"""Esquemas Pydantic V2 para Vendors, Reglas de Acopio y Catálogos."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class AcopioConfigSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled: bool = Field(default=False)
    min_down_payment_pct: float = Field(default=100.0, ge=0.0, le=100.0)
    freeze_days: int = Field(default=30, ge=1, le=3650)
    max_withdrawal_days: int = Field(default=60, ge=1, le=3650)
    min_notice_hours: int = Field(default=24, ge=0, le=720)
    price_basis: str = Field(default="LIST", pattern="^(LIST|CASH)$")


class VendorCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    locality: str = Field(min_length=2, max_length=80)
    whatsapp_phone: Optional[str] = Field(default=None, max_length=30)
    cash_discount_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    estimate_delivery_fee_ars: float = Field(default=0.0, ge=0.0, le=100_000_000.0)
    acopio_config: Optional[AcopioConfigSchema] = None


class VendorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: Optional[uuid.UUID] = None
    name: str
    locality: str
    whatsapp_phone: Optional[str] = None
    is_public_directory: bool = False
    cash_discount_pct: float = 0.0
    estimate_delivery_fee_ars: float = 0.0
    acopio_config_json: Dict[str, Any]
    created_at: datetime


class ColumnMappingSchema(BaseModel):
    sku_col: str = Field(default="sku", description="Nombre de columna para SKU o código")
    desc_col: str = Field(default="descripcion", description="Nombre de columna para descripción")
    price_cash_col: str = Field(default="precio_contado", description="Columna para precio contado/efectivo")
    price_list_col: Optional[str] = Field(default=None, description="Columna para precio de lista/financiado")
    unit_col: Optional[str] = Field(default=None, description="Columna para unidad de medida (UN, M, KG)")
    brand_col: Optional[str] = Field(default=None, description="Columna para marca comercial")
    category_col: Optional[str] = Field(default=None, description="Columna para rubro o categoría")


class CatalogImportSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    price_list_id: uuid.UUID
    vendor_id: uuid.UUID
    version_number: int
    total_rows: int
    new_or_updated_rows: int
    unchanged_skipped_rows: int
    skipped_invalid_rows: int = 0
    source_filename: str


class VendorProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    raw_description: str
    normalized_description: str
    brand: Optional[str] = None
    brand_tier: str = "STANDARD"
    category: Optional[str] = None
    sale_unit: str = "UN"
    price_cash_ars: float
    price_list_ars: float
    stock_available: bool = True
    diameter_mm: Optional[float] = None
    length_m: Optional[float] = None
    weight_kg: Optional[float] = None
    material_type: Optional[str] = None
    row_sha256: str
