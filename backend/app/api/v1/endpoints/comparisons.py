"""Endpoints para Ejecución de Compulsa, Optimización Split Cart, Congelamiento y PDF."""

import copy
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import get_current_user_optional, get_current_workspace
from app.core.database import get_db
from app.core.exceptions import DimensionMismatchOverrideError, LockedBudgetModificationError
from app.core.security import compute_matrix_snapshot_hash, generate_hmac_share_token
from app.models.comparison import ComparisonItemMatch, ComparisonRun
from app.models.requisition import Requisition
from app.models.vendor import PriceList, ProductAlias, Vendor, VendorProduct
from app.models.workspace import User, Workspace
from app.schemas.comparison import (
    ComparisonMatrixResponse,
    LockBudgetRequest,
    LockBudgetResponse,
    ManualVendorMatchOverride,
    RunComparisonRequest,
)
from app.services.comparison_optimizer import ComparisonOptimizerService
from app.services.matching_engine import MatchingEngineService
from app.services.pdf_generator import PDFGeneratorService

router = APIRouter(tags=["Compulsa y Optimización"])


@router.post("/requisitions/{req_id}/compare", response_model=ComparisonMatrixResponse)
def run_comparison(
    req_id: uuid.UUID,
    payload: RunComparisonRequest,
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Ejecuta la compulsa multi-negocio, optimización Branch-and-Bound y cálculo de acopio."""
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
        budget_strategy=payload.budget_strategy,
        selected_single_vendor_id=payload.selected_single_vendor_id,
        existing_run_id=payload.existing_run_id,
        persist=payload.persist,
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
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Sustitución manual validada (material, diámetro, longitud, peso) con justificación y auditoría (H-10)."""
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

    prod = db.scalar(
        select(VendorProduct)
        .join(PriceList, VendorProduct.price_list_id == PriceList.id)
        .where(
            VendorProduct.id == payload.vendor_product_id,
            VendorProduct.vendor_id == match_rec.vendor_id,
            PriceList.is_active.is_(True),
        )
    )
    if not prod:
        raise HTTPException(
            status_code=404,
            detail="Producto alternativo no encontrado en el catálogo activo de este comercio.",
        )

    req_item = match_rec.requisition_item
    discrepancies = ComparisonOptimizerService.detect_technical_discrepancies(req_item, prod)

    if discrepancies and not payload.force_dimension_override:
        raise DimensionMismatchOverrideError(" | ".join(discrepancies))

    reason_text = (payload.override_reason or "").strip()
    if discrepancies and payload.force_dimension_override and not reason_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Toda excepción técnica sobre material o dimensiones requiere una justificación "
                f"explícita (override_reason). Discrepancias detectadas: {' | '.join(discrepancies)}"
            ),
        )

    vendor = db.scalar(select(Vendor).where(Vendor.id == match_rec.vendor_id))
    price = MatchingEngineService.resolve_effective_unit_price(prod, vendor, run.payment_modality)
    comm_qty, sale_unit_used, conv_note, _ = MatchingEngineService.calculate_commercial_quantity(
        req_item, prod
    )
    line_sub_dec = (price * comm_qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    match_rec.vendor_product_id = prod.id
    match_rec.match_status = "EXACT_MATCH"
    match_rec.unit_price_applied_ars = price
    match_rec.line_subtotal_ars = line_sub_dec

    # H-11: Aprendizaje completo de alias para raw_line y requested_term con target_vendor_product_id
    if payload.save_vendor_alias:
        terms_to_save = {req_item.raw_line.strip(), req_item.requested_term.strip()}
        for alias_term in terms_to_save:
            if not alias_term:
                continue
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

    audit_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": str(current_user.id) if current_user else None,
        "user_email": current_user.email if current_user else f"workspace:{current_ws.id}",
        "requisition_item_id": str(req_item.id),
        "vendor_id": str(match_rec.vendor_id),
        "new_vendor_product_id": str(prod.id),
        "discrepancies": discrepancies,
        "forced_exception": bool(discrepancies and payload.force_dimension_override),
        "reason": reason_text or "Sustitución manual dentro de tolerancia técnica",
    }

    matrix = copy.deepcopy(run.comparison_matrix_json)
    audit_log = matrix.get("override_audit_log") or []
    audit_log.append(audit_entry)
    matrix["override_audit_log"] = audit_log

    for row in matrix.get("matrix_rows", []):
        if row.get("requisition_item_id") == str(match_rec.requisition_item_id):
            for cell in row.get("vendor_cells", []):
                if str(cell.get("vendor_id")) == str(match_rec.vendor_id):
                    cell["match_id"] = str(match_rec.id)
                    cell["vendor_product_id"] = str(prod.id)
                    cell["match_status"] = "EXACT_MATCH"
                    cell["product_sku"] = prod.sku
                    cell["product_description"] = prod.raw_description
                    cell["sale_unit"] = sale_unit_used
                    cell["commercial_qty"] = float(comm_qty)
                    cell["conversion_note"] = conv_note
                    cell["unit_price_ars"] = float(price)
                    cell["line_subtotal_ars"] = float(line_sub_dec)
                    cell["override_audit"] = audit_entry

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

    run.public_share_token = generate_hmac_share_token(str(run.id), str(run.requisition_id), matrix)
    matrix["public_share_token"] = run.public_share_token
    run.comparison_matrix_json = matrix

    if matrix.get("best_single_vendor_id"):
        run.best_single_vendor_id = uuid.UUID(str(matrix["best_single_vendor_id"]))
    else:
        run.best_single_vendor_id = None

    if matrix.get("best_single_total_ars") is not None:
        run.best_single_total_ars = Decimal(str(matrix["best_single_total_ars"]))
    else:
        run.best_single_total_ars = None

    split_cart_data = matrix.get("split_cart") or {}
    if "total_cart_ars" in split_cart_data:
        run.split_cart_total_ars = Decimal(str(split_cart_data["total_cart_ars"]))
    if "savings_vs_single_vendor_ars" in split_cart_data:
        run.split_cart_savings_ars = Decimal(str(split_cart_data["savings_vs_single_vendor_ars"]))

    for row in matrix.get("matrix_rows", []):
        r_item_id = uuid.UUID(str(row["requisition_item_id"]))
        for cell in row.get("vendor_cells", []):
            c_vendor_id = uuid.UUID(str(cell["vendor_id"]))
            is_split = bool(cell.get("is_selected_split", False))
            db.execute(
                update(ComparisonItemMatch)
                .where(
                    ComparisonItemMatch.comparison_run_id == run.id,
                    ComparisonItemMatch.requisition_item_id == r_item_id,
                    ComparisonItemMatch.vendor_id == c_vendor_id,
                )
                .values(is_selected_for_split_cart=is_split)
            )

    flag_modified(run, "comparison_matrix_json")
    db.commit()

    return ComparisonMatrixResponse(**run.comparison_matrix_json)


@router.post("/comparisons/{run_id}/lock-budget", response_model=LockBudgetResponse)
def lock_budget(
    run_id: uuid.UUID,
    payload: Optional[LockBudgetRequest] = Body(default=None),
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Congela la comparativa validando completitud (H-08) y sellando HMAC de snapshot (H-04)."""
    run = db.scalar(
        select(ComparisonRun).where(
            ComparisonRun.id == run_id, ComparisonRun.workspace_id == current_ws.id
        )
    )
    if not run:
        raise HTTPException(status_code=404, detail="Compulsa no encontrada")

    req = db.scalar(select(Requisition).where(Requisition.id == run.requisition_id))
    if req and req.status == "LOCKED_BUDGET" and run.comparison_matrix_json.get("status") != "LOCKED_BUDGET":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta requisición ya cuenta con un presupuesto congelado definitivo.",
        )

    matrix = copy.deepcopy(run.comparison_matrix_json)
    fulfillment_status, unresolved_count, ambiguous_count = (
        ComparisonOptimizerService.compute_fulfillment_status(matrix.get("matrix_rows", []))
    )

    if fulfillment_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No se puede emitir el presupuesto: existen {ambiguous_count} renglones ambiguos "
                "pendientes de confirmación o ningún material cotizado."
            ),
        )

    accept_partial = bool(payload.accept_partial) if payload else False
    if fulfillment_status == "partial" and not accept_partial:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Presupuesto parcial: {unresolved_count} material(es) quedaron sin cotizar. "
                "Confirme explícitamente accept_partial=True para emitir un presupuesto parcial."
            ),
        )

    strategy = (payload.strategy if payload else matrix.get("budget_strategy")) or "SPLIT_CART"
    single_vid = (
        str(payload.selected_single_vendor_id)
        if payload and payload.selected_single_vendor_id
        else matrix.get("selected_single_vendor_id")
    )

    if req:
        req.status = "LOCKED_BUDGET"

    matrix["status"] = "LOCKED_BUDGET"
    matrix["fulfillment_status"] = fulfillment_status
    matrix["unresolved_items_count"] = unresolved_count
    matrix["ambiguous_items_count"] = ambiguous_count
    matrix["budget_strategy"] = strategy
    if single_vid:
        matrix["selected_single_vendor_id"] = single_vid
    matrix["locked_at"] = datetime.now(timezone.utc).isoformat()

    # H-04: Sellar hash criptográfico del contenido del snapshot en la firma HMAC
    snapshot_hash = compute_matrix_snapshot_hash(matrix)
    matrix["snapshot_content_hash"] = snapshot_hash
    run.public_share_token = generate_hmac_share_token(str(run.id), str(run.requisition_id), matrix)
    matrix["public_share_token"] = run.public_share_token

    run.comparison_matrix_json = matrix
    flag_modified(run, "comparison_matrix_json")
    db.commit()

    return LockBudgetResponse(
        run_id=run.id,
        public_share_token=run.public_share_token,
        share_url=f"/p/{run.public_share_token}",
        pdf_url=f"/api/v1/comparisons/{run.id}/pdf",
        status="LOCKED_BUDGET",
        fulfillment_status=fulfillment_status,  # type: ignore[arg-type]
        budget_strategy=strategy,  # type: ignore[arg-type]
        snapshot_content_hash=snapshot_hash,
    )


@router.get("/comparisons/{run_id}/pdf")
def download_comparison_pdf(
    run_id: uuid.UUID,
    mode: str = Query(default="comparison", pattern="^(comparison|client_budget)$"),
    strategy: Optional[Literal["SPLIT_CART", "SINGLE_VENDOR"]] = Query(default=None),
    single_vendor_id: Optional[str] = Query(default=None),
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
        strategy=strategy,
        single_vendor_id=single_vendor_id,
    )

    filename = f"compulsa_{str(run.id)[:8]}_{mode}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )
