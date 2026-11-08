"""Esquemas Pydantic V2 para Matriz Comparativa, Split Cart, Acopio y Métricas."""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class RunComparisonRequest(BaseModel):
    vendor_ids: List[uuid.UUID] = Field(min_length=1, description="Lista de IDs de comercios a compulsa")
    payment_modality: Literal["CASH", "LIST", "ACOPIO"] = Field(default="CASH")
    markup_pct: float = Field(default=0.0, ge=0.0, description="Margen del presupuestador")
    include_delivery_fees: bool = Field(default=True, description="Incluir costo logístico de flete")


class ManualVendorMatchOverride(BaseModel):
    vendor_product_id: uuid.UUID
    save_vendor_alias: bool = False
    force_dimension_override: bool = False


class ComparisonVendorSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vendor_id: uuid.UUID
    vendor_name: str
    locality: str
    coverage_pct: float
    matched_items_count: int
    missing_items_count: int
    materials_subtotal_ars: float
    delivery_fee_ars: float
    total_with_delivery_ars: float
    acopio_summary: Optional[Dict[str, Any]] = None


class ComparisonItemCell(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    match_id: Optional[uuid.UUID] = None
    vendor_id: uuid.UUID
    vendor_name: str
    match_status: Literal["EXACT_MATCH", "AMBIGUOUS_CANDIDATES", "OUT_OF_STOCK", "NOT_CARRIED"]
    vendor_product_id: Optional[uuid.UUID] = None
    product_sku: Optional[str] = None
    product_description: Optional[str] = None
    unit_price_ars: Optional[float] = None
    line_subtotal_ars: Optional[float] = None
    similarity_score: Optional[float] = None
    is_best_price: bool = False
    is_selected_split: bool = False


class ComparisonItemRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    requisition_item_id: uuid.UUID
    line_order: int
    requested_term: str
    quantity: float
    requested_unit: str
    diameter_mm: Optional[float] = None
    material_type: Optional[str] = None
    vendor_cells: List[ComparisonItemCell]
    lowest_price_ars: Optional[float] = None
    winning_vendor_id: Optional[uuid.UUID] = None


class SplitCartSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_materials_ars: float
    total_delivery_fees_ars: float
    total_cart_ars: float
    participating_vendors_count: int
    participating_vendor_names: List[str]
    savings_vs_single_vendor_ars: float
    is_split_recommended: bool


class ComparisonMatrixResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    requisition_id: uuid.UUID
    payment_modality: Literal["CASH", "LIST", "ACOPIO"]
    markup_pct: float
    include_delivery_fees: bool
    best_single_vendor_id: Optional[uuid.UUID] = None
    best_single_vendor_name: Optional[str] = None
    best_single_total_ars: Optional[float] = None
    split_cart: SplitCartSummary
    vendors: List[ComparisonVendorSummary]
    matrix_rows: List[ComparisonItemRow]
    public_share_token: str
    created_at: datetime


class TractionMetricsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    active_real_workspaces: int
    real_vendors_compared: int
    real_budgets_generated: int
    total_lines_processed: int
    median_elaboration_seconds: float


class LockBudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    public_share_token: str
    share_url: str
    pdf_url: str
    status: str = "LOCKED_BUDGET"
