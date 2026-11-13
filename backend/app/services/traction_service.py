"""Registro de eventos auditables de tracción real en espacios no-demo (H-23, H-30)."""

from typing import Any, Dict, Optional
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.telemetry import TractionEvent
from app.models.workspace import Workspace


def record_traction_event(
    db: Session,
    *,
    event_type: str,
    workspace_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    comparison_run_id: Optional[uuid.UUID] = None,
    requisition_id: Optional[uuid.UUID] = None,
    is_demo: Optional[bool] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[TractionEvent]:
    """Registra un evento verificable de uso real omitiendo estrictamente el espacio Demo."""
    if is_demo is True:
        return None
    if is_demo is None and workspace_id is not None:
        ws_is_demo = db.execute(
            sa.select(Workspace.is_demo).where(Workspace.id == workspace_id)
        ).scalar_one_or_none()
        if ws_is_demo is None or ws_is_demo is True:
            return None

    event = TractionEvent(
        event_type=event_type,
        workspace_id=workspace_id,
        user_id=user_id,
        comparison_run_id=comparison_run_id,
        requisition_id=requisition_id,
        metadata_json=metadata or {},
    )
    db.add(event)
    return event
