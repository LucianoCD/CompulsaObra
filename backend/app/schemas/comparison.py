"""Esquemas Pydantic V2 para Matriz Comparativa, Split Cart, Acopio, Presupuesto Público y Métricas."""

import uuid
from datetime import datetime
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class _SubscriptableSchema(BaseModel):
    """Permite acceso por atributo o subíndice dict-compatible sin relajar tipado Pydantic V2."""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        if self.__pydantic_extra__ and key in self.__pydantic_extra__:
            return self.__pydantic_extra__[key]
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return hasattr(self, key) or bool(self.__pydantic_extra__ and key in self.__pydantic_extra__)


class CandidateOptionSchema(_SubscriptableSchema):
    vendor_product_id: str
    sku: str
    description: str
    sale_unit: Optional[str] = None
    score: Optional[float] = None
    similarity_score: Optional[float] = None


class OverrideAuditEntrySchema(_SubscriptableSchema):
    timestamp: str
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    requisition_item_id: str
    vendor_id: str
    new_vendor_product_id: str
    new_product_id: Optional[str] = None
    discrepancies: List[str] = Field(default_factory=list)
    forced_exception: bool = False
    forced_override: bool = False
    reason: str = ""


class AcopioSummarySchema(_SubscriptableSchema):
    enabled: bool = True
    price_basis: Literal["LIST", "CASH"] = "LIST"
    min_down_payment_pct: float
    down_payment_ars: float
    remaining_balance_ars: float
    freeze_days: int
    freeze_until_date: str
    max_withdrawal_days: int
    max_withdrawal_date: str
    min_notice_hours: int


class RunComparisonRequest(BaseModel):
    vendor_ids: List[uuid.UUID] = Field(
        min_length=1,
        max_length=50,
        description="Lista de IDs de comercios a compulsar (máximo 50)",
    )
    payment_modality: Literal["CASH", "LIST", "ACOPIO"] = Field(default="CASH")
    markup_pct: float = Field(default=0.0, ge=0.0, description="Margen del presupuestador")
    include_delivery_fees: bool = Field(default=True, description="Incluir costo logístico de flete")
    budget_strategy: Literal["SPLIT_CART", "SINGLE_VENDOR"] = Field(
        default="SPLIT_CART",
        description="Estrategia seleccionada para el presupuesto final",
    )
    selected_single_vendor_id: Optional[uuid.UUID] = None
    existing_run_id: Optional[uuid.UUID] = None
    persist: bool = True


class ManualVendorMatchOverride(BaseModel):
    vendor_product_id: uuid.UUID
    save_vendor_alias: bool = False
    force_dimension_override: bool = False
    override_reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Justificación técnica obligatoria cuando existen discrepancias",
    )


class LockBudgetRequest(BaseModel):
    accept_partial: bool = False
    strategy: Literal["SPLIT_CART", "SINGLE_VENDOR"] = "SPLIT_CART"
    selected_single_vendor_id: Optional[uuid.UUID] = None


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
    acopio_summary: Optional[AcopioSummarySchema] = None


class ComparisonItemCell(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    match_id: Optional[uuid.UUID] = None
    vendor_id: uuid.UUID
    vendor_name: str
    match_status: Literal["EXACT_MATCH", "AMBIGUOUS_CANDIDATES", "OUT_OF_STOCK", "NOT_CARRIED"]
    vendor_product_id: Optional[uuid.UUID] = None
    product_sku: Optional[str] = None
    product_description: Optional[str] = None
    sale_unit: Optional[str] = None
    commercial_qty: Optional[float] = None
    conversion_note: Optional[str] = None
    unit_price_ars: Optional[float] = None
    line_subtotal_ars: Optional[float] = None
    similarity_score: Optional[float] = None
    is_best_price: bool = False
    is_selected_split: bool = False
    candidate_options: List[CandidateOptionSchema] = Field(default_factory=list)
    override_audit: Optional[OverrideAuditEntrySchema] = None


class ComparisonItemRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    requisition_item_id: uuid.UUID
    line_order: int
    requested_term: str
    quantity: float
    requested_unit: str
    diameter_mm: Optional[float] = None
    length_m: Optional[float] = None
    weight_kg: Optional[float] = None
    material_type: Optional[str] = None
    vendor_cells: List[ComparisonItemCell]
    lowest_unit_price_ars: Optional[float] = None
    lowest_line_subtotal_ars: Optional[float] = None
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
    requisition_version: int = 1
    requisition_version_hash: Optional[str] = None
    is_stale: bool = False
    stale_reason: Optional[str] = None
    status: str = "COMPARED"
    fulfillment_status: Literal["complete", "partial", "pending"] = "complete"
    unresolved_items_count: int = 0
    ambiguous_items_count: int = 0
    payment_modality: Literal["CASH", "LIST", "ACOPIO"]
    markup_pct: float
    include_delivery_fees: bool
    budget_strategy: Literal["SPLIT_CART", "SINGLE_VENDOR"] = "SPLIT_CART"
    selected_single_vendor_id: Optional[uuid.UUID] = None
    best_single_vendor_id: Optional[uuid.UUID] = None
    best_single_vendor_name: Optional[str] = None
    best_single_total_ars: Optional[float] = None
    split_cart: SplitCartSummary
    vendors: List[ComparisonVendorSummary]
    matrix_rows: List[ComparisonItemRow]
    public_share_token: str
    snapshot_content_hash: Optional[str] = None
    override_audit_log: List[OverrideAuditEntrySchema] = Field(default_factory=list)
    is_locked: bool = False
    locked_at: Optional[datetime] = None
    created_at: datetime


class PublicClientBudgetItemRow(BaseModel):
    """DTO público estricto con lista blanca de campos permitidos para el cliente final (H-03)."""

    model_config = ConfigDict(from_attributes=True)

    requisition_item_id: uuid.UUID
    line_order: int
    canonical_name: str
    requested_qty: float
    requested_unit: str
    commercial_qty: Optional[float] = None
    sale_unit: Optional[str] = None
    conversion_note: Optional[str] = None
    client_unit_price_ars: Optional[float] = None
    client_subtotal_ars: Optional[float] = None
    covered: bool = True


class PublicClientBudgetResponse(BaseModel):
    """Respuesta pública independiente sin nombres de proveedores, costos internos ni márgenes (H-03)."""

    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    requisition_id: uuid.UUID
    title: str
    client_name: Optional[str] = None
    status: str
    fulfillment_status: Literal["complete", "partial", "pending"] = "complete"
    budget_strategy: Literal["SPLIT_CART", "SINGLE_VENDOR"] = "SPLIT_CART"
    payment_modality: Literal["CASH", "LIST", "ACOPIO"]
    items: List[PublicClientBudgetItemRow]
    materials_subtotal_ars: float
    logistics_ars: float
    grand_total_ars: float
    created_at: datetime
    locked_at: Optional[datetime] = None
    is_simulation: bool = False
    signature_verified: bool = True


class TractionMetricsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    active_real_workspaces: int
    active_real_users: int = 0
    real_vendors_compared: int
    real_budgets_generated: int
    verified_usage_events: int = 0
    total_lines_processed: int
    median_elaboration_seconds: float


class LockBudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    public_share_token: str
    share_url: str
    pdf_url: str
    status: str = "LOCKED_BUDGET"
    fulfillment_status: Literal["complete", "partial", "pending"] = "complete"
    budget_strategy: Literal["SPLIT_CART", "SINGLE_VENDOR"] = "SPLIT_CART"
    snapshot_content_hash: str
