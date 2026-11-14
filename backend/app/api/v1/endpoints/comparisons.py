"""Endpoints para Ejecución de Compulsa, Optimización Split Cart, Congelamiento y PDF."""

import copy
import hmac
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Literal, Optional, Tuple
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import get_current_user_optional, get_current_workspace
from app.core.database import get_db
from app.core.exceptions import DimensionMismatchOverrideError, LockedBudgetModificationError
from app.core.security import (
    compute_matrix_snapshot_hash,
    compute_requisition_version_hash,
    generate_hmac_share_token,
)
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
from app.services.traction_service import record_traction_event

router = APIRouter(tags=["Compulsa y Optimización"])


def _check_run_staleness(
    run: ComparisonRun, req: Optional[Requisition]
) -> Tuple[bool, Optional[str]]:
    """Verifica si la compulsa quedó desactualizada respecto al requerimiento actual (H-39)."""
    matrix: Dict[str, Any] = (
        run.comparison_matrix_json if isinstance(run.comparison_matrix_json, dict) else {}
    )
    if run.is_locked or matrix.get("status") == "LOCKED_BUDGET":
        return False, None

    if not req:
        return True, "La requisición asociada no existe."

    if bool(getattr(run, "is_stale", False)) or bool(matrix.get("is_stale")) or matrix.get("status") == "STALE":
        return True, str(
            matrix.get("stale_reason")
            or "La matriz de comparación quedó desactualizada tras modificar el pedido. Ejecutá una nueva comparativa antes de bloquear."
        )

    run_ver = int(getattr(run, "requisition_version", None) or matrix.get("requisition_version") or 1)
    cur_ver = int(getattr(req, "version", 1) or 1)
    if run_ver != cur_ver:
        return (
            True,
            f"El requerimiento cambió (v{run_ver} -> v{cur_ver}). Ejecutá una nueva comparativa antes de bloquear el presupuesto.",
        )

    expected_hash = getattr(run, "requisition_version_hash", None) or matrix.get("requisition_version_hash")
    if expected_hash:
        current_hash = compute_requisition_version_hash(req)
        if not hmac.compare_digest(str(expected_hash), current_hash):
            return (
                True,
                "Las cantidades, unidades o especificaciones del pedido cambiaron desde esta comparativa. Ejecutá una nueva comparativa.",
            )

    matrix_rows = matrix.get("matrix_rows") or []
    req_items = list(getattr(req, "items", []) or [])
    if matrix_rows and req_items:
        if len(matrix_rows) != len(req_items):
            return True, "La cantidad de ítems del requerimiento cambió desde esta comparativa."
        by_id = {str(it.id): it for it in req_items}
        for row in matrix_rows:
            it = by_id.get(str(row.get("requisition_item_id")))
            if not it:
                return True, "Los ítems del requerimiento no coinciden con la comparativa."
            row_qty = float(row.get("quantity", 0) or 0)
            row_unit = str(row.get("requested_unit", "") or "").strip().upper()
            it_unit = str(it.requested_unit or "").strip().upper()
            if abs(row_qty - float(it.quantity)) > 1e-4 or row_unit != it_unit:
                return (
                    True,
                    f"Se modificó la cantidad o unidad de '{it.requested_term}'. Ejecutá una nueva comparativa antes de emitir.",
                )

    return False, None


