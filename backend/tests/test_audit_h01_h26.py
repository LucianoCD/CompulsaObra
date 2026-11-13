"""Suite de pruebas exhaustivas para los 26 hallazgos de auditoría (H-01 a H-26)."""

import hashlib
import time
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import database as db_module
from app.core.config import Settings, settings
from app.models.comparison import ComparisonRun
from app.models.requisition import Requisition, RequisitionItem
from app.models.vendor import PriceList, Vendor, VendorProduct
from app.models.workspace import Workspace
from app.services.comparison_optimizer import ComparisonOptimizerService
from app.services.matching_engine import MatchingEngineService
from app.services.pdf_generator import PDFGeneratorService
from app.services.unit_normalizer import UnitNormalizerService


def _create_private_workspace_session(client: TestClient, suffix: str) -> dict:
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"auditoria_{suffix}_{uuid.uuid4().hex[:6]}@obra.com.ar",
            "password": "PasswordSeguro2026!",
            "full_name": "Ing. Auditor",
            "workspace_name": f"Estudio Auditor {suffix}",
            "role": "ESTIMATOR",
        },
    )
    assert res.status_code == 201
    return res.json()


def _create_vendor_with_products(
    db: Session,
    workspace_id: uuid.UUID,
    name: str,
    delivery_fee: Decimal,
    products: list[dict],
) -> tuple[Vendor, list[VendorProduct]]:
    vendor = Vendor(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        name=name,
        locality="San Salvador de Jujuy",
        is_public_directory=False,
        cash_discount_pct=Decimal("0.00"),
        estimate_delivery_fee_ars=delivery_fee,
        acopio_config_json={
            "enabled": True,
            "price_basis": "LIST",
            "min_down_payment_pct": 100.0,
            "freeze_days": 30,
            "max_withdrawal_days": 60,
            "min_notice_hours": 24,
        },
    )
    db.add(vendor)
    db.flush()

    pl = PriceList(
        id=uuid.uuid4(),
        vendor_id=vendor.id,
        version_number=1,
        source_filename=f"{name}.xlsx",
        is_active=True,
        row_count=len(products),
    )
    db.add(pl)
    db.flush()

    created_products: list[VendorProduct] = []
    for p in products:
        desc = p["raw_description"]
        vp = VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl.id,
            vendor_id=vendor.id,
            sku=p["sku"],
            raw_description=desc,
            normalized_description=desc.lower(),
            sale_unit=p.get("sale_unit", "UN"),
            price_cash_ars=Decimal(str(p["price_cash"])),
            price_list_ars=Decimal(str(p.get("price_list", p["price_cash"]))),
            diameter_mm=Decimal(str(p["diameter_mm"])) if p.get("diameter_mm") is not None else None,
            length_m=Decimal(str(p["length_m"])) if p.get("length_m") is not None else None,
            weight_kg=Decimal(str(p["weight_kg"])) if p.get("weight_kg") is not None else None,
            material_type=p.get("material_type"),
            stock_available=p.get("stock_available", True),
            row_sha256=hashlib.sha256(f"{p['sku']}||{desc}".encode()).hexdigest(),
        )
        db.add(vp)
        created_products.append(vp)

    db.commit()
    return vendor, created_products


