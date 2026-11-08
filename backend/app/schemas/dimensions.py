"""Esquemas Pydantic V2 para dimensiones físicas y normalización técnica."""

from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class PhysicalDimensions(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    diameter_inch: Optional[str] = Field(default=None, description="Diámetro nominal fraccionario (ej. '1/2', '3/4', '4')")
    diameter_mm: Optional[float] = Field(default=None, description="Diámetro convertido a milímetros (ej. 19.05, 110.0)")
    length_m: Optional[float] = Field(default=None, description="Longitud comercial en metros (ej. 12.0, 4.0)")
    weight_kg: Optional[float] = Field(default=None, description="Peso nominal por unidad en kilogramos (ej. 50.0)")
    material_type: Optional[str] = Field(default=None, description="Material constructivo (ej. 'Acero', 'PVC', 'Termofusión')")
    completeness: Literal["complete", "missing_critical_attribute", "user_resolved"] = Field(
        default="complete",
        description="Estado de completitud dimensional previa al emparejamiento",
    )


class NormalizedItemDraft(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_order: int = Field(default=1)
    raw_line: str
    requested_term: str
    quantity: float = Field(gt=0, default=1.0)
    requested_unit: str = Field(default="UN")
    diameter_inch: Optional[str] = None
    diameter_mm: Optional[float] = None
    length_m: Optional[float] = None
    weight_kg: Optional[float] = None
    material_type: Optional[str] = None
    completeness: Literal["complete", "missing_critical_attribute", "user_resolved"] = "complete"
    clarification_prompt: Optional[str] = None
    is_confirmed: bool = False
