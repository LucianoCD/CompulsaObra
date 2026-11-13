"""Endpoints públicos con token HMAC ligado al snapshot completo y métricas auditables de /traccion."""

from datetime import datetime, timezone
import statistics
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
import sqlalchemy as sa
from sqlalchemy import distinct, exists, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_hmac_share_token
from app.models.comparison import ComparisonItemMatch, ComparisonRun
from app.models.requisition import Requisition, RequisitionItem
from app.models.telemetry import TractionEvent
from app.models.vendor import Vendor
from app.models.workspace import User, Workspace
from app.schemas.comparison import (
    PublicClientBudgetItemRow,
    PublicClientBudgetResponse,
    TractionMetricsResponse,
)
from app.services.comparison_optimizer import ComparisonOptimizerService
from app.services.pdf_generator import PDFGeneratorService
from app.services.traction_service import record_traction_event

router = APIRouter(prefix="/public", tags=["Público y Tracción"])

_OPERATIONAL_TRACTION_EVENTS = (
    "USER_EMAIL_VERIFIED",
    "VENDOR_CATALOG_IMPORTED",
    "REQUISITION_CREATED",
    "ITEM_DISAMBIGUATED",
    "COMPARISON_EXECUTED",
    "MANUAL_OVERRIDE_APPLIED",
    "BUDGET_LOCKED",
    "PDF_EXPORTED",
    "PUBLIC_SHARE_VIEWED",
)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.get("/comparisons/{share_token}", response_model=PublicClientBudgetResponse)
def get_public_budget_view(
    share_token: str,
    format: Optional[str] = Query(default="json", pattern="^(json|pdf)$"),
    mode: str = Query(default="client_budget", pattern="^(comparison|client_budget)$"),
    strategy: Optional[Literal["SPLIT_CART", "SINGLE_VENDOR"]] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Acceso público a presupuestos emitidos verificando integridad HMAC completa e inmutabilidad (H-02, H-03, H-04, H-31, H-32)."""
    if strategy is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se permite alterar la estrategia de un presupuesto público emitido.",
        )
    if mode != "client_budget":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El enlace público solo habilita la vista sanitizada de presupuesto al cliente (client_budget).",
        )

    run = db.scalar(
        select(ComparisonRun).where(ComparisonRun.public_share_token == share_token)
    )
    if not run:
        raise HTTPException(status_code=404, detail="Presupuesto o comparativa no encontrada")

    req = db.scalar(select(Requisition).where(Requisition.id == run.requisition_id))
    matrix_json = run.comparison_matrix_json if isinstance(run.comparison_matrix_json, dict) else {}
    matrix_status = matrix_json.get("status")

    # Exigir presupuesto emitido y congelado tanto en columna relacional como en requisición y snapshot (CO-05 / H-31)
    if (
        not run.is_locked
        or not req
        or req.status != "LOCKED_BUDGET"
        or matrix_status != "LOCKED_BUDGET"
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El presupuesto aún no ha sido emitido y congelado (LOCKED_BUDGET) para acceso público.",
        )

    # H-04 / H-32: Verificar integridad completa (firma HMAC + snapshot_content_hash + locked_snapshot_hash)
    if not verify_hmac_share_token(
        share_token,
        str(run.requisition_id),
        matrix_json,
        expected_snapshot_hash=run.locked_snapshot_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firma criptográfica del presupuesto inválida o contenido alterado tras su emisión.",
        )

    # Validar coherencia entre columnas bloqueadas y el snapshot firmado
    if run.locked_strategy and matrix_json.get("budget_strategy") != run.locked_strategy:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inconsistencia detectada entre la estrategia congelada y el snapshot firmado.",
        )
    expected_vid = str(run.locked_single_vendor_id) if run.locked_single_vendor_id else None
    snapshot_vid = (
        str(matrix_json["selected_single_vendor_id"])
        if matrix_json.get("selected_single_vendor_id")
        else None
    )
    if expected_vid != snapshot_vid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inconsistencia detectada en el proveedor bloqueado del snapshot.",
        )

    # H-32: Leer metadatos públicos únicamente desde el snapshot firmado e inmutable
    title = str(matrix_json.get("title") or "Presupuesto de Materiales")
    client_name = matrix_json.get("client_name")
    frozen = matrix_json.get("frozen_budget_snapshot")
    if isinstance(frozen, dict):
        resolved = frozen
    else:
        resolved = ComparisonOptimizerService.resolve_budget_lines_for_strategy(
            matrix_data=matrix_json,
        )

    ws_is_demo = db.scalar(select(Workspace.is_demo).where(Workspace.id == run.workspace_id))
    record_traction_event(
        db,
        event_type="PUBLIC_SHARE_VIEWED",
        workspace_id=run.workspace_id,
        comparison_run_id=run.id,
        requisition_id=run.requisition_id,
        is_demo=bool(ws_is_demo) if ws_is_demo is not None else True,
        metadata={"format": format or "json"},
    )
    db.commit()

    if format == "pdf":
        pdf_bytes = PDFGeneratorService.generate_pdf(
            matrix_data=matrix_json,
            mode="client_budget",
            title=title,
            client_name=client_name,
            is_simulation=False,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename=presupuesto_{share_token[:8]}.pdf"},
        )

    fulfillment_status = matrix_json.get("fulfillment_status") or "complete"
    return PublicClientBudgetResponse(
        run_id=run.id,
        requisition_id=run.requisition_id,
        title=title,
        client_name=client_name,
        status="LOCKED_BUDGET",
        fulfillment_status=fulfillment_status,
        budget_strategy=resolved["strategy"],
        payment_modality=matrix_json.get("payment_modality", "CASH"),
        items=[PublicClientBudgetItemRow(**line) for line in resolved["lines"]],
        materials_subtotal_ars=resolved["materials_subtotal_ars"],
        logistics_ars=resolved["logistics_ars"],
        grand_total_ars=resolved["grand_total_ars"],
        created_at=run.created_at,
        locked_at=run.locked_at or matrix_json.get("locked_at"),
        is_simulation=False,
        signature_verified=True,
    )


@router.get("/traction", response_model=TractionMetricsResponse)
def get_traction_metrics(db: Session = Depends(get_db)):
    """Tablero público auditable (/traccion): contabiliza únicamente cuentas verificadas, actividad real y runs congelados (H-23, H-30)."""
    verified_user_exists = exists(
        select(User.id).where(
            User.workspace_id == Workspace.id,
            User.email_verified.is_(True),
        )
    )
    workspace_has_activity = sa.or_(
        exists(select(Requisition.id).where(Requisition.workspace_id == Workspace.id)),
        exists(
            select(ComparisonRun.id).where(
                ComparisonRun.workspace_id == Workspace.id,
                ComparisonRun.is_locked.is_(True),
            )
        ),
    )

    # 1. Espacios de trabajo reales verificados Y con actividad operativa real
    active_real_workspaces = (
        db.scalar(
            select(func.count(Workspace.id)).where(
                Workspace.is_demo.is_(False),
                verified_user_exists,
                workspace_has_activity,
            )
        )
        or 0
    )

    # 2. Usuarios verificados con actividad real en su espacio no-demo
    active_real_users = (
        db.scalar(
            select(func.count(distinct(User.id)))
            .join(Workspace, User.workspace_id == Workspace.id)
            .where(
                Workspace.is_demo.is_(False),
                User.email_verified.is_(True),
                workspace_has_activity,
            )
        )
        or 0
    )

    # 3. Presupuestos reales efectivamente emitidos y congelados (ComparisonRun.is_locked = TRUE)
    real_locked_runs_count = (
        db.scalar(
            select(func.count(ComparisonRun.id))
            .join(Workspace, ComparisonRun.workspace_id == Workspace.id)
            .join(Requisition, ComparisonRun.requisition_id == Requisition.id)
            .where(
                Workspace.is_demo.is_(False),
                verified_user_exists,
                ComparisonRun.is_locked.is_(True),
                Requisition.status == "LOCKED_BUDGET",
            )
        )
        or 0
    )

    # 4. Comercios reales efectivamente incluidos en corridas congeladas emitidas
    real_vendors_count = (
        db.scalar(
            select(func.count(distinct(ComparisonItemMatch.vendor_id)))
            .join(ComparisonRun, ComparisonItemMatch.comparison_run_id == ComparisonRun.id)
            .join(Requisition, ComparisonRun.requisition_id == Requisition.id)
            .join(Workspace, ComparisonRun.workspace_id == Workspace.id)
            .join(Vendor, ComparisonItemMatch.vendor_id == Vendor.id)
            .where(
                Workspace.is_demo.is_(False),
                verified_user_exists,
                ComparisonRun.is_locked.is_(True),
                Requisition.status == "LOCKED_BUDGET",
                Vendor.is_public_directory.is_(False),
            )
        )
        or 0
    )

    # 5. Líneas procesadas exclusivamente en cuentas verificadas no-demo
    total_lines = (
        db.scalar(
            select(func.count(RequisitionItem.id))
            .join(Requisition, RequisitionItem.requisition_id == Requisition.id)
            .join(Workspace, Requisition.workspace_id == Workspace.id)
            .where(
                Workspace.is_demo.is_(False),
                verified_user_exists,
            )
        )
        or 0
    )

    # 6. Eventos auditables reales persistidos en traction_events (sin fórmula sintética)
    verified_usage_events = (
        db.scalar(
            select(func.count(TractionEvent.id))
            .join(Workspace, TractionEvent.workspace_id == Workspace.id)
            .where(
                Workspace.is_demo.is_(False),
                verified_user_exists,
                TractionEvent.event_type.in_(_OPERATIONAL_TRACTION_EVENTS),
            )
        )
        or 0
    )

    # 7. Mediana real de tiempo de elaboración desde creación de requisición hasta emisión (locked_at)
    locked_runs = db.scalars(
        select(ComparisonRun)
        .join(Workspace, ComparisonRun.workspace_id == Workspace.id)
        .join(Requisition, ComparisonRun.requisition_id == Requisition.id)
        .where(
            Workspace.is_demo.is_(False),
            verified_user_exists,
            ComparisonRun.is_locked.is_(True),
            Requisition.status == "LOCKED_BUDGET",
        )
    ).all()

    durations = []
    for r in locked_runs:
        end_dt = _as_utc(r.locked_at)
        start_dt = _as_utc(r.requisition.created_at) if r.requisition else None
        if end_dt and start_dt:
            diff = (end_dt - start_dt).total_seconds()
            if diff >= 0:
                durations.append(diff)

    median_seconds = round(float(statistics.median(durations)), 1) if durations else 0.0

    return TractionMetricsResponse(
        active_real_workspaces=active_real_workspaces,
        active_real_users=active_real_users,
        real_vendors_compared=real_vendors_count,
        real_budgets_generated=real_locked_runs_count,
        verified_usage_events=verified_usage_events,
        total_lines_processed=total_lines,
        median_elaboration_seconds=median_seconds,
    )