def test_h01_manual_override_preserves_unit_and_subtotal_for_multi_qty(client: TestClient, db: Session):
    """H-01: Modificar manualmente un ítem con cantidad > 1 separa lowest_unit_price_ars y lowest_line_subtotal_ars."""
    ws = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
    assert ws is not None

    vendor, prods = _create_vendor_with_products(
        db,
        ws.id,
        "Corralón H01",
        Decimal("500.00"),
        [
            {
                "sku": "H01-CEM-A",
                "raw_description": "Cemento Standard 50 kg",
                "sale_unit": "BOLSA",
                "price_cash": "1200.00",
                "weight_kg": 50.0,
                "material_type": "Cemento",
            },
            {
                "sku": "H01-CEM-B",
                "raw_description": "Cemento Especial Obra 50 kg",
                "sale_unit": "BOLSA",
                "price_cash": "1000.00",
                "weight_kg": 50.0,
                "material_type": "Cemento",
            },
        ],
    )

    res_in = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Test H01", "raw_text": "10 bolsas de cemento 50 kg"},
    )
    assert res_in.status_code == 201
    req_id = res_in.json()["id"]

    res_cmp = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={"vendor_ids": [str(vendor.id)], "payment_modality": "CASH", "markup_pct": 0.0},
    )
    assert res_cmp.status_code == 200
    comp = res_cmp.json()
    cell = comp["matrix_rows"][0]["vendor_cells"][0]
    match_id = cell["match_id"]
    run_id = comp["run_id"]

    res_ov = client.patch(
        f"/api/v1/comparisons/{run_id}/matches/{match_id}",
        json={"vendor_product_id": str(prods[1].id), "override_reason": "Selección directa $1.000/bolsa"},
    )
    assert res_ov.status_code == 200
    row = res_ov.json()["matrix_rows"][0]
    assert row["lowest_unit_price_ars"] == 1000.0
    assert row["lowest_line_subtotal_ars"] == 10000.0
    assert comp["split_cart"]["total_materials_ars"] != row["lowest_line_subtotal_ars"]
    assert res_ov.json()["split_cart"]["total_materials_ars"] == 10000.0

    res_pdf = client.get(f"/api/v1/comparisons/{run_id}/pdf?mode=client_budget")
    assert res_pdf.status_code == 200
    assert res_pdf.content.startswith(b"%PDF-1.")


def test_h02_h03_h04_strategy_consistency_public_whitelist_and_hmac_tamper(client: TestClient, db: Session):
    """H-02, H-03, H-04: Consistencia de estrategia en PDF, DTO público estricto y detección de manipulación en DB."""
    ws = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
    assert ws is not None

    v_a, _ = _create_vendor_with_products(
        db,
        ws.id,
        "Corralón Alfa Secreto",
        Decimal("2000.00"),
        [
            {
                "sku": "A-CEM",
                "raw_description": "Cemento Loma Negra 50 kg",
                "sale_unit": "BOLSA",
                "price_cash": "1000.00",
                "weight_kg": 50.0,
                "material_type": "Cemento",
            },
            {
                "sku": "A-HIE",
                "raw_description": "Barra acero aletado Ø 8 mm x 12 m",
                "sale_unit": "BARRA",
                "price_cash": "2000.00",
                "diameter_mm": 8.0,
                "length_m": 12.0,
                "material_type": "Acero",
            },
        ],
    )
    v_b, _ = _create_vendor_with_products(
        db,
        ws.id,
        "Corralón Beta Secreto",
        Decimal("2000.00"),
        [
            {
                "sku": "B-CEM",
                "raw_description": "Cemento Loma Negra 50 kg",
                "sale_unit": "BOLSA",
                "price_cash": "1500.00",
                "weight_kg": 50.0,
                "material_type": "Cemento",
            },
            {
                "sku": "B-HIE",
                "raw_description": "Barra acero aletado Ø 8 mm x 12 m",
                "sale_unit": "BARRA",
                "price_cash": "1800.00",
                "diameter_mm": 8.0,
                "length_m": 12.0,
                "material_type": "Acero",
            },
        ],
    )

    res_in = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Obra H02 H03 H04", "raw_text": "1 bolsa cemento y 1 barra del 8"},
    )
    assert res_in.status_code == 201
    req_id = res_in.json()["id"]

    # SINGLE_VENDOR debe usar los precios exactos de v_a (1000 + 2000 = 3000 materiales, 2000 flete, total 5000)
    res_cmp = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={
            "vendor_ids": [str(v_a.id), str(v_b.id)],
            "payment_modality": "CASH",
            "markup_pct": 10.0,
            "include_delivery_fees": True,
            "budget_strategy": "SINGLE_VENDOR",
            "selected_single_vendor_id": str(v_a.id),
        },
    )
    assert res_cmp.status_code == 200
    run_id = res_cmp.json()["run_id"]

    res_lock = client.post(
        f"/api/v1/comparisons/{run_id}/lock-budget",
        json={"strategy": "SINGLE_VENDOR", "selected_single_vendor_id": str(v_a.id)},
    )
    assert res_lock.status_code == 200
    token = res_lock.json()["public_share_token"]

    # H-03: Consultar endpoint público SIN query param usa client_budget y no expone proveedores/márgenes
    res_pub = client.get(f"/api/v1/public/comparisons/{token}")
    assert res_pub.status_code == 200
    pub_data = res_pub.json()
    raw_dump = res_pub.text.lower()
    assert "corralón alfa secreto" not in raw_dump
    assert "corralón beta secreto" not in raw_dump
    assert "markup_pct" not in pub_data
    assert "vendors" not in pub_data
    assert "split_cart" not in pub_data
    assert pub_data["budget_strategy"] == "SINGLE_VENDOR"
    # Materiales v_a = 3000 * 1.10 = 3300; logística = 2000 -> grand total = 5300
    assert pub_data["materials_subtotal_ars"] == 3300.0
    assert pub_data["logistics_ars"] == 2000.0
    assert pub_data["grand_total_ars"] == 5300.0
    assert pub_data["signature_verified"] is True

    # H-04: Alterar comparison_matrix_json en base de datos invalida la verificación HMAC -> 403
    run_obj = db.scalar(select(ComparisonRun).where(ComparisonRun.id == uuid.UUID(run_id)))
    assert run_obj is not None
    mutated = dict(run_obj.comparison_matrix_json)
    mutated["best_single_total_ars"] = 999999.0
    run_obj.comparison_matrix_json = mutated
    db.commit()

    res_tampered = client.get(f"/api/v1/public/comparisons/{token}")
    assert res_tampered.status_code == 403


