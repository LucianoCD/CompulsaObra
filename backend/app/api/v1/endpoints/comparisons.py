"""Endpoints para Ejecución de Compulsa, Optimización Split Cart, Congelamiento y PDF."""

import copy
import uuid
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import get_db
from app.models.workspace import Workspace
from app.models.requisition import Requisition
from app.models.comparison import ComparisonRun, ComparisonItemMatch
from app.models.vendor import Vendor, PriceList, VendorProduct, ProductAlias
from app.schemas.comparison import (
    RunComparisonRequest,
    ComparisonMatrixResponse,
    ManualVendorMatchOverride,
    LockBudgetResponse,
)
from app.api.deps import get_current_workspace
from app.services.comparison_optimizer import ComparisonOptimizerService
from app.services.pdf_generator import PDFGeneratorService
from app.core.exceptions import DimensionMismatchOverrideError, LockedBudgetModificationError

router = APIRouter(tags=["Compulsa y Optimización"])


@router.post("/requisitions/{req_id}/compare", response_model=ComparisonMatrixResponse)
def run_comparison(
    req_id: uuid.UUID,
    payload: RunComparisonRequest,
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Ejecuta la compulsa multi-negocio, optimización de carrito dividido y cálculo de acopio."""
    req = db.scalar(
        select(Requisition).where(
            Requisition.id == req_id, Requisition.workspace_id == current_ws.id
        )
    )
    if not req:
        raise HTTPException(status_code=404, detail="Requisición no encontrada")

    res = ComparisonOptimizerService.run_multi_vendor_comparison(
        db=db,
        requisition_id=req.id,
        vendor_ids=payload.vendor_ids,
        payment_modality=payload.payment_modality,
        markup_pct=payload.markup_pct,
        include_delivery_fees=payload.include_delivery_fees,
    )
    return res


@router.get("/comparisons/{run_id}", response_model=ComparisonMatrixResponse)
def get_comparison_run(
    run_id: uuid.UUID,
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Obtiene el resultado y matriz comparativa de una compulsa guardada."""
    run = db.scalar(
        select(ComparisonRun).where(
            ComparisonRun.id == run_id, ComparisonRun.workspace_id == current_ws.id
        )
    )
    if not run:
        raise HTTPException(status_code=404, detail="Compulsa no encontrada")

    return ComparisonMatrixResponse(**run.comparison_matrix_json)


@router.patch("/comparisons/{run_id}/matches/{match_id}", response_model=ComparisonMatrixResponse)
def override_item_match(
    run_id: uuid.UUID,
    match_id: uuid.UUID,
    payload: ManualVendorMatchOverride,
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Permite al presupuestador sustituir manualmente el producto asignado a un comercio con validación dimensional y recálculo."""
    run = db.scalar(
        select(ComparisonRun).where(
            ComparisonRun.id == run_id, ComparisonRun.workspace_id == current_ws.id
        )
    )
    if not run:
        raise HTTPException(status_code=404, detail="Compulsa no encontrada")

    req = db.scalar(select(Requisition).where(Requisition.id == run.requisition_id))
    if req and req.status == "LOCKED_BUDGET":
        raise LockedBudgetModificationError(
            "El presupuesto está congelado (LOCKED_BUDGET) y no admite modificaciones en sus productos."
        )

    match_rec = db.scalar(
        select(ComparisonItemMatch).where(
            ComparisonItemMatch.id == match_id,
            ComparisonItemMatch.comparison_run_id == run.id,
        )
    )
    if not match_rec:
        raise HTTPException(status_code=404, detail="Coincidencia de ítem no encontrada")

    # [SEC-02] Validar que el producto pertenezca al MISMO vendor_id y a su lista activa
    prod = db.scalar(
        select(VendorProduct)
        .join(PriceList, VendorProduct.price_list_id == PriceList.id)
        .where(
            VendorProduct.id == payload.vendor_product_id,
            VendorProduct.vendor_id == match_rec.vendor_id,
            PriceList.is_active == True,
        )
    )
    if not prod:
        raise HTTPException(
            status_code=404,
            detail="Producto alternativo no encontrado en el catálogo activo de este comercio.",
        )

    req_item = match_rec.requisition_item
    # [DOC-03] Validar compatibilidad dimensional salvo que force_dimension_override sea True
    if not payload.force_dimension_override:
        if req_item.diameter_mm is not None and (
            prod.diameter_mm is None or abs(float(prod.diameter_mm) - float(req_item.diameter_mm)) > 0.5
        ):
            raise DimensionMismatchOverrideError(
                f"Diámetro incompatible: solicitado {req_item.diameter_mm} mm vs producto {prod.diameter_mm} mm."
            )
        if req_item.length_m is not None and (
            prod.length_m is None or abs(float(prod.length_m) - float(req_item.length_m)) > 0.05
        ):
            raise DimensionMismatchOverrideError(
                f"Longitud incompatible: solicitado {req_item.length_m} m vs producto {prod.length_m} m."
            )
        if req_item.weight_kg is not None and (
            prod.weight_kg is None or abs(float(prod.weight_kg) - float(req_item.weight_kg)) > 0.5
        ):
            raise DimensionMismatchOverrideError(
                f"Peso incompatible: solicitado {req_item.weight_kg} kg vs producto {prod.weight_kg} kg."
            )

    price = prod.price_cash_ars if run.payment_modality == "CASH" else prod.price_list_ars
    qty = req_item.quantity

    match_rec.vendor_product_id = prod.id
    match_rec.match_status = "EXACT_MATCH"
    match_rec.unit_price_applied_ars = price
    match_rec.line_subtotal_ars = price * qty

    # [BUG-01] Guardar alias si fue solicitado con upsert seguro
    if payload.save_vendor_alias:
        alias_term = req_item.raw_line.strip()
        existing_alias = db.scalar(
            select(ProductAlias).where(
                ProductAlias.workspace_id == current_ws.id,
                ProductAlias.vendor_id == match_rec.vendor_id,
                ProductAlias.alias_term == alias_term,
            )
        )
        if existing_alias:
            existing_alias.canonical_term = prod.raw_description
            existing_alias.target_vendor_product_id = prod.id
            existing_alias.is_active = True
        else:
            db.add(
                ProductAlias(
                    id=uuid.uuid4(),
                    workspace_id=current_ws.id,
                    vendor_id=match_rec.vendor_id,
                    alias_term=alias_term,
                    canonical_term=prod.raw_description,
                    target_vendor_product_id=prod.id,
                    is_active=True,
                )
            )

    # [BUG-01] Clonar matriz JSON, actualizar celda y recalcular totales
    matrix = copy.deepcopy(run.comparison_matrix_json)
    for row in matrix.get("matrix_rows", []):
        if row.get("requisition_item_id") == str(match_rec.requisition_item_id):
            for cell in row.get("vendor_cells", []):
                if str(cell.get("vendor_id")) == str(match_rec.vendor_id):
                    cell["match_id"] = str(match_rec.id)
                    cell["vendor_product_id"] = str(prod.id)
                    cell["match_status"] = "EXACT_MATCH"
                    cell["product_sku"] = prod.sku
                    cell["product_description"] = prod.raw_description
                    cell["unit_price_ars"] = float(price)
                    cell["line_subtotal_ars"] = float(price * qty)

    # Obtener vendors para recálculo
    vendors_in_run = db.scalars(
        select(Vendor).where(
            Vendor.id.in_([uuid.UUID(str(v["vendor_id"])) for v in matrix.get("vendors", [])])
        )
    ).all()

    matrix = ComparisonOptimizerService.recalculate_matrix_totals(
        matrix_dict=matrix,
        vendors=vendors_in_run,
        include_delivery_fees=matrix.get("include_delivery_fees", True),
    )

    run.comparison_matrix_json = matrix
    flag_modified(run, "comparison_matrix_json")
    db.commit()

    return ComparisonMatrixResponse(**run.comparison_matrix_json)


@router.post("/comparisons/{run_id}/lock-budget", response_model=LockBudgetResponse)
def lock_budget(
    run_id: uuid.UUID,
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Congela la comparativa como presupuesto definitivo inmutable y habilita enlaces públicos."""
    run = db.scalar(
        select(ComparisonRun).where(
            ComparisonRun.id == run_id, ComparisonRun.workspace_id == current_ws.id
        )
    )
    if not run:
        raise HTTPException(status_code=404, detail="Compulsa no encontrada")

    req = db.scalar(select(Requisition).where(Requisition.id == run.requisition_id))
    if req:
        req.status = "LOCKED_BUDGET"

    db.commit()

    return LockBudgetResponse(
        run_id=run.id,
        public_share_token=run.public_share_token,
        share_url=f"/p/{run.public_share_token}",
        pdf_url=f"/api/v1/comparisons/{run.id}/pdf",
        status="LOCKED_BUDGET",
    )


@router.get("/comparisons/{run_id}/pdf")
def download_comparison_pdf(
    run_id: uuid.UUID,
    mode: str = Query(default="comparison", pattern="^(comparison|client_budget)$"),
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Genera y descarga el PDF vectorial membretado (en modo Comparativa u Oferta al Cliente)."""
    run = db.scalar(
        select(ComparisonRun).where(
            ComparisonRun.id == run_id, ComparisonRun.workspace_id == current_ws.id
        )
    )
    if not run:
        raise HTTPException(status_code=404, detail="Compulsa no encontrada")

    req = db.scalar(select(Requisition).where(Requisition.id == run.requisition_id))
    title = req.title if req else "Presupuesto de Materiales"
    client_name = req.client_name if req else None

    pdf_bytes = PDFGeneratorService.generate_pdf(
        matrix_data=run.comparison_matrix_json,
        mode=mode,
        title=title,
        client_name=client_name,
    )

    filename = f"compulsa_{str(run.id)[:8]}_{mode}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )
