"""Suite integral de regresión y verificación empírica para la remediación completa de auditoría."""

from io import BytesIO
import json
from pathlib import Path
import uuid

from fastapi.testclient import TestClient
import openpyxl
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    AUTH_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    verify_hmac_share_token,
)
from app.models.comparison import ComparisonRun
from app.models.vendor import VendorProduct
from app.models.workspace import Workspace
from app.services.email_service import EmailService
from app.services.matching_engine import MatchingEngineService
from app.services.unit_normalizer import UnitNormalizerService


def _register_verified_session(client: TestClient, tag: str) -> dict:
    email = f"remed_{tag}_{uuid.uuid4().hex[:6]}@constructora.com.ar"
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "PasswordSeguro2026!",
            "full_name": f"Ing. {tag}",
            "workspace_name": f"Estudio {tag}",
            "role": "ESTIMATOR",
        },
    )
    assert res.status_code == 201, res.text
    token = EmailService.get_outbox(email)[-1].verification_token
    res_ver = client.post("/api/v1/auth/verify-email", json={"email": email, "token": token})
    assert res_ver.status_code == 200, res_ver.text
    data = res_ver.json()
    data["csrf_token"] = client.cookies.get(CSRF_COOKIE_NAME)
    return data


def _build_xlsx_bytes(rows: list[list[object]]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_dh3_dh4_unit_normalizer_and_commercial_conversions(db: Session):
    """D-H3 / D-H4: Normalizador NOA (miles ARS, fracciones, conjunciones) y conversión lineal/ponderal."""
    items = UnitNormalizerService.parse_and_normalize_line(
        "1.500 ladrillos comunes\n"
        "2,5 kg alambre recocido\n"
        'Caño Termofusión 3/4"\n'
        "20 barra del 8 y 4 caño de 3/4 + 10 bolsas cemento"
    )
    assert len(items) == 6

    assert items[0].quantity == pytest.approx(1500.0)
    assert "ladrillo" in items[0].requested_term.lower()

    assert items[1].quantity == pytest.approx(2.5)
    assert items[1].requested_unit == "KG"

    assert items[2].quantity == pytest.approx(1.0)
    assert items[2].diameter_inch == "3/4"
    assert items[2].diameter_mm == pytest.approx(19.05)
    assert items[2].material_type == "Termofusión"
    assert items[2].completeness == "complete"

    # "20 barra del 8"
    assert items[3].quantity == pytest.approx(20.0)
    assert items[3].material_type == "Acero"
    assert items[3].diameter_mm == pytest.approx(8.0)
    assert items[3].length_m == pytest.approx(12.0)

    # "4 caño de 3/4" sin material -> bloqueado HITL
    assert items[4].quantity == pytest.approx(4.0)
    assert items[4].diameter_mm == pytest.approx(19.05)
    assert items[4].completeness == "missing_critical_attribute"
    assert items[4].is_confirmed is False

    # Conversión comercial lineal (metros a tiras) y ponderal (kg a bolsas)
    from decimal import Decimal
    from app.models.requisition import RequisitionItem

    item_m = RequisitionItem(
        id=uuid.uuid4(),
        requisition_id=uuid.uuid4(),
        line_order=1,
        raw_line="10 m caño pvc 110 mm",
        requested_term="Caño PVC 110 mm",
        quantity=Decimal("10"),
        requested_unit="M",
        diameter_mm=Decimal("110"),
        material_type="PVC",
        completeness="complete",
        is_confirmed=True,
    )
    prod_pipe = VendorProduct(
        id=uuid.uuid4(),
        price_list_id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        sku="PVC-110-4M",
        raw_description="Caño PVC 110 mm x 4 m",
        normalized_description="cano pvc 110 mm x 4 m",
        sale_unit="UN",
        price_cash_ars=Decimal("18000.00"),
        price_list_ars=Decimal("20000.00"),
        diameter_mm=Decimal("110.00"),
        length_m=Decimal("4.00"),
        material_type="PVC",
        row_sha256="pvc110_4m",
    )
    comm_qty, sale_unit, _, is_safe = MatchingEngineService.calculate_commercial_quantity(item_m, prod_pipe)
    assert is_safe is True
    assert comm_qty == Decimal("3")
    assert sale_unit == "UN"

    item_kg = RequisitionItem(
        id=uuid.uuid4(),
        requisition_id=uuid.uuid4(),
        line_order=2,
        raw_line="120 kg cemento portland",
        requested_term="Cemento Portland 50 kg",
        quantity=Decimal("120"),
        requested_unit="KG",
        weight_kg=Decimal("50"),
        material_type="Cemento",
        completeness="complete",
        is_confirmed=True,
    )
    prod_cem = VendorProduct(
        id=uuid.uuid4(),
        price_list_id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        sku="CEM-50",
        raw_description="Cemento Portland 50 kg",
        normalized_description="cemento portland 50 kg",
        sale_unit="BOLSA",
        price_cash_ars=Decimal("9500.00"),
        price_list_ars=Decimal("10500.00"),
        weight_kg=Decimal("50.00"),
        material_type="Cemento",
        row_sha256="cem50",
    )
    bag_qty, bag_unit, _, bag_safe = MatchingEngineService.calculate_commercial_quantity(item_kg, prod_cem)
    assert bag_safe is True
    assert bag_qty == Decimal("3")
    assert bag_unit == "BOLSA"


def test_co10_co12_xlsx_import_and_intrabatch_deduplication(client: TestClient, db: Session):
    """CO-10 / CO-12: Importación HTTP de .xlsx real, deduplicación intra-lote y reimportación incremental SHA-256."""
    session = _register_verified_session(client, "xlsx")
    headers = {CSRF_HEADER_NAME: session["csrf_token"]}

    res_v = client.post(
        "/api/v1/vendors",
        json={
            "name": "Corralón XLSX Norte",
            "locality": "San Salvador de Jujuy",
            "cash_discount_pct": 5.0,
            "estimate_delivery_fee_ars": 5000.0,
        },
        headers=headers,
    )
    assert res_v.status_code == 201, res_v.text
    vendor_id = res_v.json()["id"]

    xlsx_v1 = _build_xlsx_bytes([
        ["sku", "descripcion", "precio_contado", "precio_lista", "unidad", "marca", "categoria"],
        ["XLS-CEM", "Cemento Portland Loma Negra 50 kg", "$ 9.500,00", "$ 10.500,00", "BOLSA", "Loma Negra", "Obra"],
        # Duplicado idéntico intra-lote en SKU+descripción (CO-12)
        ["xls-cem", "Cemento Portland Loma Negra 50 kg", "$ 9.600,00", "$ 10.600,00", "BOLSA", "Loma Negra", "Obra"],
        ["XLS-H8", "Barra Hierro Aletado 8 mm x 12 m", "9800", "10800", "BARRA", "Acindar", "Acero"],
    ])

    res_imp1 = client.post(
        f"/api/v1/vendors/{vendor_id}/catalogs/import",
        files={"file": ("lista_v1.xlsx", xlsx_v1, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert res_imp1.status_code == 200, res_imp1.text
    summary1 = res_imp1.json()
    assert summary1["version_number"] == 1
    assert summary1["new_or_updated_rows"] == 2
    assert summary1["unchanged_skipped_rows"] == 0

    xlsx_v2 = _build_xlsx_bytes([
        ["sku", "descripcion", "precio_contado", "precio_lista", "unidad", "marca", "categoria"],
        ["XLS-CEM", "Cemento Portland Loma Negra 50 kg", "$ 9.900,00", "$ 10.900,00", "BOLSA", "Loma Negra", "Obra"],
        ["XLS-H8", "Barra Hierro Aletado 8 mm x 12 m", "9800", "10800", "BARRA", "Acindar", "Acero"],
        ["XLS-PVC110", "Caño PVC 110 mm x 4 m", "17500", "19200", "UN", "Tigre", "Plomeria"],
    ])
    res_imp2 = client.post(
        f"/api/v1/vendors/{vendor_id}/catalogs/import",
        files={"file": ("lista_v2.xlsx", xlsx_v2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert res_imp2.status_code == 200, res_imp2.text
    summary2 = res_imp2.json()
    assert summary2["version_number"] == 2
    assert summary2["unchanged_skipped_rows"] == 2
    assert summary2["new_or_updated_rows"] == 1


def test_co02_image_priority_over_raw_text_and_invalid_preset_400(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """CO-02: image_bytes tiene prioridad sobre raw_text residual (503 sin API Key) y preset inválido da 400."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    session = _register_verified_session(client, "co02")
    headers = {CSRF_HEADER_NAME: session["csrf_token"]}

    res_img = client.post(
        "/api/v1/requisitions/ingest",
        data={"title": "Imagen + texto residual", "raw_text": "10 bolsas cemento loma negra"},
        files={"image_file": ("manuscrito.png", b"\x89PNG\r\n\x1a\nfakebytes", "image/png")},
        headers=headers,
    )
    assert res_img.status_code == 503
    assert "gemini" in str(res_img.json()).lower() or "imagen" in str(res_img.json()).lower()

    res_bad_form = client.post(
        "/api/v1/requisitions/ingest",
        data={"title": "Preset inválido", "preset_id": "preset_inexistente"},
        headers=headers,
    )
    assert res_bad_form.status_code == 400

    res_bad_json = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Preset inválido JSON", "preset_id": "preset_inexistente"},
        headers=headers,
    )
    assert res_bad_json.status_code == 400


def test_e2e01_compare_endpoint_blocks_ambiguous_item_until_resolved(client: TestClient):
    """E2E-01: /compare bloquea con 422 mientras exista ítem pendiente HITL; tras resolver, compulsa con 200."""
    session = _register_verified_session(client, "e2e01")
    headers = {CSRF_HEADER_NAME: session["csrf_token"]}

    res_v = client.post(
        "/api/v1/vendors",
        json={"name": "Corralón HITL", "locality": "Jujuy", "estimate_delivery_fee_ars": 2000.0},
        headers=headers,
    )
    vendor_id = res_v.json()["id"]
    csv_bytes = (
        "sku,descripcion,precio_contado,precio_lista,unidad\n"
        "H8,Barra Hierro Aletado 8 mm x 12 m,9800,10800,BARRA\n"
        "P34,Caño PVC 3/4,4200,4600,UN\n"
        "CEM,Cemento Portland 50 kg,9400,10400,BOLSA\n"
        "P110,Caño PVC 110 mm x 4 m,17500,19200,UN\n"
    ).encode("utf-8")
    res_imp = client.post(
        f"/api/v1/vendors/{vendor_id}/catalogs/import",
        files={"file": ("catalogo.csv", csv_bytes, "text/csv")},
        headers=headers,
    )
    assert res_imp.status_code == 200

    res_req = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Obra HITL HTTP", "preset_id": "manuscrito_obra"},
        headers=headers,
    )
    assert res_req.status_code == 201
    req_data = res_req.json()
    assert req_data["status"] == "NEEDS_CLARIFICATION"
    assert req_data["pending_clarifications_count"] >= 1
    req_id = req_data["id"]

    # Bloqueo pre-cotización vía HTTP
    res_cmp_blocked = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={"vendor_ids": [vendor_id], "payment_modality": "CASH", "include_delivery_fees": True},
        headers=headers,
    )
    assert res_cmp_blocked.status_code == 422

    pending_item = next(it for it in req_data["items"] if not it["is_confirmed"])
    res_resolve = client.patch(
        f"/api/v1/requisitions/{req_id}/items/{pending_item['id']}/resolve",
        json={"material_type": "PVC"},
        headers=headers,
    )
    assert res_resolve.status_code == 200
    assert res_resolve.json()["status"] == "READY_TO_COMPARE"

    res_cmp_ok = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={"vendor_ids": [vendor_id], "payment_modality": "CASH", "include_delivery_fees": True},
        headers=headers,
    )
    assert res_cmp_ok.status_code == 200
    assert res_cmp_ok.json()["best_single_total_ars"] > 0


def test_e2e04_snapshot_immutability_and_post_lock_guards(client: TestClient):
    """E2E-04: Cambio tras comparar vuelve obsoleta la corrida (409) y LOCKED_BUDGET congela ítem, override y estrategia."""
    session = _register_verified_session(client, "e2e04")
    headers = {CSRF_HEADER_NAME: session["csrf_token"]}

    res_v = client.post(
        "/api/v1/vendors",
        json={"name": "Corralón Snapshot", "locality": "Palpalá", "estimate_delivery_fee_ars": 3000.0},
        headers=headers,
    )
    vendor_id = res_v.json()["id"]
    csv_bytes = (
        "sku,descripcion,precio_contado,precio_lista,unidad\n"
        "CEM50,Cemento Portland 50 kg,9000,10000,BOLSA\n"
    ).encode("utf-8")
    assert client.post(
        f"/api/v1/vendors/{vendor_id}/catalogs/import",
        files={"file": ("cat.csv", csv_bytes, "text/csv")},
        headers=headers,
    ).status_code == 200

    res_req = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Cemento Snapshot", "raw_text": "10 bolsas cemento portland 50 kg"},
        headers=headers,
    )
    assert res_req.status_code == 201
    req_data = res_req.json()
    req_id = req_data["id"]
    item_id = req_data["items"][0]["id"]

    res_cmp = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={"vendor_ids": [vendor_id], "payment_modality": "CASH", "include_delivery_fees": True},
        headers=headers,
    )
    assert res_cmp.status_code == 200
    cmp_data = res_cmp.json()
    run_id = cmp_data["run_id"]
    cell = cmp_data["matrix_rows"][0]["vendor_cells"][0]
    match_id = cell["match_id"]
    prod_id = cell["vendor_product_id"]
    assert match_id and prod_id

    # Cambiar cantidad vuelve obsoleta (STALE) la compulsa -> lock-budget y /pdf devuelven 409
    assert client.patch(
        f"/api/v1/requisitions/{req_id}/items/{item_id}/resolve",
        json={"quantity": 25},
        headers=headers,
    ).status_code == 200
    assert client.get(f"/api/v1/comparisons/{run_id}", headers=headers).json()["is_stale"] is True
    assert client.post(f"/api/v1/comparisons/{run_id}/lock-budget", headers=headers).status_code == 409
    assert client.get(f"/api/v1/comparisons/{run_id}/pdf", headers=headers).status_code == 409

    # Recalcular y congelar definitivamente
    assert client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={
            "vendor_ids": [vendor_id],
            "payment_modality": "CASH",
            "include_delivery_fees": True,
            "existing_run_id": run_id,
        },
        headers=headers,
    ).status_code == 200

    res_lock = client.post(
        f"/api/v1/comparisons/{run_id}/lock-budget",
        json={"accept_partial": False, "strategy": "SINGLE_VENDOR", "selected_single_vendor_id": vendor_id},
        headers=headers,
    )
    assert res_lock.status_code == 200
    assert res_lock.json()["status"] == "LOCKED_BUDGET"

    # Mutaciones posteriores al congelamiento deben rechazarse con 409
    assert client.patch(
        f"/api/v1/requisitions/{req_id}/items/{item_id}/resolve",
        json={"quantity": 30},
        headers=headers,
    ).status_code == 409
    assert client.patch(
        f"/api/v1/comparisons/{run_id}/matches/{match_id}",
        json={"vendor_product_id": prod_id},
        headers=headers,
    ).status_code == 409
    assert client.post(
        f"/api/v1/comparisons/{run_id}/lock-budget",
        json={"accept_partial": False, "strategy": "SPLIT_CART"},
        headers=headers,
    ).status_code == 409

    res_pdf = client.get(f"/api/v1/comparisons/{run_id}/pdf?mode=client_budget", headers=headers)
    assert res_pdf.status_code == 200
    assert res_pdf.content.startswith(b"%PDF-")


def test_sh1_hmac_share_token_bound_to_run_id(client: TestClient, db: Session):
    """S-H1: Un token HMAC firmado para run_A es rechazado si intenta validarse contra run_B (cross-run replay)."""
    session = _register_verified_session(client, "sh1")
    headers = {CSRF_HEADER_NAME: session["csrf_token"]}

    res_v = client.post(
        "/api/v1/vendors",
        json={"name": "Corralón HMAC", "locality": "Jujuy", "estimate_delivery_fee_ars": 1000.0},
        headers=headers,
    )
    vendor_id = res_v.json()["id"]
    csv_bytes = b"sku,descripcion,precio_contado,precio_lista,unidad\nCEM,Cemento Portland 50 kg,9000,10000,BOLSA\n"
    assert client.post(
        f"/api/v1/vendors/{vendor_id}/catalogs/import",
        files={"file": ("hmac.csv", csv_bytes, "text/csv")},
        headers=headers,
    ).status_code == 200

    tokens: list[str] = []
    run_ids: list[str] = []
    for idx in (1, 2):
        r_req = client.post(
            "/api/v1/requisitions/ingest-json",
            json={"title": f"Obra HMAC {idx}", "raw_text": "10 bolsas cemento portland 50 kg"},
            headers=headers,
        )
        req_id = r_req.json()["id"]
        r_cmp = client.post(
            f"/api/v1/requisitions/{req_id}/compare",
            json={"vendor_ids": [vendor_id], "payment_modality": "CASH", "include_delivery_fees": True},
            headers=headers,
        )
        run_id = r_cmp.json()["run_id"]
        r_lock = client.post(
            f"/api/v1/comparisons/{run_id}/lock-budget",
            json={"accept_partial": False, "strategy": "SINGLE_VENDOR", "selected_single_vendor_id": vendor_id},
            headers=headers,
        )
        assert r_lock.status_code == 200
        run_ids.append(run_id)
        tokens.append(r_lock.json()["public_share_token"])

    run_b = db.scalar(select(ComparisonRun).where(ComparisonRun.id == uuid.UUID(run_ids[1])))
    assert run_b is not None
    assert (
        verify_hmac_share_token(
            tokens[0],
            str(run_b.requisition_id),
            run_b.comparison_matrix_json,
            expected_snapshot_hash=run_b.locked_snapshot_hash,
            expected_run_id=str(run_b.id),
        )
        is False
    )

    # Si un registro DB apuntara al token de run_A pero el objeto fuera run_B, /public debe responder 403
    run_a = db.scalar(select(ComparisonRun).where(ComparisonRun.id == uuid.UUID(run_ids[0])))
    assert run_a is not None
    run_b_orig_token = run_b.public_share_token
    run_a.public_share_token = f"disabled_{uuid.uuid4().hex}"
    db.flush()
    run_b.public_share_token = tokens[0]
    db.commit()
    try:
        res_swap = client.get(f"/api/v1/public/comparisons/{tokens[0]}")
        assert res_swap.status_code == 403
    finally:
        run_b.public_share_token = run_b_orig_token
        db.flush()
        run_a.public_share_token = tokens[0]
        db.commit()


def test_sh2_bcrypt_utf8_byte_limit_and_uniform_lockout_429(client: TestClient):
    """S-H2: Contraseña >72 bytes UTF-8 (aunque <72 chars multibyte) da 422; lockout devuelve 429 uniforme."""
    res_73_ascii = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"sh2_a_{uuid.uuid4().hex[:6]}@obra.com.ar",
            "password": "a" * 73,
            "full_name": "Ing Largo",
        },
    )
    assert res_73_ascii.status_code == 422

    # 40 caracteres 'ñ' = 40 chars (<=72) pero 80 bytes UTF-8 (>72) -> debe fallar 422 sin truncar silenciosamente
    res_multibyte = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"sh2_mb_{uuid.uuid4().hex[:6]}@obra.com.ar",
            "password": "ñ" * 40,
            "full_name": "Ing Multibyte",
        },
    )
    assert res_multibyte.status_code == 422

    target_email = f"sh2_lock_{uuid.uuid4().hex[:6]}@obra.com.ar"
    _ = client.post(
        "/api/v1/auth/register",
        json={"email": target_email, "password": "PasswordSeguro2026!", "full_name": "Ing Lock"},
    )
    token = EmailService.get_outbox(target_email)[-1].verification_token
    assert client.post("/api/v1/auth/verify-email", json={"email": target_email, "token": token}).status_code == 200
    client.post("/api/v1/auth/logout")

    for _ in range(settings.AUTH_LOCKOUT_THRESHOLD):
        client.post("/api/v1/auth/login", json={"email": target_email, "password": "WrongPassword!"})

    res_locked = client.post("/api/v1/auth/login", json={"email": target_email, "password": "PasswordSeguro2026!"})
    assert res_locked.status_code == 429

    # Usuario inexistente también converge en 429 uniforme
    unknown_email = f"ghost_{uuid.uuid4().hex[:6]}@obra.com.ar"
    for _ in range(settings.AUTH_LOCKOUT_THRESHOLD):
        client.post("/api/v1/auth/login", json={"email": unknown_email, "password": "WrongPassword!"})
    res_unknown_locked = client.post("/api/v1/auth/login", json={"email": unknown_email, "password": "WrongPassword!"})
    assert res_unknown_locked.status_code == 429


def test_sh6_demo_role_isolated_in_cookie_and_excluded_from_traction(client: TestClient, db: Session):
    """S-H6 / E2E-05: PATCH /auth/role en Demo se aísla en cookie sin mutar BD compartida ni contaminar /traction."""
    before_traction = client.get("/api/v1/public/traction").json()

    demo_ws = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
    assert demo_ws is not None
    assert demo_ws.owner_role == "ESTIMATOR"

    res_demo = client.post("/api/v1/auth/demo-session")
    assert res_demo.status_code == 200
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf

    res_role = client.patch(
        "/api/v1/auth/role",
        json={"role": "BUYER"},
        headers={CSRF_HEADER_NAME: csrf},
    )
    assert res_role.status_code == 200
    assert res_role.json()["role"] == "BUYER"
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf

    res_me_1 = client.get("/api/v1/auth/me")
    assert res_me_1.status_code == 200
    assert res_me_1.json()["role"] == "BUYER"
    assert res_me_1.json()["is_demo"] is True

    db.refresh(demo_ws)
    assert demo_ws.owner_role == "ESTIMATOR"

    # Generar actividad dentro de la sesión Demo (ingesta de presupuesto)
    res_demo_req = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Demo Sin Tracción", "preset_id": "computo_tecnico"},
        headers={CSRF_HEADER_NAME: csrf},
    )
    assert res_demo_req.status_code == 201

    # Otra sesión anónima aislada conserva ESTIMATOR por defecto
    from app.main import app

    with TestClient(app) as client_2:
        res_me_2 = client_2.get("/api/v1/auth/me")
        assert res_me_2.status_code == 200
        assert res_me_2.json()["role"] == "ESTIMATOR"

    after_traction = client.get("/api/v1/public/traction").json()
    assert after_traction == before_traction


def test_deploy_option_a_files_and_profile_a1_direct_registration(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Opción A: Verifica vercel.json, backend/Dockerfile, render.yaml y registro directo sin SMTP en Perfil A1."""
    repo_root = Path(__file__).resolve().parents[2]
    assert (repo_root / "DEPLOY_SPEC_OPTION_A.md").exists()
    assert (repo_root / "render.yaml").exists()

    vercel_cfg = json.loads((repo_root / "frontend" / "vercel.json").read_text(encoding="utf-8"))
    rewrites = vercel_cfg.get("rewrites") or []
    sources = {r["source"]: r["destination"] for r in rewrites}
    assert "/api/v1/:path*" in sources and "/api/v1/:path*" in sources["/api/v1/:path*"]
    assert "/health" in sources and sources["/health"].endswith("/health")
    assert any(r.get("destination") == "/index.html" for r in rewrites)

    dockerfile_txt = (repo_root / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert "${PORT:-8000}" in dockerfile_txt

    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", False)
    email = f"deploy_a1_{uuid.uuid4().hex[:6]}@constructora.com.ar"
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "PasswordSeguro2026!",
            "full_name": "Ing. Perfil A1",
            "workspace_name": "Estudio Nube Jujuy",
            "role": "ESTIMATOR",
        },
    )
    assert res_reg.status_code == 201, res_reg.text
    reg_data = res_reg.json()
    assert reg_data["authenticated"] is True
    assert reg_data["email_verified"] is True
    assert reg_data["verification_required"] is False
    assert AUTH_COOKIE_NAME in client.cookies
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf

    res_me = client.get("/api/v1/auth/me")
    assert res_me.status_code == 200
    assert res_me.json()["is_demo"] is False
    assert res_me.json()["email"] == email

    res_vendor = client.post(
        "/api/v1/vendors",
        json={"name": "Corralón Nube A1", "locality": "San Salvador de Jujuy"},
        headers={CSRF_HEADER_NAME: csrf},
    )
    assert res_vendor.status_code == 201

