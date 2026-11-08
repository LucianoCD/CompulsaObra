"""Pruebas de endpoints REST y aislamiento estricto en /traccion (E2E-05)."""

import uuid
from decimal import Decimal
from sqlalchemy import select
from app.models.workspace import Workspace
from app.models.vendor import Vendor, PriceList, VendorProduct
from app.models.requisition import Requisition, RequisitionItem
from app.models.comparison import ComparisonRun, ComparisonItemMatch


def test_e2e_05_isolation_of_traction_metrics(client, db):
    """E2E-05: Aislamiento de Métricas Reales en /traccion.
    - 10 comparativas en modo Demo (is_demo = TRUE)
    - 2 comparativas en un workspace Real (is_demo = FALSE)
    - GET /api/v1/public/traction DEBE contabilizar exactamente 2 presupuestos reales.
    """
    # 1. Crear workspace Demo con 10 comparativas
    demo_ws = db.scalar(select(Workspace).where(Workspace.is_demo == True))
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
            public_share_token=f"demo_token_{i}_{uuid.uuid4().hex[:6]}",
            comparison_matrix_json={"demo": True},
        )
        db.add(run_demo)

    # 2. Crear workspace Real con 2 comparativas
    real_ws = Workspace(
        id=uuid.uuid4(),
        name="Constructora Jujuy SRL - Real",
        owner_role="ESTIMATOR",
        is_demo=False,
    )
    db.add(real_ws)
    db.flush()

    req_real = Requisition(
        id=uuid.uuid4(),
        workspace_id=real_ws.id,
        title="Edificio Belgrano - Real",
        status="LOCKED_BUDGET",
    )
    db.add(req_real)
    db.flush()

    for i in range(2):
        run_real = ComparisonRun(
            id=uuid.uuid4(),
            requisition_id=req_real.id,
            workspace_id=real_ws.id,
            payment_modality="CASH",
            public_share_token=f"real_token_{i}_{uuid.uuid4().hex[:6]}",
            comparison_matrix_json={"real": True},
        )
        db.add(run_real)

    db.commit()

    # 3. Consultar /api/v1/public/traction
    response = client.get("/api/v1/public/traction")
    assert response.status_code == 200
    data = response.json()

    assert data["real_budgets_generated"] == 2
    assert data["active_real_workspaces"] == 1


def test_lock_budget_and_pdf_generation(client, db):
    """Verifica congelamiento de presupuesto (lock-budget) y descarga de PDF vectorial."""
    demo_ws = db.scalar(select(Workspace).where(Workspace.is_demo == True))
    vendors = db.scalars(select(Vendor).where(Vendor.workspace_id == demo_ws.id)).all()
    vendor_ids = [str(v.id) for v in vendors[:2]]

    # 1. Ingestar pedido sin ambigüedades
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

    # 2. Ejecutar compulsa
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

    # 3. Congelar presupuesto (lock-budget)
    lock_res = client.post(f"/api/v1/comparisons/{run_id}/lock-budget")
    assert lock_res.status_code == 200
    lock_data = lock_res.json()
    assert lock_data["status"] == "LOCKED_BUDGET"
    token = lock_data["public_share_token"]

    # 4. Descargar PDF modo comparativa
    pdf_res = client.get(f"/api/v1/comparisons/{run_id}/pdf?mode=comparison")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF-")

    # 5. Descargar PDF modo presupuesto cliente con margen
    pdf_client_res = client.get(f"/api/v1/comparisons/{run_id}/pdf?mode=client_budget")
    assert pdf_client_res.status_code == 200
    assert pdf_client_res.headers["content-type"] == "application/pdf"
    assert pdf_client_res.content.startswith(b"%PDF-")

    # 6. Consultar vista pública mediante token firmado
    pub_res = client.get(f"/api/v1/public/comparisons/{token}")
    assert pub_res.status_code == 200
    assert pub_res.json()["run_id"] == run_id
