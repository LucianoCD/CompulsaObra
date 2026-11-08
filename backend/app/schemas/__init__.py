"""Exportación centralizada de esquemas Pydantic V2."""

from app.schemas.common import (
    BaseSchema,
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
)
from app.schemas.dimensions import (
    PhysicalDimensions,
    NormalizedItemDraft,
)
from app.schemas.vendor import (
    AcopioConfigSchema,
    VendorCreateRequest,
    VendorResponse,
    ColumnMappingSchema,
    CatalogImportSummary,
    VendorProductResponse,
)
from app.schemas.requisition import (
    RequisitionIngestRequest,
    ItemClarificationResolveRequest,
    RequisitionItemResponse,
    RequisitionDetailResponse,
    RequisitionExtractionBatch,
)
from app.schemas.comparison import (
    RunComparisonRequest,
    ManualVendorMatchOverride,
    ComparisonVendorSummary,
    ComparisonItemCell,
    ComparisonItemRow,
    SplitCartSummary,
    ComparisonMatrixResponse,
    TractionMetricsResponse,
    LockBudgetResponse,
)

__all__ = [
    "BaseSchema",
    "ErrorDetail",
    "ErrorResponse",
    "PaginatedResponse",
    "PhysicalDimensions",
    "NormalizedItemDraft",
    "AcopioConfigSchema",
    "VendorCreateRequest",
    "VendorResponse",
    "ColumnMappingSchema",
    "CatalogImportSummary",
    "VendorProductResponse",
    "RequisitionIngestRequest",
    "ItemClarificationResolveRequest",
    "RequisitionItemResponse",
    "RequisitionDetailResponse",
    "RequisitionExtractionBatch",
    "RunComparisonRequest",
    "ManualVendorMatchOverride",
    "ComparisonVendorSummary",
    "ComparisonItemCell",
    "ComparisonItemRow",
    "SplitCartSummary",
    "ComparisonMatrixResponse",
    "TractionMetricsResponse",
    "LockBudgetResponse",
]