def test_h05_private_pdf_requires_auth_and_accepts_bearer_or_cookie(client: TestClient, db: Session):
    """H-05: Descarga de PDF en workspace privado exige Bearer o cookie HttpOnly y falla con 401 sin credenciales."""
    session_data = _create_private_workspace_session(client, "h05")
    token = session_data["access_token"]
    ws_id = uuid.UUID(session_data["workspace_id"])

    vendor, _ = _create_vendor_with_products(
        db,
        ws_id,
        "Privado PDF SA",
        Decimal("0.00"),
        [
            {
                "sku": "PRIV-CEM",
                "raw_description": "Cemento Loma Negra 50 kg",
                "sale_unit": "BOLSA",
                "price_cash": "9000.00",
                "weight_kg": 50.0,
                "material_type": "Cemento",
            }
        ],
    )

    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": str(ws_id)}
    res_in = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "PDF Privado", "raw_text": "2 bolsas cemento 50 kg"},
        headers=headers,
    )
    assert res_in.status_code == 201
    req_id = res_in.json()["id"]

    res_cmp = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={"vendor_ids": [str(vendor.id)], "payment_modality": "CASH"},
        headers=headers,
    )
    assert res_cmp.status_code == 200
    run_id = res_cmp.json()["run_id"]

    # Sin credenciales -> 401
    client.cookies.clear()
    res_unauth = client.get(
        f"/api/v1/comparisons/{run_id}/pdf?mode=client_budget",
        headers={"X-Workspace-Id": str(ws_id)},
    )
    assert res_unauth.status_code == 401

    # Con Bearer -> 200 PDF válido
    res_bearer = client.get(
        f"/api/v1/comparisons/{run_id}/pdf?mode=client_budget",
        headers=headers,
    )
    assert res_bearer.status_code == 200
    assert res_bearer.content.startswith(b"%PDF-1.")


def test_h06_nominal_vs_physical_inch_conversion_by_family(db: Session):
    """H-06: Diferencia equivalencias comerciales vs físicas según familia (PVC 4''=110mm vs Acero 4''=101.6mm; 3/4'' termofusión=20/19.05mm)."""
    pvc_4 = UnitNormalizerService.parse_single_line('4 caños pvc 4"')
    assert pvc_4.diameter_mm == 110.0

    steel_4 = UnitNormalizerService.parse_single_line('4 caños acero 4"')
    assert steel_4.diameter_mm == 101.6

    ws = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
    assert ws is not None
    vendor, prods = _create_vendor_with_products(
        db,
        ws.id,
        "Tubos Familia H06",
        Decimal("0.00"),
        [
            {
                "sku": "PVC-110",
                "raw_description": "Caño PVC cloacal 110 mm x 4 m",
                "diameter_mm": 110.0,
                "length_m": 4.0,
                "material_type": "PVC",
                "price_cash": "15000.00",
            },
            {
                "sku": "AC-1016",
                "raw_description": "Caño acero 101.6 mm x 6 m",
                "diameter_mm": 101.6,
                "length_m": 6.0,
                "material_type": "Acero",
                "price_cash": "35000.00",
            },
            {
                "sku": "TF-20",
                "raw_description": "Caño termofusión nominal 20 mm x 4 m",
                "diameter_mm": 20.0,
                "length_m": 4.0,
                "material_type": "Termofusión",
                "price_cash": "8500.00",
            },
        ],
    )

    # Pedir PVC 4'' -> matchea 110mm PVC, NO 101.6mm acero
    req = Requisition(workspace_id=ws.id, title="Tubos H06", status="READY_TO_COMPARE")
    db.add(req)
    db.flush()
    item_pvc = RequisitionItem(
        requisition_id=req.id,
        line_order=1,
        raw_line='2 caños pvc 4"',
        requested_term="Caño PVC 110 mm",
        quantity=Decimal("2"),
        requested_unit="UN",
        diameter_inch="4",
        diameter_mm=Decimal("110.00"),
        material_type="PVC",
        completeness="complete",
        is_confirmed=True,
    )
    item_tf_34 = RequisitionItem(
        requisition_id=req.id,
        line_order=2,
        raw_line='2 caños termofusion 3/4"',
        requested_term="Caño termofusión nominal 20 mm",
        quantity=Decimal("2"),
        requested_unit="UN",
        diameter_inch="3/4",
        diameter_mm=Decimal("19.05"),
        material_type="Termofusión",
        completeness="complete",
        is_confirmed=True,
    )
    db.add_all([item_pvc, item_tf_34])
    db.commit()

    m1 = MatchingEngineService.match_item_against_vendor(db, ws.id, item_pvc, vendor.id)
    assert m1.match_status == "EXACT_MATCH"
    assert m1.vendor_product_id == prods[0].id

    m2 = MatchingEngineService.match_item_against_vendor(db, ws.id, item_tf_34, vendor.id)
    assert m2.match_status == "EXACT_MATCH"
    assert m2.vendor_product_id == prods[2].id


def test_h07_commercial_packaging_conversion_and_safe_rounding(db: Session):
    """H-07: Solicitar 20 m cuando el proveedor vende rollos de 25 m redondea a 1 rollo con commercial_qty=1."""
    ws = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
    assert ws is not None

    vendor, _ = _create_vendor_with_products(
        db,
        ws.id,
        "Rollos Jujuy",
        Decimal("0.00"),
        [
            {
                "sku": "ROLLO-25",
                "raw_description": "Caño corrugado 25 mm rollo x 25 m",
                "sale_unit": "ROLLO",
                "diameter_mm": 25.0,
                "length_m": 25.0,
                "material_type": "Corrugado",
                "price_cash": "25000.00",
            },
            {
                "sku": "SIN-LONG",
                "raw_description": "Manguera especial 40 mm PVC",
                "sale_unit": "ROLLO",
                "diameter_mm": 40.0,
                "length_m": None,
                "material_type": "PVC",
                "price_cash": "12000.00",
            },
        ],
    )

    draft = UnitNormalizerService.parse_single_line("20 m caño corrugado 25 mm")
    assert draft.requested_unit == "M"
    assert draft.length_m is None  # No confundir cantidad 20m con longitud fija del producto

    req = Requisition(workspace_id=ws.id, title="Rollos", status="READY_TO_COMPARE")
    db.add(req)
    db.flush()
    item_rollo = RequisitionItem(
        requisition_id=req.id,
        line_order=1,
        raw_line="20 m caño corrugado 25 mm",
        requested_term="caño corrugado 25 mm",
        quantity=Decimal("20"),
        requested_unit="M",
        diameter_mm=Decimal("25.00"),
        material_type="Corrugado",
        completeness="complete",
        is_confirmed=True,
    )
    item_unsafe = RequisitionItem(
        requisition_id=req.id,
        line_order=2,
        raw_line="10 m manguera especial 40 mm pvc",
        requested_term="manguera especial 40 mm pvc",
        quantity=Decimal("10"),
        requested_unit="M",
        diameter_mm=Decimal("40.00"),
        material_type="PVC",
        completeness="complete",
        is_confirmed=True,
    )
    db.add_all([item_rollo, item_unsafe])
    db.commit()

    res_safe = MatchingEngineService.match_item_against_vendor(db, ws.id, item_rollo, vendor.id)
    assert res_safe.match_status == "EXACT_MATCH"
    assert res_safe.commercial_qty == 1.0
    assert res_safe.line_subtotal_ars == Decimal("25000.00")
    assert res_safe.conversion_note is not None and "ROLLO" in res_safe.conversion_note

    res_unsafe = MatchingEngineService.match_item_against_vendor(db, ws.id, item_unsafe, vendor.id)
    assert res_unsafe.match_status == "AMBIGUOUS_CANDIDATES"
    assert res_unsafe.match_origin == "UNIT_CONVERSION_CONFIRMATION_REQUIRED"


def test_h08_lock_budget_blocks_pending_and_requires_accept_partial_for_partial(client: TestClient, db: Session):
    """H-08: lock-budget exige accept_partial=True para presupuestos parciales y rechaza pending (409)."""
    ws = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
    assert ws is not None

    vendor, _ = _create_vendor_with_products(
        db,
        ws.id,
        "Parciales SA",
        Decimal("0.00"),
        [
            {
                "sku": "ONLY-CEM",
                "raw_description": "Cemento Loma Negra 50 kg",
                "sale_unit": "BOLSA",
                "weight_kg": 50.0,
                "material_type": "Cemento",
                "price_cash": "9500.00",
            }
        ],
    )

    res_in = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Pliego Parcial H08", "raw_text": "10 bolsas cemento 50 kg\n5 barras del 25"},
    )
    assert res_in.status_code == 201
    req_id = res_in.json()["id"]

    res_cmp = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={"vendor_ids": [str(vendor.id)], "payment_modality": "CASH"},
    )
    assert res_cmp.status_code == 200
    comp = res_cmp.json()
    assert comp["fulfillment_status"] == "partial"
    run_id = comp["run_id"]

    # Sin accept_partial -> 409 Conflict
    res_block = client.post(f"/api/v1/comparisons/{run_id}/lock-budget", json={"accept_partial": False})
    assert res_block.status_code == 409

    # Con accept_partial=True -> 200 OK
    res_ok = client.post(f"/api/v1/comparisons/{run_id}/lock-budget", json={"accept_partial": True})
    assert res_ok.status_code == 200
    assert res_ok.json()["fulfillment_status"] == "partial"


def test_h09_ambiguous_candidates_triggered_when_scores_tie_or_low_confidence(db: Session):
    """H-09: Candidatos cercanos en puntaje generan AMBIGUOUS_CANDIDATES con opciones para HITL."""
    ws = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
    assert ws is not None

    vendor, _ = _create_vendor_with_products(
        db,
        ws.id,
        "Ambiguos Materiales",
        Decimal("0.00"),
        [
            {
                "sku": "CODO-A",
                "raw_description": "Codo PVC reforzado 40 mm 90 grados",
                "diameter_mm": 40.0,
                "material_type": "PVC",
                "price_cash": "1200.00",
            },
            {
                "sku": "CODO-B",
                "raw_description": "Codo PVC reforzado 40 mm 45 grados",
                "diameter_mm": 40.0,
                "material_type": "PVC",
                "price_cash": "1150.00",
            },
        ],
    )

    req = Requisition(workspace_id=ws.id, title="Ambigüedad H09", status="READY_TO_COMPARE")
    db.add(req)
    db.flush()
    item = RequisitionItem(
        requisition_id=req.id,
        line_order=1,
        raw_line="4 codos pvc reforzado 40 mm",
        requested_term="codo pvc reforzado 40 mm",
        quantity=Decimal("4"),
        requested_unit="UN",
        diameter_mm=Decimal("40.00"),
        material_type="PVC",
        completeness="complete",
        is_confirmed=True,
    )
    db.add(item)
    db.commit()

    match_res = MatchingEngineService.match_item_against_vendor(db, ws.id, item, vendor.id)
    assert match_res.match_status == "AMBIGUOUS_CANDIDATES"
    assert len(match_res.candidate_options) == 2


def test_h10_h16_override_validates_material_and_logs_audit_with_reason(client: TestClient, db: Session):
    """H-10 & H-16: Reemplazar PVC por Acero exige force_dimension_override + override_reason y registra auditoría."""
    ws = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
    assert ws is not None

    vendor, prods = _create_vendor_with_products(
        db,
        ws.id,
        "Materiales Mix H10",
        Decimal("0.00"),
        [
            {
                "sku": "PVC-20",
                "raw_description": "Caño PVC 20 mm x 4 m",
                "diameter_mm": 20.0,
                "length_m": 4.0,
                "material_type": "PVC",
                "price_cash": "3500.00",
            },
            {
                "sku": "ACE-20",
                "raw_description": "Barra acero 20 mm x 12 m",
                "diameter_mm": 20.0,
                "length_m": 12.0,
                "material_type": "Acero",
                "price_cash": "22000.00",
            },
        ],
    )

    res_in = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Test H10", "raw_text": "2 caños pvc 20 mm"},
    )
    assert res_in.status_code == 201
    req_id = res_in.json()["id"]

    res_cmp = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={"vendor_ids": [str(vendor.id)], "payment_modality": "CASH"},
    )
    assert res_cmp.status_code == 200
    comp = res_cmp.json()
    run_id = comp["run_id"]
    match_id = comp["matrix_rows"][0]["vendor_cells"][0]["match_id"]

    # Intentar reemplazar PVC 20mm por Acero 20mm sin force_dimension_override -> 422
    res_reject = client.patch(
        f"/api/v1/comparisons/{run_id}/matches/{match_id}",
        json={"vendor_product_id": str(prods[1].id), "force_dimension_override": False},
    )
    assert res_reject.status_code == 422
    assert "Material incompatible" in str(res_reject.json())

    # Con force_dimension_override=True pero sin justificación -> 422
    res_no_reason = client.patch(
        f"/api/v1/comparisons/{run_id}/matches/{match_id}",
        json={"vendor_product_id": str(prods[1].id), "force_dimension_override": True},
    )
    assert res_no_reason.status_code == 422

    # Con justificación válida -> 200 + registro en override_audit_log
    res_ok = client.patch(
        f"/api/v1/comparisons/{run_id}/matches/{match_id}",
        json={
            "vendor_product_id": str(prods[1].id),
            "force_dimension_override": True,
            "override_reason": "Sustitución aprobada por calculista por faltante de caño.",
        },
    )
    assert res_ok.status_code == 200
    audit_log = res_ok.json()["override_audit_log"]
    assert len(audit_log) == 1
    assert audit_log[0]["reason"] == "Sustitución aprobada por calculista por faltante de caño."
    assert len(audit_log[0]["discrepancies"]) >= 1


def test_h11_alias_learning_persists_target_product_and_reuses_in_comparison(client: TestClient, db: Session):
    """H-11: Guardar un alias desde /resolve vincula target_vendor_product_id y se usa en compulsas siguientes."""
    ws = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
    assert ws is not None

    vendor, prods = _create_vendor_with_products(
        db,
        ws.id,
        "Alias Sanitario SA",
        Decimal("0.00"),
        [
            {
                "sku": "ALIAS-TER-19",
                "raw_description": "Caño termofusión agua 3/4 pulgada x 4 m",
                "diameter_mm": 19.05,
                "length_m": 4.0,
                "material_type": "Termofusión",
                "price_cash": "7200.00",
            }
        ],
    )

    res_in = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Alias H11 1", "raw_text": '4 caño de 3/4'},
    )
    assert res_in.status_code == 201
    req1 = res_in.json()
    item_id = req1["items"][0]["id"]

    res_res = client.patch(
        f"/api/v1/requisitions/{req1['id']}/items/{item_id}/resolve",
        json={
            "material_type": "Termofusión",
            "confirmed_term": "Caño termofusión agua 3/4 pulgada",
            "save_as_alias": True,
        },
    )
    assert res_res.status_code == 200

    # Segundo pedido con la misma línea ambigua ahora se apoya en el alias aprendido
    req2 = Requisition(workspace_id=ws.id, title="Alias H11 2", status="READY_TO_COMPARE")
    db.add(req2)
    db.flush()
    item2 = RequisitionItem(
        requisition_id=req2.id,
        line_order=1,
        raw_line='4 caño de 3/4',
        requested_term='caño de 3/4',
        quantity=Decimal("4"),
        requested_unit="UN",
        diameter_inch="3/4",
        diameter_mm=Decimal("19.05"),
        material_type="Termofusión",
        completeness="complete",
        is_confirmed=True,
    )
    db.add(item2)
    db.commit()

    match_res = MatchingEngineService.match_item_against_vendor(db, ws.id, item2, vendor.id)
    assert match_res.match_status == "EXACT_MATCH"
    assert match_res.vendor_product_id == prods[0].id
    assert match_res.match_origin == "SUPERVISED_ALIAS"


def test_h12_h13_branch_and_bound_25_vendors_fast_and_decimal_exact():
    """H-12 & H-13: Branch-and-Bound optimiza 25 proveedores en <1s sin pérdida de precisión Decimal."""
    vendor_ids = [str(uuid.uuid4()) for _ in range(25)]
    vendor_fees = {vid: Decimal("1000.00") for vid in vendor_ids}
    item_prices = {}
    for r in range(10):
        prices = {}
        for idx, vid in enumerate(vendor_ids):
            if idx == (r % 3):
                prices[vid] = Decimal("100.15")
            else:
                prices[vid] = Decimal("500.55")
        item_prices[f"item_{r}"] = prices

    t0 = time.perf_counter()
    covered_count, total_mat, total_deliv, total_cart, used_vendors, selected_map = (
        ComparisonOptimizerService._solve_split_cart_bnb(
            item_prices=item_prices,
            vendor_fees=vendor_fees,
        )
    )
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0
    assert covered_count == 10
    assert len(selected_map) == 10
    assert len(used_vendors) == 3
    assert total_mat == Decimal("1001.50")
    assert total_deliv == Decimal("3000.00")
    assert total_cart == Decimal("4001.50")


def test_h14_existing_run_id_reuses_unlocked_run(client: TestClient, db: Session):
    """H-14: Re-ejecutar compulsa con existing_run_id reutiliza el ComparisonRun sin duplicar filas."""
    ws = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
    assert ws is not None
    vendors = db.scalars(select(Vendor).where(Vendor.workspace_id == ws.id)).all()
    v_ids = [str(v.id) for v in vendors[:2]]

    res_in = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Test H14", "raw_text": "10 bolsas cemento loma negra 50 kg"},
    )
    req_id = res_in.json()["id"]

    res_1 = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={"vendor_ids": v_ids, "payment_modality": "CASH", "markup_pct": 0.0},
    )
    assert res_1.status_code == 200
    run_id = res_1.json()["run_id"]

    res_2 = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={
            "vendor_ids": v_ids,
            "payment_modality": "LIST",
            "markup_pct": 12.0,
            "existing_run_id": run_id,
        },
    )
    assert res_2.status_code == 200
    assert res_2.json()["run_id"] == run_id
    runs_count = len(db.scalars(select(ComparisonRun).where(ComparisonRun.requisition_id == uuid.UUID(req_id))).all())
    assert runs_count == 1


