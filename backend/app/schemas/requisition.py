"""Esquemas Pydantic V2 para Requisiciones, Ingesta Multimodal y Desambiguación."""

import uuid
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.dimensions import NormalizedItemDraft


class RequisitionIngestRequest(BaseModel):
    title: str = Field(default="Pedido de Materiales", min_length=2, max_length=160)
    client_name: Optional[str] = Field(default=None, max_length=140)
    raw_text: Optional[str] = None
    preset_id: Optional[str] = None


class ItemClarificationResolveRequest(BaseModel):
    diameter_mm: Optional[float] = None
    length_m: Optional[float] = None
    weight_kg: Optional[float] = None
    material_type: Optional[str] = None
    confirmed_term: Optional[str] = None
    quantity: Optional[float] = Field(default=None, gt=0)
    requested_unit: Optional[str] = Field(default=None, min_length=1, max_length=24)
    save_as_alias: bool = False
    vendor_id: Optional[uuid.UUID] = None


class RequisitionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requisition_id: uuid.UUID
    line_order: int
    raw_line: str
    requested_term: str
    quantity: float
    requested_unit: str
    diameter_inch: Optional[str] = None
    diameter_mm: Optional[float] = None
    length_m: Optional[float] = None
    weight_kg: Optional[float] = None
    material_type: Optional[str] = None
    completeness: Literal["complete", "missing_critical_attribute", "user_resolved"]
    clarification_prompt: Optional[str] = None
    is_confirmed: bool


class RequisitionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    client_name: Optional[str] = None
    source_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    items: List[RequisitionItemResponse]
    pending_clarifications_count: int = 0


class RequisitionExtractionBatch(BaseModel):
    """Esquema de salida estructurada JSON para Gemini 2.5 Flash."""
    items: List[NormalizedItemDraft]
