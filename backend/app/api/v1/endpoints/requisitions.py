"""Endpoints para Ingesta Multimodal, Requisiciones y Desambiguación Human-in-the-Loop."""

import uuid
from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.config import settings
from app.core.security import read_upload_file_bounded
from app.models.workspace import Workspace
from app.models.vendor import ProductAlias, Vendor, VendorProduct, PriceList
from app.models.requisition import Requisition, RequisitionItem
from app.schemas.dimensions import NormalizedItemDraft
from app.schemas.requisition import (
    RequisitionIngestRequest,
    ItemClarificationResolveRequest,
    RequisitionDetailResponse,
    RequisitionItemResponse,
)
from app.api.deps import get_current_workspace
from app.services.multimodal_extractor import MultimodalExtractorService
from app.services.traction_service import record_traction_event
from app.services.unit_normalizer import normalize_material_label, MATERIAL_FAMILIES, strip_accents

router = APIRouter(prefix="/requisitions", tags=["Requisiciones y Desambiguación"])
extractor = MultimodalExtractorService()


def _build_detail_response(req: Requisition) -> RequisitionDetailResponse:
    item_responses = [
        RequisitionItemResponse(
            id=it.id,
            requisition_id=it.requisition_id,
            line_order=it.line_order,
            raw_line=it.raw_line,
            requested_term=it.requested_term,
            quantity=float(it.quantity),
            requested_unit=it.requested_unit,
            diameter_inch=it.diameter_inch,
            diameter_mm=float(it.diameter_mm) if it.diameter_mm is not None else None,
            length_m=float(it.length_m) if it.length_m is not None else None,
            weight_kg=float(it.weight_kg) if it.weight_kg is not None else None,
            material_type=it.material_type,
            completeness=it.completeness,
            clarification_prompt=it.clarification_prompt,
            is_confirmed=it.is_confirmed,
        )
        for it in req.items
    ]
    pending = sum(1 for it in req.items if not it.is_confirmed)
    return RequisitionDetailResponse(
        id=req.id,
        workspace_id=req.workspace_id,
        title=req.title,
        client_name=req.client_name,
        source_type=req.source_type,
        status=req.status,
        created_at=req.created_at,
        updated_at=req.updated_at,
        items=item_responses,
        pending_clarifications_count=pending,
    )


def _create_requisition_from_drafts(
    db: Session,
    current_ws: Workspace,
    title: str,
    client_name: Optional[str],
    source_type: str,
    raw_input_text: str,
    draft_items: List[NormalizedItemDraft],
) -> RequisitionDetailResponse:
    """Helper DRY para instanciar y persistir una Requisition con sus ítems."""
    has_ambiguity = any(it.completeness == "missing_critical_attribute" for it in draft_items)
    initial_status = "NEEDS_CLARIFICATION" if has_ambiguity else "READY_TO_COMPARE"

    req = Requisition(
        id=uuid.uuid4(),
        workspace_id=current_ws.id,
        title=title,
        client_name=client_name,
        source_type=source_type,
        raw_input_text=raw_input_text,
        status=initial_status,
    )
    db.add(req)
    db.flush()

    db_items: List[RequisitionItem] = []
    for d in draft_items:
        it = RequisitionItem(
            id=uuid.uuid4(),
            requisition_id=req.id,
            line_order=d.line_order,
            raw_line=d.raw_line,
            requested_term=d.requested_term,
            quantity=Decimal(str(d.quantity)),
            requested_unit=d.requested_unit,
            diameter_inch=d.diameter_inch,
            diameter_mm=Decimal(str(d.diameter_mm)) if d.diameter_mm is not None else None,
            length_m=Decimal(str(d.length_m)) if d.length_m is not None else None,
            weight_kg=Decimal(str(d.weight_kg)) if d.weight_kg is not None else None,
            material_type=d.material_type,
            completeness=d.completeness,
            clarification_prompt=d.clarification_prompt,
            is_confirmed=d.is_confirmed,
        )
        db_items.append(it)

    db.add_all(db_items)
    record_traction_event(
        db,
        event_type="REQUISITION_CREATED",
        workspace_id=current_ws.id,
        requisition_id=req.id,
        is_demo=current_ws.is_demo,
        metadata={"items_count": len(db_items), "source_type": source_type},
    )
    db.commit()
    db.refresh(req)

    return _build_detail_response(req)


@router.post("/ingest", response_model=RequisitionDetailResponse, status_code=status.HTTP_201_CREATED)
async def ingest_requisition(
    title: str = Form(default="Pedido de Materiales"),
    client_name: Optional[str] = Form(default=None),
    raw_text: Optional[str] = Form(default=None),
    preset_id: Optional[str] = Form(default=None),
    image_file: Optional[UploadFile] = File(default=None),
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Ingesta un pliego de materiales desde texto, foto manuscrita o preset de demostración."""
    image_bytes = None
    mime_type = "image/jpeg"
    source_type = "TEXT"

    if image_file:
        content_type = image_file.content_type or "image/jpeg"
        if not (content_type.startswith("image/") or content_type == "application/octet-stream"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de imagen inválido. Solo se admiten archivos de imagen (JPEG, PNG, WebP).",
            )
        image_bytes = await read_upload_file_bounded(image_file, settings.MAX_UPLOAD_SIZE_BYTES)
        mime_type = content_type
        source_type = "IMAGE"
    elif preset_id:
        source_type = "TEXT"
    elif not raw_text:
        raise HTTPException(
            status_code=400,
            detail="Debe proporcionar al menos una imagen, texto libre o un preset_id.",
        )

    # Procesar con el servicio extractor
    draft_items = extractor.extract_requisition_items(
        raw_text=raw_text,
        image_bytes=image_bytes,
        preset_id=preset_id,
        mime_type=mime_type,
    )

    if not draft_items:
        raise HTTPException(
            status_code=400,
            detail="No se pudo extraer ningún renglón de materiales del pedido enviado.",
        )

    raw_input_desc = raw_text or (f"Preset: {preset_id}" if preset_id else "Subida de Imagen")
    return _create_requisition_from_drafts(
        db=db,
        current_ws=current_ws,
        title=title,
        client_name=client_name,
        source_type=source_type,
        raw_input_text=raw_input_desc,
        draft_items=draft_items,
    )


@router.post("/ingest-json", response_model=RequisitionDetailResponse, status_code=status.HTTP_201_CREATED)
def ingest_requisition_json(
    payload: RequisitionIngestRequest,
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Variante JSON directa para ingesta de texto o presets."""
    draft_items = extractor.extract_requisition_items(
        raw_text=payload.raw_text,
        preset_id=payload.preset_id,
    )

    if not draft_items:
        raise HTTPException(
            status_code=400,
            detail="No se pudo extraer ningún renglón de materiales del texto o preset enviado.",
        )

    raw_input_desc = payload.raw_text or f"Preset: {payload.preset_id}"
    return _create_requisition_from_drafts(
        db=db,
        current_ws=current_ws,
        title=payload.title,
        client_name=payload.client_name,
        source_type="TEXT",
        raw_input_text=raw_input_desc,
        draft_items=draft_items,
    )


@router.get("", response_model=List[RequisitionDetailResponse])
def list_requisitions(
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Lista las requisiciones del espacio de trabajo activo evitando consultas N+1."""
    reqs = db.scalars(
        select(Requisition)
        .options(selectinload(Requisition.items))
        .where(Requisition.workspace_id == current_ws.id)
        .order_by(Requisition.created_at.desc())
    ).all()
    return [_build_detail_response(r) for r in reqs]


@router.get("/{req_id}", response_model=RequisitionDetailResponse)
def get_requisition(
    req_id: uuid.UUID,
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Obtiene el pliego técnico completo de materiales con estado de confirmación."""
    req = db.scalar(
        select(Requisition)
        .options(selectinload(Requisition.items))
        .where(
            Requisition.id == req_id, Requisition.workspace_id == current_ws.id
        )
    )
    if not req:
        raise HTTPException(status_code=404, detail="Requisición no encontrada")
    return _build_detail_response(req)


@router.patch("/{req_id}/items/{item_id}/resolve", response_model=RequisitionDetailResponse)
def resolve_item_ambiguity(
    req_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ItemClarificationResolveRequest,
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Consola Human-in-the-Loop: define atributos faltantes con validación dimensional estricta (CO-03)."""
    req = db.scalar(
        select(Requisition).where(
            Requisition.id == req_id, Requisition.workspace_id == current_ws.id
        )
    )
    if not req:
        raise HTTPException(status_code=404, detail="Requisición no encontrada")

    if req.status == "LOCKED_BUDGET":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El presupuesto está congelado (LOCKED_BUDGET) y no admite modificaciones.",
        )

    item = db.scalar(
        select(RequisitionItem).where(
            RequisitionItem.id == item_id, RequisitionItem.requisition_id == req.id
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado en esta requisición")

    # Actualizar campos resueltos o edición inline de cantidad/unidad
    if payload.quantity is not None:
        item.quantity = Decimal(str(payload.quantity))
    if payload.requested_unit is not None:
        item.requested_unit = payload.requested_unit.strip().upper()
    if payload.diameter_mm is not None:
        item.diameter_mm = Decimal(str(payload.diameter_mm))
    if payload.length_m is not None:
        item.length_m = Decimal(str(payload.length_m))
    if payload.weight_kg is not None:
        item.weight_kg = Decimal(str(payload.weight_kg))
    if payload.material_type is not None:
        item.material_type = normalize_material_label(payload.material_type)
    if payload.confirmed_term is not None:
        item.requested_term = payload.confirmed_term

    # Validación Human-in-the-Loop estricta (Cierre de CO-03 / CO-04: Bloqueo de bypass con body vacío {})
    provided_updates = payload.model_dump(exclude_unset=True)
    if not item.is_confirmed and not provided_updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Debe suministrar al menos un atributo técnico (como material constructivo o diámetro) para resolver la ambigüedad del ítem.",
        )

    technical_attr_keys = {
        "diameter_mm",
        "length_m",
        "weight_kg",
        "material_type",
        "confirmed_term",
    }
    only_quantity_or_unit_edit = (
        bool({"quantity", "requested_unit"} & set(provided_updates.keys()))
        and not (technical_attr_keys & set(provided_updates.keys()))
    )
    if only_quantity_or_unit_edit:
        db.commit()
        db.refresh(req)
        return _build_detail_response(req)

    norm_context = strip_accents(f"{item.requested_term} {item.raw_line}").lower()
    is_critical_fam = any(fam in norm_context for fam in MATERIAL_FAMILIES)
    if is_critical_fam:
        if not item.material_type or item.diameter_mm is None or float(item.diameter_mm) <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No se puede confirmar el ítem: debe especificar obligatoriamente el material constructivo y el diámetro físico.",
            )

    is_steel_fam = any(s in norm_context for s in ["barra", "hierro", "acero", "malla", "alambre"])
    if is_steel_fam:
        if item.diameter_mm is None or float(item.diameter_mm) <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No se puede confirmar el ítem: debe especificar obligatoriamente el diámetro nominal de la barra o hierro.",
            )

    if payload.material_type and not payload.confirmed_term:
        if payload.material_type.lower() not in item.requested_term.lower():
            item.requested_term = f"{item.requested_term} {item.material_type}".strip()

    item.completeness = "user_resolved"
    item.is_confirmed = True
    item.clarification_prompt = None

    # Si solicitó guardar como alias supervisado en el workspace (H-11: vincula producto real si existe y guarda canonical_term)
    if payload.save_as_alias:
        alias_term = item.requested_term.strip()
        raw_term = item.raw_line.strip()
        target_prod_id: Optional[uuid.UUID] = None

        # Buscar producto compatible en el comercio especificado (o catálogo accesible) para enlazar target_vendor_product_id
        from sqlalchemy import or_ as sql_or
        vp_stmt = (
            select(VendorProduct)
            .join(PriceList, VendorProduct.price_list_id == PriceList.id)
            .join(Vendor, VendorProduct.vendor_id == Vendor.id)
            .where(
                PriceList.is_active.is_(True),
                sql_or(Vendor.workspace_id == current_ws.id, Vendor.is_public_directory.is_(True)),
            )
        )
        if payload.vendor_id:
            vp_stmt = vp_stmt.where(VendorProduct.vendor_id == payload.vendor_id)
        if item.diameter_mm is not None:
            vp_stmt = vp_stmt.where(VendorProduct.diameter_mm.is_not(None))
            from sqlalchemy import func as sql_func
            vp_stmt = vp_stmt.where(sql_func.abs(VendorProduct.diameter_mm - item.diameter_mm) <= Decimal("0.5"))
        if item.material_type:
            mat_clean = strip_accents(item.material_type).lower()
            vp_stmt = vp_stmt.where(
                sql_func.lower(sql_func.coalesce(VendorProduct.material_type, VendorProduct.normalized_description)).contains(mat_clean)
            )
        matching_vps = db.scalars(vp_stmt).all()
        if len(matching_vps) == 1:
            target_prod_id = matching_vps[0].id

        for term_to_save in {alias_term, raw_term}:
            existing_alias = db.scalar(
                select(ProductAlias).where(
                    ProductAlias.workspace_id == current_ws.id,
                    ProductAlias.vendor_id == payload.vendor_id,
                    ProductAlias.alias_term == term_to_save,
                )
            )
            if existing_alias:
                existing_alias.canonical_term = item.requested_term
                if target_prod_id is not None:
                    existing_alias.target_vendor_product_id = target_prod_id
                existing_alias.is_active = True
            else:
                db.add(
                    ProductAlias(
                        id=uuid.uuid4(),
                        workspace_id=current_ws.id,
                        vendor_id=payload.vendor_id,
                        alias_term=term_to_save,
                        canonical_term=item.requested_term,
                        target_vendor_product_id=target_prod_id,
                        is_active=True,
                    )
                )

    # Verificar si todos los ítems de la requisición están confirmados
    all_confirmed = all(it.is_confirmed for it in req.items)
    if all_confirmed:
        req.status = "READY_TO_COMPARE"

    record_traction_event(
        db,
        event_type="ITEM_DISAMBIGUATED",
        workspace_id=current_ws.id,
        requisition_id=req.id,
        is_demo=current_ws.is_demo,
        metadata={"item_id": str(item.id)},
    )
    db.commit()
    db.refresh(req)
    return _build_detail_response(req)