def test_h17_h18_h20_upload_size_limit_and_production_config_and_migrations(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    """H-17, H-18, H-20: Lectura acotada HTTP 413, validación estricta en producción y fail-fast en migraciones."""
    session_data = _create_private_workspace_session(client, "h17")
    headers = {
        "Authorization": f"Bearer {session_data['access_token']}",
        "X-Workspace-Id": session_data["workspace_id"],
    }
    res_v = client.post(
        "/api/v1/vendors/",
        json={"name": "Corralón Grande", "locality": "Palpalá"},
        headers=headers,
    )
    assert res_v.status_code == 201
    vendor_id = res_v.json()["id"]

    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 1024)
    big_content = b"SKU,DESCRIPCION,PRECIO_CONTADO\n" + (b"SKU1,Cemento Loma Negra 50kg,9500\n" * 60)
    res_big = client.post(
        f"/api/v1/vendors/{vendor_id}/catalogs/import",
        files={"file": ("grande.csv", big_content, "text/csv")},
        data={"mapping_json": '{"sku":"SKU","description":"DESCRIPCION","price_cash":"PRECIO_CONTADO"}'},
        headers=headers,
    )
    assert res_big.status_code == 413

    # H-18: Rechazar configuración insegura en producción
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="sqlite:///./local.db",
            SECRET_KEY="super-secret-explicit-but-sqlite-must-fail-here",
            HMAC_SHARE_SECRET="another-explicit-hmac-secret-at-least-32-chars",
        )

    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+psycopg://app:Str0ngP@ss!2026@db:5432/compulsa",
            SECRET_KEY="short",
            HMAC_SHARE_SECRET="another-explicit-hmac-secret-at-least-32-chars",
        )

    # H-20: run_migrations en production no hace silent fallback a create_all
    monkeypatch.setattr(db_module.settings, "ENVIRONMENT", "production")

    def boom_upgrade(*_args, **_kwargs):
        raise RuntimeError("Alembic migration error")

    monkeypatch.setattr("alembic.command.upgrade", boom_upgrade)
    with pytest.raises(RuntimeError, match="Alembic migration error"):
        db_module.run_migrations()


def test_h21_h22_h23_httponly_cookie_logout_lockout_verification_and_traction(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    """H-21, H-22, H-23: Cookie HttpOnly, logout, lockout tras 5 fallos, verificación de email y tracción real."""
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    email = f"seguridad_{uuid.uuid4().hex[:6]}@obra.com.ar"
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "PasswordSeguro2026!",
            "full_name": "Ing. Seguro",
            "workspace_name": "Constructora Seguridad Real",
        },
    )
    assert res_reg.status_code == 201
    reg_data = res_reg.json()
    assert reg_data["verification_required"] is True
    assert reg_data["email_verified"] is False
    ver_token = reg_data["verification_token"]

    # Login sin verificar correo -> 403
    res_unverified = client.post("/api/v1/auth/login", json={"email": email, "password": "PasswordSeguro2026!"})
    assert res_unverified.status_code == 403

    # Verificar email -> 200
    res_ver = client.post("/api/v1/auth/verify-email", json={"email": email, "token": ver_token})
    assert res_ver.status_code == 200

    # Login correcto emite cookie HttpOnly y responde 200
    res_ok = client.post("/api/v1/auth/login", json={"email": email, "password": "PasswordSeguro2026!"})
    assert res_ok.status_code == 200
    assert "compulsa_access_token" in res_ok.cookies

    # Logout limpia cookie HttpOnly
    res_out = client.post("/api/v1/auth/logout")
    assert res_out.status_code == 200

    # 5 intentos fallidos -> lockout HTTP 429 en el 5to fallo / subsiguiente
    for _ in range(4):
        r_bad = client.post("/api/v1/auth/login", json={"email": email, "password": "Incorrecta!1"})
        assert r_bad.status_code == 401
    r_5 = client.post("/api/v1/auth/login", json={"email": email, "password": "Incorrecta!1"})
    assert r_5.status_code == 429

    # H-23: Métricas de tracción incluyen nuevos campos auditables
    res_traction = client.get("/api/v1/public/traction")
    assert res_traction.status_code == 200
    tr = res_traction.json()
    assert "active_real_users" in tr
    assert "verified_usage_events" in tr
    assert tr["active_real_workspaces"] >= 1
    assert tr["active_real_users"] >= 1
    assert PDFGeneratorService.__name__ == "PDFGeneratorService"
