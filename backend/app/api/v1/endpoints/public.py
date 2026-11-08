"""Endpoints públicos con token HMAC y métricas auditables de /traccion (E2E-05)."""

import copy
import uuid
import statistics
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_hmac_share_token
from app.models.workspace import Workspace
from app.models.vendor import Vendor
from app.models.requisition import Requisition, RequisitionItem
from app.models.comparison import ComparisonRun, ComparisonItemMatch
from app.schemas.comparison import ComparisonMatrixResponse, TractionMetricsResponse
from app.services.pdf_generator import PDFGeneratorService

router = APIRouter(prefix="/public", tags=["Público y Tracción"])


@router.get("/comparisons/{share_token}")
def get_public_budget_view(
    share_token: str,
    format: Optional[str] = Query(default="json", pattern="^(json|pdf)$"),
    mode: str = Query(default="comparison", pattern="^(comparison|client_budget)$"),
    db: Session = Depends(get_db),
):
    """Acceso público a presupuestos y comparativas emitidas mediante token firmado HMAC-SHA256."""
    run = db.scalar(
        select(ComparisonRun).where(ComparisonRun.public_share_token == share_token)
    )
    if not run:
        raise HTTPException(status_code=404, detail="Presupuesto o comparativa no encontrada")

    # Invariante DOC-01: Verificación de firma criptográfica HMAC-SHA256
    if not verify_hmac_share_token(share_token, str(run.requisition_id)):
        raise HTTPException(status_code=404, detail="Firma criptográfica del token inválida o adulterada.")

    # Invariante CO-05: El enlace público solo debe exponer presupuestos emitidos y congelados
    req = db.scalar(select(Requisition).where(Requisition.id == run.requisition_id))
    matrix_status = run.comparison_matrix_json.get("status") if isinstance(run.comparison_matrix_json, dict) else None
    if not req or req.status != "LOCKED_BUDGET" or matrix_status != "LOCKED_BUDGET":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El presupuesto aún no ha sido emitido y congelado (LOCKED_BUDGET) para acceso público.",
        )

    title = req.title if req else "Presupuesto de Materiales"
    client_name = req.client_name if req else None

    if format == "pdf":
        pdf_bytes = PDFGeneratorService.generate_pdf(
            matrix_data=run.comparison_matrix_json,
            mode=mode,
            title=title,
            client_name=client_name,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename=presupuesto_{share_token[:8]}.pdf"},
        )

    # Si es modo presupuesto al cliente final, sanitizar matriz para no exponer costos ni markup_pct
    matrix_data = copy.deepcopy(run.comparison_matrix_json)
    if mode == "client_budget":
        markup_pct = float(matrix_data.get("markup_pct", 0.0))
        markup_mult = 1.0 + (markup_pct / 100.0)

        for row in matrix_data.get("matrix_rows", []):
            low_p = row.get("lowest_price_ars")
            if low_p is not None:
                row["lowest_price_ars"] = round(low_p * markup_mult, 2)
            row["winning_vendor_id"] = None
            row["vendor_cells"] = []

        matrix_data["vendors"] = []
        matrix_data["best_single_vendor_name"] = None
        matrix_data["best_single_vendor_id"] = None
        matrix_data["markup_pct"] = 0.0

    return ComparisonMatrixResponse(**matrix_data)


@router.get("/traction", response_model=TractionMetricsResponse)
def get_traction_metrics(db: Session = Depends(get_db)):
    """Tablero público auditable (/traccion): contabiliza EXCLUSIVAMENTE cuentas reales (is_demo = FALSE)."""
    # 1. Espacios de trabajo reales
    real_workspaces_count = db.scalar(
        select(func.count(Workspace.id)).where(Workspace.is_demo == False)
    ) or 0

    # 2. Presupuestos y comparativas reales generadas
    real_runs_count = db.scalar(
        select(func.count(ComparisonRun.id))
        .join(Workspace, ComparisonRun.workspace_id == Workspace.id)
        .where(Workspace.is_demo == False)
    ) or 0

    # 3. Comercios reales comparados (excluyendo directorio público / demo)
    real_vendors_count = db.scalar(
        select(func.count(distinct(ComparisonItemMatch.vendor_id)))
        .join(ComparisonRun, ComparisonItemMatch.comparison_run_id == ComparisonRun.id)
        .join(Workspace, ComparisonRun.workspace_id == Workspace.id)
        .join(Vendor, ComparisonItemMatch.vendor_id == Vendor.id)
        .where(Workspace.is_demo == False, Vendor.is_public_directory == False)
    ) or 0

    # 4. Total de líneas procesadas en cuentas reales
    total_lines = db.scalar(
        select(func.count(RequisitionItem.id))
        .join(Requisition, RequisitionItem.requisition_id == Requisition.id)
        .join(Workspace, Requisition.workspace_id == Workspace.id)
        .where(Workspace.is_demo == False)
    ) or 0

    # 5. Mediana real auditada de tiempo de elaboración (segundos) - Cierre de DOC-02
    runs = db.scalars(
        select(ComparisonRun)
        .join(Workspace, ComparisonRun.workspace_id == Workspace.id)
        .where(Workspace.is_demo == False)
    ).all()

    durations = []
    for r in runs:
        if r.requisition and r.requisition.created_at and r.created_at:
            diff = (r.created_at - r.requisition.created_at).total_seconds()
            if diff >= 0:
                durations.append(diff)

    median_seconds = round(float(statistics.median(durations)), 1) if durations else 0.0

    return TractionMetricsResponse(
        active_real_workspaces=real_workspaces_count,
        real_vendors_compared=real_vendors_count,
        real_budgets_generated=real_runs_count,
        total_lines_processed=total_lines,
        median_elaboration_seconds=median_seconds,
    )

