"""Pruebas de endpoints REST y aislamiento estricto en /traccion (E2E-05 / H-30)."""

from datetime import datetime, timedelta, timezone
import uuid
from sqlalchemy import select
from app.models.workspace import User, Workspace
from app.models.vendor import Vendor
from app.models.requisition import Requisition
from app.models.comparison import ComparisonRun


def test_e2e_05_isolation_of_traction_metrics(client, db):
    """E2E-05 / H-30: Aislamiento de Métricas Reales en /traccion.
    - 10 comparativas en modo Demo (is_demo = TRUE)
    - 1 workspace Real no verificado + corrida sin bloquear -> ignorado
    - 1 workspace Real con usuario verificado y 2 corridas bloqueadas (is_locked=TRUE)
    - GET /api/v1/public/traction DEBE contabilizar exactamente 2 presupuestos reales y 1 workspace real activo.
    """
    demo_ws = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
    assert demo_ws is not None

    req_demo = Requisition(
        id=uuid.uuid4(),
        workspace_id=demo_ws.id,
        title="Obra Demo",
        status="LOCKED_BUDGET",
    )
    db.add(req_demo)
    db.flush()

    for i in range(10):
        run_demo = ComparisonRun(
            id=uuid.uuid4(),
            requisition_id=req_demo.id,
            workspace_id=demo_ws.id,
            payment_modality="CASH",
            is_locked=True,
            locked_at=datetime.now(timezone.utc),
            public_share_token=f"demo_token_{i}_{uuid.uuid4().hex[:6]}",
            comparison_matrix_json={"demo": True},
        )
        db.add(run_demo)

    # Workspace real con usuario NO verificado (no debe contar en /traccion)
    unverified_ws = Workspace(
        id=uuid.uuid4(),
        name="Workspace No Verificado",
        owner_role="ESTIMATOR",
        is_demo=False,
    )
    db.add(unverified_ws)
    db.flush()
    db.add(
        User(
            id=uuid.uuid4(),
            workspace_id=unverified_ws.id,
            email=f"unverified_{uuid.uuid4().hex[:6]}@test.com",
            full_name="No Verificado",
            password_hash="x",
            role="ESTIMATOR",
            email_verified=False,
        )
    )
    db.add(
        Requisition(
            id=uuid.uuid4(),
            workspace_id=unverified_ws.id,
            title="Requisición no verificada",
            status="READY_TO_COMPARE",
        )
    )

    # Workspace Real verificado con 2 presupuestos efectivamente bloqueados + 1 preliminar abierto
    real_ws = Workspace(
        id=uuid.uuid4(),
        name="Constructora Jujuy SRL - Real",
        owner_role="ESTIMATOR",
        is_demo=False,
    )
    db.add(real_ws)
    db.flush()
    db.add(
        User(
            id=uuid.uuid4(),
            workspace_id=real_ws.id,
            email=f"verified_{uuid.uuid4().hex[:6]}@constructora.com.ar",
            full_name="Ing. Real Verificado",
            password_hash="x",
            role="ESTIMATOR",
            email_verified=True,
        )
    )

    now = datetime.now(timezone.utc)
    req_real_1 = Requisition(
        id=uuid.uuid4(),
        workspace_id=real_ws.id,
        title="Edificio Belgrano - Real",
        status="LOCKED_BUDGET",
        created_at=now - timedelta(seconds=120),
    )
    req_real_2 = Requisition(
        id=uuid.uuid4(),
        workspace_id=real_ws.id,
        title="Edificio Lavalle - Real",
        status="LOCKED_BUDGET",
        created_at=now - timedelta(seconds=180),
    )
    db.add_all([req_real_1, req_real_2])
    db.flush()

    # 1 preliminar sin bloquear en req_real_1 (no debe contar en real_budgets_generated)
    db.add(
        ComparisonRun(
            id=uuid.uuid4(),
            requisition_id=req_real_1.id,
            workspace_id=real_ws.id,
            payment_modality="CASH",
            is_locked=False,
            public_share_token=f"prelim_{uuid.uuid4().hex[:6]}",
            comparison_matrix_json={"prelim": True},
        )
    )

    for idx, req_target in enumerate([req_real_1, req_real_2]):
        run_real = ComparisonRun(
            id=uuid.uuid4(),
            requisition_id=req_target.id,
            workspace_id=real_ws.id,
            payment_modality="CASH",
            is_locked=True,
            locked_at=now,
            locked_strategy="SPLIT_CART",
            public_share_token=f"real_token_{idx}_{uuid.uuid4().hex[:6]}",
            comparison_matrix_json={"real": True},
        )
        db.add(run_real)

    db.commit()

    response = client.get("/api/v1/public/traction")
    assert response.status_code == 200
    data = response.json()

    assert data["real_budgets_generated"] == 2
    assert data["active_real_workspaces"] == 1
    assert data["active_real_users"] == 1
    assert data["median_elaboration_seconds"] >= 120.0


def test_lock_budget_and_pdf_generation(client, db):
    """Verifica congelamiento de presupuesto (lock-budget) y descarga de PDF vectorial."""
    demo_ws = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
    vendors = db.scalars(select(Vendor).where(Vendor.workspace_id == demo_ws.id)).all()
    vendor_ids = [str(v.id) for v in vendors[:2]]

    ingest_res = client.post(
        "/api/v1/requisitions/ingest-json",
        json={
            "title": "Prueba PDF",
            "client_name": "Ing. Morales",
            "raw_text": "50 bolsas cemento y 40 barras del 8",
        },
    )
    assert ingest_res.status_code == 201
    req_data = ingest_res.json()
    assert req_data["status"] == "READY_TO_COMPARE"
    req_id = req_data["id"]

    comp_res = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={
            "vendor_ids": vendor_ids,
            "payment_modality": "CASH",
            "markup_pct": 10.0,
            "include_delivery_fees": True,
        },
    )
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    run_id = comp_data["run_id"]

    lock_res = client.post(f"/api/v1/comparisons/{run_id}/lock-budget")
    assert lock_res.status_code == 200
    lock_data = lock_res.json()
    assert lock_data["status"] == "LOCKED_BUDGET"
    token = lock_data["public_share_token"]

    pdf_res = client.get(f"/api/v1/comparisons/{run_id}/pdf?mode=comparison")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF-")

    pdf_client_res = client.get(f"/api/v1/comparisons/{run_id}/pdf?mode=client_budget")
    assert pdf_client_res.status_code == 200
    assert pdf_client_res.headers["content-type"] == "application/pdf"
    assert pdf_client_res.content.startswith(b"%PDF-")

    pub_res = client.get(f"/api/v1/public/comparisons/{token}")
    assert pub_res.status_code == 200
    assert pub_res.json()["run_id"] == run_id
