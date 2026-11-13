"""Endpoints públicos con token HMAC ligado al snapshot y métricas auditables de /traccion."""

import statistics
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_hmac_share_token
from app.models.comparison import ComparisonItemMatch, ComparisonRun
from app.models.requisition import Requisition, RequisitionItem
from app.models.vendor import Vendor
from app.models.workspace import User, Workspace
from app.schemas.comparison import (
    PublicClientBudgetItemRow,
    PublicClientBudgetResponse,
    TractionMetricsResponse,
)
from app.services.comparison_optimizer import ComparisonOptimizerService
from app.services.pdf_generator import PDFGeneratorService

router = APIRouter(prefix="/public", tags=["Público y Tracción"])


@router.get("/comparisons/{share_token}", response_model=PublicClientBudgetResponse)
def get_public_budget_view(
    share_token: str,
    format: Optional[str] = Query(default="json", pattern="^(json|pdf)$"),
    mode: str = Query(default="client_budget", pattern="^(comparison|client_budget)$"),
    strategy: Optional[Literal["SPLIT_CART", "SINGLE_VENDOR"]] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Acceso público a presupuestos emitidos verificando firma HMAC de contenido y DTO de lista blanca (H-03 / H-04)."""
    run = db.scalar(
        select(ComparisonRun).where(ComparisonRun.public_share_token == share_token)
    )
    if not run:
        raise HTTPException(status_code=404, detail="Presupuesto o comparativa no encontrada")

    req = db.scalar(select(Requisition).where(Requisition.id == run.requisition_id))
    matrix_json = run.comparison_matrix_json if isinstance(run.comparison_matrix_json, dict) else {}
    matrix_status = matrix_json.get("status")

    # Exigir presupuesto congelado antes de liberar acceso público (CO-05)
    if not req or req.status != "LOCKED_BUDGET" or matrix_status != "LOCKED_BUDGET":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El presupuesto aún no ha sido emitido y congelado (LOCKED_BUDGET) para acceso público.",
        )

    # H-04: Verificar integridad del contenido del snapshot mediante HMAC-SHA256
    if not verify_hmac_share_token(share_token, str(run.requisition_id), matrix_json):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firma criptográfica del presupuesto inválida o contenido alterado tras su emisión.",
        )

    title = req.title if req else "Presupuesto de Materiales"
    client_name = req.client_name if req else None

    if format == "pdf":
        # En endpoint público, el PDF siempre se emite en modo cliente sanitizado para no filtrar proveedores internos
        pdf_bytes = PDFGeneratorService.generate_pdf(
            matrix_data=matrix_json,
            mode="client_budget",
            title=title,
            client_name=client_name,
            strategy=strategy,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename=presupuesto_{share_token[:8]}.pdf"},
        )

    # H-03: Construir DTO público estricto mediante lista blanca (nunca expone vendors, vendor_cells, split_cart ni markup_pct)
    resolved = ComparisonOptimizerService.resolve_budget_lines_for_strategy(
        matrix_data=matrix_json,
        strategy=strategy,
    )
    fulfillment_status = matrix_json.get("fulfillment_status") or "complete"

    return PublicClientBudgetResponse(
        run_id=run.id,
        requisition_id=run.requisition_id,
        title=title,
        client_name=client_name,
        status=matrix_status or "LOCKED_BUDGET",
        fulfillment_status=fulfillment_status,
        budget_strategy=resolved["strategy"],
        payment_modality=matrix_json.get("payment_modality", "CASH"),
        items=[PublicClientBudgetItemRow(**line) for line in resolved["lines"]],
        materials_subtotal_ars=resolved["materials_subtotal_ars"],
        logistics_ars=resolved["logistics_ars"],
        grand_total_ars=resolved["grand_total_ars"],
        created_at=run.created_at,
        locked_at=matrix_json.get("locked_at"),
        signature_verified=True,
    )


@router.get("/traction", response_model=TractionMetricsResponse)
def get_traction_metrics(db: Session = Depends(get_db)):
    """Tablero público auditable (/traccion): contabiliza EXCLUSIVAMENTE presupuestos emitidos reales (H-23)."""
    # 1. Espacios de trabajo reales (is_demo = FALSE)
    real_workspaces_count = db.scalar(
        select(func.count(Workspace.id)).where(Workspace.is_demo.is_(False))
    ) or 0

    # 2. Usuarios activos reales con al menos una requisición o presupuesto emitido
    active_real_users = db.scalar(
        select(func.count(distinct(User.id)))
        .join(Workspace, User.workspace_id == Workspace.id)
        .join(Requisition, Requisition.workspace_id == Workspace.id)
        .where(Workspace.is_demo.is_(False))
    ) or 0

    # 3. Presupuestos reales efectivamente emitidos y congelados (LOCKED_BUDGET)
    real_locked_runs_count = db.scalar(
        select(func.count(ComparisonRun.id))
        .join(Workspace, ComparisonRun.workspace_id == Workspace.id)
        .join(Requisition, ComparisonRun.requisition_id == Requisition.id)
        .where(
            Workspace.is_demo.is_(False),
            Requisition.status == "LOCKED_BUDGET",
        )
    ) or 0

    # 4. Comercios reales comparados en presupuestos reales emitidos
    real_vendors_count = db.scalar(
        select(func.count(distinct(ComparisonItemMatch.vendor_id)))
        .join(ComparisonRun, ComparisonItemMatch.comparison_run_id == ComparisonRun.id)
        .join(Requisition, ComparisonRun.requisition_id == Requisition.id)
        .join(Workspace, ComparisonRun.workspace_id == Workspace.id)
        .join(Vendor, ComparisonItemMatch.vendor_id == Vendor.id)
        .where(
            Workspace.is_demo.is_(False),
            Requisition.status == "LOCKED_BUDGET",
            Vendor.is_public_directory.is_(False),
        )
    ) or 0

    # 5. Total de líneas procesadas en cuentas reales
    total_lines = db.scalar(
        select(func.count(RequisitionItem.id))
        .join(Requisition, RequisitionItem.requisition_id == Requisition.id)
        .join(Workspace, Requisition.workspace_id == Workspace.id)
        .where(Workspace.is_demo.is_(False))
    ) or 0

    # 6. Eventos de uso verificables (requisiciones reales + presupuestos reales congelados)
    real_reqs_count = db.scalar(
        select(func.count(Requisition.id))
        .join(Workspace, Requisition.workspace_id == Workspace.id)
        .where(Workspace.is_demo.is_(False))
    ) or 0
    verified_usage_events = real_reqs_count + real_locked_runs_count

    # 7. Mediana real de tiempo de elaboración hasta emisión
    locked_runs = db.scalars(
        select(ComparisonRun)
        .join(Workspace, ComparisonRun.workspace_id == Workspace.id)
        .join(Requisition, ComparisonRun.requisition_id == Requisition.id)
        .where(
            Workspace.is_demo.is_(False),
            Requisition.status == "LOCKED_BUDGET",
        )
    ).all()

    durations = []
    for r in locked_runs:
        if r.requisition and r.requisition.created_at and r.created_at:
            diff = (r.created_at - r.requisition.created_at).total_seconds()
            if diff >= 0:
                durations.append(diff)

    median_seconds = round(float(statistics.median(durations)), 1) if durations else 0.0

    return TractionMetricsResponse(
        active_real_workspaces=real_workspaces_count,
        active_real_users=active_real_users,
        real_vendors_compared=real_vendors_count,
        real_budgets_generated=real_locked_runs_count,
        verified_usage_events=verified_usage_events,
        total_lines_processed=total_lines,
        median_elaboration_seconds=median_seconds,
    )