@router.post("/requisitions/{req_id}/compare", response_model=ComparisonMatrixResponse)
def run_comparison(
    req_id: uuid.UUID,
    payload: RunComparisonRequest,
    current_ws: Workspace = Depends(get_current_workspace),
    current_user: Optional[User] = Depends(get_current_user_optional),
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
    if payload.persist:
        record_traction_event(
            db,
            event_type="COMPARISON_EXECUTED",
            workspace_id=current_ws.id,
            user_id=current_user.id if current_user else None,
            comparison_run_id=res.run_id,
            requisition_id=req.id,
            is_demo=current_ws.is_demo,
            metadata={"payment_modality": payload.payment_modality, "strategy": payload.budget_strategy},
        )
        db.commit()
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

    req = db.scalar(
        select(Requisition)
        .options(selectinload(Requisition.items))
        .where(Requisition.id == run.requisition_id)
    )
    is_stale, stale_reason = _check_run_staleness(run, req)

    data = dict(run.comparison_matrix_json or {})
    data["requisition_version"] = int(
        getattr(run, "requisition_version", None) or data.get("requisition_version") or 1
    )
    data["requisition_version_hash"] = (
        getattr(run, "requisition_version_hash", None) or data.get("requisition_version_hash")
    )
    data["is_stale"] = is_stale
    data["stale_reason"] = stale_reason
    data["is_locked"] = bool(run.is_locked or data.get("status") == "LOCKED_BUDGET")
    if is_stale and not data["is_locked"]:
        data["status"] = "STALE"
    if run.locked_at and not data.get("locked_at"):
        data["locked_at"] = run.locked_at.isoformat()
    return ComparisonMatrixResponse(**data)


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

    req = db.scalar(
        select(Requisition)
        .options(selectinload(Requisition.items))
        .where(Requisition.id == run.requisition_id)
    )
    if run.is_locked or (req and req.status == "LOCKED_BUDGET"):
        raise LockedBudgetModificationError(
            "El presupuesto está congelado (LOCKED_BUDGET) y no admite modificaciones en sus productos."
        )
    is_stale, stale_reason = _check_run_staleness(run, req)
    if is_stale:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=stale_reason or "La matriz de comparación está desactualizada. Ejecute una nueva comparación.",
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

    matrix["snapshot_content_hash"] = compute_matrix_snapshot_hash(matrix)
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

    record_traction_event(
        db,
        event_type="MANUAL_OVERRIDE_APPLIED",
        workspace_id=current_ws.id,
        user_id=current_user.id if current_user else None,
        comparison_run_id=run.id,
        requisition_id=run.requisition_id,
        is_demo=current_ws.is_demo,
        metadata={"requisition_item_id": str(req_item.id), "vendor_id": str(match_rec.vendor_id)},
    )
    flag_modified(run, "comparison_matrix_json")
    db.commit()

    return ComparisonMatrixResponse(**run.comparison_matrix_json)


@router.post("/comparisons/{run_id}/lock-budget", response_model=LockBudgetResponse)
def lock_budget(
    run_id: uuid.UUID,
    payload: Optional[LockBudgetRequest] = Body(default=None),
    current_ws: Workspace = Depends(get_current_workspace),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Congela la comparativa validando completitud, fijando estrategia inmutable y sellando HMAC completo (H-02, H-04, H-32)."""
    run = db.scalar(
        select(ComparisonRun).where(
            ComparisonRun.id == run_id, ComparisonRun.workspace_id == current_ws.id
        )
    )
    if not run:
        raise HTTPException(status_code=404, detail="Compulsa no encontrada")

    req = db.scalar(
        select(Requisition)
        .options(selectinload(Requisition.items))
        .where(Requisition.id == run.requisition_id)
    )

    if run.is_locked or run.comparison_matrix_json.get("status") == "LOCKED_BUDGET":
        locked_strategy = run.locked_strategy or run.comparison_matrix_json.get("budget_strategy") or "SPLIT_CART"
        locked_vid = str(run.locked_single_vendor_id) if run.locked_single_vendor_id else run.comparison_matrix_json.get("selected_single_vendor_id")
        if payload:
            req_vid = str(payload.selected_single_vendor_id) if payload.selected_single_vendor_id else None
            if payload.strategy != locked_strategy or (
                payload.strategy == "SINGLE_VENDOR" and req_vid and locked_vid and req_vid != str(locked_vid)
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El presupuesto definitivo ya está bloqueado y su estrategia es inmutable.",
                )
        return LockBudgetResponse(
            run_id=run.id,
            public_share_token=run.public_share_token,
            share_url=f"/p/{run.public_share_token}",
            pdf_url=f"/api/v1/comparisons/{run.id}/pdf",
            status="LOCKED_BUDGET",
            fulfillment_status=run.comparison_matrix_json.get("fulfillment_status") or "complete",
            budget_strategy=locked_strategy,
            snapshot_content_hash=run.locked_snapshot_hash or run.comparison_matrix_json.get("snapshot_content_hash", ""),
        )

    if req and req.status == "LOCKED_BUDGET":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta requisición ya cuenta con un presupuesto congelado definitivo.",
        )

    is_stale, stale_reason = _check_run_staleness(run, req)
    if is_stale:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=stale_reason
            or "La matriz de comparación está desactualizada respecto al requerimiento actual. Ejecute una nueva comparación antes de bloquear el presupuesto.",
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

    if strategy == "SINGLE_VENDOR":
        vendor_ids_in_run = {str(v.get("vendor_id")) for v in matrix.get("vendors", [])}
        single_vid = single_vid or (
            str(matrix.get("best_single_vendor_id")) if matrix.get("best_single_vendor_id") else None
        )
        if not single_vid or str(single_vid) not in vendor_ids_in_run:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe seleccionar un proveedor válido de esta compulsa para la estrategia SINGLE_VENDOR.",
            )
    else:
        single_vid = None

    frozen_resolved = ComparisonOptimizerService.resolve_budget_lines_for_strategy(
        matrix_data=matrix,
        strategy=strategy,
        single_vendor_id=single_vid,
    )

    locked_now = datetime.now(timezone.utc)
    if req:
        req.status = "LOCKED_BUDGET"

    matrix["run_id"] = str(run.id)
    matrix["requisition_id"] = str(run.requisition_id)
    matrix["title"] = req.title if req else matrix.get("title") or "Presupuesto de Materiales"
    matrix["client_name"] = req.client_name if req else matrix.get("client_name")
    matrix["status"] = "LOCKED_BUDGET"
    matrix["is_locked"] = True
    matrix["is_stale"] = False
    matrix["stale_reason"] = None
    matrix["fulfillment_status"] = fulfillment_status
    matrix["unresolved_items_count"] = unresolved_count
    matrix["ambiguous_items_count"] = ambiguous_count
    matrix["budget_strategy"] = frozen_resolved["strategy"]
    matrix["selected_single_vendor_id"] = frozen_resolved.get("selected_single_vendor_id")
    if run.created_at:
        matrix["created_at"] = run.created_at.isoformat()
    matrix["locked_at"] = locked_now.isoformat()
    matrix["frozen_budget_snapshot"] = frozen_resolved

    # H-04 / H-32: Sellar hash criptográfico sobre contenido completo + metadatos públicos en firma HMAC
    snapshot_hash = compute_matrix_snapshot_hash(matrix)
    matrix["snapshot_content_hash"] = snapshot_hash
    run.public_share_token = generate_hmac_share_token(str(run.id), str(run.requisition_id), matrix)
    matrix["public_share_token"] = run.public_share_token

    run.is_locked = True
    run.locked_at = locked_now
    run.locked_strategy = frozen_resolved["strategy"]
    run.locked_single_vendor_id = (
        uuid.UUID(str(frozen_resolved["selected_single_vendor_id"]))
        if frozen_resolved.get("selected_single_vendor_id")
        else None
    )
    run.locked_snapshot_hash = snapshot_hash
    run.comparison_matrix_json = matrix

    record_traction_event(
        db,
        event_type="BUDGET_LOCKED",
        workspace_id=current_ws.id,
        user_id=current_user.id if current_user else None,
        comparison_run_id=run.id,
        requisition_id=run.requisition_id,
        is_demo=current_ws.is_demo,
        metadata={"strategy": frozen_resolved["strategy"], "grand_total_ars": frozen_resolved["grand_total_ars"]},
    )

    flag_modified(run, "comparison_matrix_json")
    db.commit()

    return LockBudgetResponse(
        run_id=run.id,
        public_share_token=run.public_share_token,
        share_url=f"/p/{run.public_share_token}",
        pdf_url=f"/api/v1/comparisons/{run.id}/pdf",
        status="LOCKED_BUDGET",
        fulfillment_status=fulfillment_status,  # type: ignore[arg-type]
        budget_strategy=frozen_resolved["strategy"],  # type: ignore[arg-type]
        snapshot_content_hash=snapshot_hash,
    )


@router.get("/comparisons/{run_id}/pdf")
def download_comparison_pdf(
    run_id: uuid.UUID,
    mode: str = Query(default="comparison", pattern="^(comparison|client_budget)$"),
    strategy: Optional[Literal["SPLIT_CART", "SINGLE_VENDOR"]] = Query(default=None),
    single_vendor_id: Optional[str] = Query(default=None),
    current_ws: Workspace = Depends(get_current_workspace),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Genera PDF definitivo (snapshot inmutable) o borrador de simulación claramente rotulado (H-02, H-31)."""
    run = db.scalar(
        select(ComparisonRun).where(
            ComparisonRun.id == run_id, ComparisonRun.workspace_id == current_ws.id
        )
    )
    if not run:
        raise HTTPException(status_code=404, detail="Compulsa no encontrada")

    req = db.scalar(select(Requisition).where(Requisition.id == run.requisition_id))
    matrix = run.comparison_matrix_json if isinstance(run.comparison_matrix_json, dict) else {}
    is_locked = bool(run.is_locked or matrix.get("status") == "LOCKED_BUDGET")

    if is_locked:
        locked_strategy = run.locked_strategy or matrix.get("budget_strategy") or "SPLIT_CART"
        locked_vid = (
            str(run.locked_single_vendor_id)
            if run.locked_single_vendor_id
            else (str(matrix["selected_single_vendor_id"]) if matrix.get("selected_single_vendor_id") else None)
        )
        if strategy is not None and strategy != locked_strategy:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El presupuesto emitido es inmutable; no puede alterarse la estrategia en la exportación.",
            )
        if single_vendor_id is not None and single_vendor_id != (locked_vid or ""):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El presupuesto emitido es inmutable; no puede alterarse el comercio asignado.",
            )
        effective_strategy = None
        effective_vendor_id = None
        title = str(matrix.get("title") or (req.title if req else "Presupuesto de Materiales"))
        client_name = matrix.get("client_name") if "client_name" in matrix else (req.client_name if req else None)
    else:
        effective_strategy = strategy
        effective_vendor_id = single_vendor_id
        title = req.title if req else "Presupuesto de Materiales"
        client_name = req.client_name if req else None

    pdf_bytes = PDFGeneratorService.generate_pdf(
        matrix_data=matrix,
        mode=mode,
        title=title,
        client_name=client_name,
        strategy=effective_strategy,
        single_vendor_id=effective_vendor_id,
        is_simulation=not is_locked,
    )

    record_traction_event(
        db,
        event_type="PDF_EXPORTED",
        workspace_id=current_ws.id,
        user_id=current_user.id if current_user else None,
        comparison_run_id=run.id,
        requisition_id=run.requisition_id,
        is_demo=current_ws.is_demo,
        metadata={"mode": mode, "is_simulation": not is_locked},
    )
    db.commit()

    filename = f"compulsa_{str(run.id)[:8]}_{mode}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )
