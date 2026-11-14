"""Pruebas de regresión y verificación empírica para los hallazgos H-37, H-38 y H-39."""

from decimal import Decimal
import hashlib
from pathlib import Path
import uuid

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError
import sqlalchemy as sa
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.models.comparison import ComparisonRun
from app.models.requisition import RequisitionItem
from app.models.vendor import PriceList, Vendor, VendorProduct
from app.services.email_service import EmailService

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]


def _valid_production_settings_kwargs() -> dict:
    return {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "postgresql+psycopg://app:Str0ngP@ss!2026@db:5432/compulsa",
        "REDIS_URL": "redis://redis:6379/0",
        "SECRET_KEY": "a-very-strong-production-jwt-secret-key-32chars",
        "HMAC_SHARE_SECRET": "b-another-strong-production-hmac-secret-32chars",
        "COOKIE_SECURE": True,
        "EMAIL_BACKEND": "smtp",
        "SMTP_HOST": "smtp.resend.com",
        "SMTP_PORT": 587,
        "SMTP_USE_TLS": True,
        "SMTP_FROM_EMAIL": "no-reply@compulsaobra.ar",
        "FRONTEND_PUBLIC_URL": "https://app.compulsaobra.ar",
    }


def _register_verified_session(client: TestClient, tag: str) -> dict:
    email = f"h39_{tag}_{uuid.uuid4().hex[:6]}@obra.com.ar"
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
    assert res.status_code == 201
    token = EmailService.get_outbox(email)[-1].verification_token
    res_ver = client.post("/api/v1/auth/verify-email", json={"email": email, "token": token})
    assert res_ver.status_code == 200
    data = res_ver.json()
    data["csrf_token"] = client.cookies.get(CSRF_COOKIE_NAME)
    return data


def _seed_cement_vendor(db: Session, workspace_id: uuid.UUID) -> tuple[Vendor, VendorProduct, VendorProduct]:
    vendor = Vendor(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        name="Corralon Exactitud H39",
        locality="San Salvador de Jujuy",
        is_public_directory=False,
        cash_discount_pct=Decimal("0.00"),
        estimate_delivery_fee_ars=Decimal("0.00"),
        acopio_config_json={"enabled": False},
    )
    db.add(vendor)
    db.flush()

    plist = PriceList(
        id=uuid.uuid4(),
        vendor_id=vendor.id,
        version_number=1,
        source_filename="h39_cement.csv",
        is_active=True,
    )
    db.add(plist)
    db.flush()

    desc_primary = "Cemento Portland Loma Negra 50 kg"
    prod_primary = VendorProduct(
        id=uuid.uuid4(),
        price_list_id=plist.id,
        vendor_id=vendor.id,
        sku="CEM-LN-50",
        raw_description=desc_primary,
        normalized_description=desc_primary.lower(),
        sale_unit="BOLSA",
        price_cash_ars=Decimal("10000.00"),
        price_list_ars=Decimal("10000.00"),
        stock_available=True,
        weight_kg=Decimal("50.00"),
        row_sha256=hashlib.sha256(f"CEM-LN-50||{desc_primary.lower()}".encode()).hexdigest(),
    )
    desc_alt = "Cemento Portland Avellaneda 50 kg"
    prod_alt = VendorProduct(
        id=uuid.uuid4(),
        price_list_id=plist.id,
        vendor_id=vendor.id,
        sku="CEM-AV-50",
        raw_description=desc_alt,
        normalized_description=desc_alt.lower(),
        sale_unit="BOLSA",
        price_cash_ars=Decimal("10500.00"),
        price_list_ars=Decimal("10500.00"),
        stock_available=True,
        weight_kg=Decimal("50.00"),
        row_sha256=hashlib.sha256(f"CEM-AV-50||{desc_alt.lower()}".encode()).hexdigest(),
    )
    db.add_all([prod_primary, prod_alt])
    db.commit()
    return vendor, prod_primary, prod_alt


def test_h37_h38_docker_compose_hardening_and_dev_override():
    """H-37 / H-38: docker-compose.yml base exige defaults seguros de producción y aísla Mailpit."""
    compose_prod = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    compose_dev = (REPO_ROOT / "docker-compose.dev.yml").read_text(encoding="utf-8")
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")

    # H-37: Cookie Secure activada por defecto en producción, solo deshabilitada en dev override
    assert "COOKIE_SECURE: ${COOKIE_SECURE:-true}" in compose_prod
    assert "COOKIE_SECURE:-false" not in compose_prod
    assert 'COOKIE_SECURE: "false"' in compose_dev

    # H-38: Mailpit restringido a perfiles dev/test en compose base y reactivado solo en compose.dev
    assert 'profiles: ["dev", "development", "test"]' in compose_prod
    assert "profiles: !reset []" in compose_dev

    # H-38: Cero fallbacks inseguros de desarrollo en backend de producción
    backend_section = compose_prod.split("\n  backend:")[1].split("\n  frontend:")[0]
    assert "${SMTP_HOST:-mailpit}" not in backend_section
    assert "${SMTP_PORT:-1025}" not in backend_section
    assert "compulsaobra.local" not in backend_section
    assert "${FRONTEND_PUBLIC_URL:-http://localhost:5173}" not in backend_section
    assert "${SMTP_HOST:?" in backend_section
    assert "${SMTP_FROM_EMAIL:?" in backend_section
    assert "${FRONTEND_PUBLIC_URL:?" in backend_section
    assert "SMTP_PORT: ${SMTP_PORT:-587}" in backend_section
    assert "SMTP_USE_TLS: ${SMTP_USE_TLS:-true}" in backend_section

    assert "# En producción es obligatorio true" in env_example
    assert "SMTP_PORT=587" in env_example
    assert "# COMPOSE_PROFILES=dev" in env_example
    assert "HTTPS pública" in env_example


@pytest.mark.parametrize(
    "override_kwargs",
    [
        {"COOKIE_SECURE": False},
        {"SMTP_HOST": "mailpit"},
        {"SMTP_HOST": "localhost"},
        {"SMTP_HOST": "127.0.0.1"},
        {"SMTP_HOST": "internal-relay"},
        {"SMTP_PORT": 1025},
        {"SMTP_FROM_EMAIL": "no-reply@compulsaobra.local"},
        {"SMTP_FROM_EMAIL": "no-reply@localhost"},
        {"SMTP_FROM_EMAIL": "not-an-email"},
        {"FRONTEND_PUBLIC_URL": "http://app.compulsaobra.ar"},
        {"FRONTEND_PUBLIC_URL": "https://localhost:5173"},
        {"FRONTEND_PUBLIC_URL": "https://app.compulsaobra.local"},
        {"ENVIRONMENT": "staging"},
    ],
)
def test_h37_h38_production_settings_reject_insecure_values(override_kwargs: dict):
    """H-37 / H-38: El arranque en production falla de inmediato ante cookies o correo/URL de dev."""
    kwargs = _valid_production_settings_kwargs()
    kwargs.update(override_kwargs)
    with pytest.raises(ValidationError):
        Settings(**kwargs)


def test_h37_h38_valid_production_and_dev_settings_succeed():
    """H-37 / H-38: Producción segura pasa validación; desarrollo conserva flujo local Mailpit."""
    prod = Settings(**_valid_production_settings_kwargs())
    assert prod.ENVIRONMENT == "production"
    assert prod.COOKIE_SECURE is True
    assert prod.SMTP_PORT == 587
    assert prod.FRONTEND_PUBLIC_URL == "https://app.compulsaobra.ar"

    dev = Settings(
        ENVIRONMENT="development",
        COOKIE_SECURE=False,
        EMAIL_BACKEND="smtp",
        SMTP_HOST="mailpit",
        SMTP_PORT=1025,
        SMTP_USE_TLS=False,
        SMTP_FROM_EMAIL="no-reply@compulsaobra.local",
        FRONTEND_PUBLIC_URL="http://localhost:5174",
    )
    assert dev.ENVIRONMENT == "development"
    assert dev.COOKIE_SECURE is False
    assert dev.SMTP_HOST == "mailpit"


def test_h39_quantity_and_unit_edits_invalidate_matrix_and_block_lock_409(
    client: TestClient,
    db: Session,
):
    """H-39: Cambiar cantidad o unidad versiona el requerimiento, invalida la matriz y exige recálculo (409)."""
    session = _register_verified_session(client, "qty")
    ws_id = uuid.UUID(session["workspace_id"])
    headers = {"X-Workspace-Id": str(ws_id), CSRF_HEADER_NAME: session["csrf_token"]}
    vendor, _, prod_alt = _seed_cement_vendor(db, ws_id)

    # 1. Crear requerimiento inicial: 50 bolsas @ $10.000 = $500.000
    res_req = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Losa H-39", "client_name": "Estudio Jujuy", "raw_text": "50 bolsas cemento portland loma negra 50 kg"},
        headers=headers,
    )
    assert res_req.status_code == 201
    req_data = res_req.json()
    req_id = req_data["id"]
    item_id = req_data["items"][0]["id"]
    assert req_data["version"] == 1
    assert req_data["version_hash"]

    # 2. Comparar versión 1 -> total esperado $500.000
    res_cmp1 = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={"vendor_ids": [str(vendor.id)], "payment_modality": "CASH", "include_delivery_fees": True},
        headers=headers,
    )
    assert res_cmp1.status_code == 200
    matrix1 = res_cmp1.json()
    run_id = matrix1["run_id"]
    match_id = matrix1["matrix_rows"][0]["vendor_cells"][0]["match_id"]
    assert matrix1["requisition_version"] == 1
    assert matrix1["requisition_version_hash"] == req_data["version_hash"]
    assert matrix1["is_stale"] is False
    assert matrix1["best_single_total_ars"] == pytest.approx(500000.0)

    # 3. Modificar cantidad de 50 a 80 bolsas -> incrementa versión e invalida la matriz existente
    res_edit_qty = client.patch(
        f"/api/v1/requisitions/{req_id}/items/{item_id}/resolve",
        json={"quantity": 80},
        headers=headers,
    )
    assert res_edit_qty.status_code == 200
    req_v2 = res_edit_qty.json()
    assert req_v2["version"] == 2
    assert req_v2["version_hash"] != req_data["version_hash"]
    assert req_v2["items"][0]["quantity"] == pytest.approx(80.0)

    # GET del run refleja explícitamente el estado obsoleto
    res_get_stale = client.get(f"/api/v1/comparisons/{run_id}", headers=headers)
    assert res_get_stale.status_code == 200
    stale_matrix = res_get_stale.json()
    assert stale_matrix["is_stale"] is True
    assert stale_matrix["status"] == "STALE"
    assert stale_matrix["stale_reason"]

    # Lock-budget y override manual sobre matriz obsoleta se rechazan con HTTP 409 Conflict
    res_lock_stale = client.post(
        f"/api/v1/comparisons/{run_id}/lock-budget",
        json={"accept_partial": False, "strategy": "SINGLE_VENDOR", "selected_single_vendor_id": str(vendor.id)},
        headers=headers,
    )
    assert res_lock_stale.status_code == 409

    res_override_stale = client.patch(
        f"/api/v1/comparisons/{run_id}/matches/{match_id}",
        json={"vendor_product_id": str(prod_alt.id), "override_reason": "Prueba obsoleta"},
        headers=headers,
    )
    assert res_override_stale.status_code == 409

    db.expire_all()
    run_obj = db.scalar(select(ComparisonRun).where(ComparisonRun.id == uuid.UUID(run_id)))
    assert run_obj is not None
    assert run_obj.is_locked is False
    assert run_obj.is_stale is True

    # 4. Recalcular comparativa para v2 -> total actualizado $800.000
    res_cmp2 = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={
            "vendor_ids": [str(vendor.id)],
            "payment_modality": "CASH",
            "include_delivery_fees": True,
            "existing_run_id": run_id,
        },
        headers=headers,
    )
    assert res_cmp2.status_code == 200
    matrix2 = res_cmp2.json()
    assert matrix2["is_stale"] is False
    assert matrix2["status"] == "COMPARED"
    assert matrix2["requisition_version"] == 2
    assert matrix2["requisition_version_hash"] == req_v2["version_hash"]
    assert matrix2["best_single_total_ars"] == pytest.approx(800000.0)

    # 5. Cambiar unidad también invalida la matriz y bloquea lock-budget con 409
    res_edit_unit = client.patch(
        f"/api/v1/requisitions/{req_id}/items/{item_id}/resolve",
        json={"requested_unit": "UN"},
        headers=headers,
    )
    assert res_edit_unit.status_code == 200
    assert res_edit_unit.json()["version"] == 3

    res_lock_unit_stale = client.post(
        f"/api/v1/comparisons/{run_id}/lock-budget",
        json={"accept_partial": False, "strategy": "SINGLE_VENDOR", "selected_single_vendor_id": str(vendor.id)},
        headers=headers,
    )
    assert res_lock_unit_stale.status_code == 409

    # Restaurar unidad BOLSA -> recalcular -> verificación defensiva ante desfase directo en DB -> recalcular -> bloquear
    res_restore_unit = client.patch(
        f"/api/v1/requisitions/{req_id}/items/{item_id}/resolve",
        json={"requested_unit": "BOLSA"},
        headers=headers,
    )
    assert res_restore_unit.status_code == 200
    assert res_restore_unit.json()["version"] == 4

    res_cmp3 = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={
            "vendor_ids": [str(vendor.id)],
            "payment_modality": "CASH",
            "include_delivery_fees": True,
            "existing_run_id": run_id,
        },
        headers=headers,
    )
    assert res_cmp3.status_code == 200
    assert res_cmp3.json()["best_single_total_ars"] == pytest.approx(800000.0)

    # Chequeo defensivo: si el ítem cambiara en DB sin pasar por /resolve, lock-budget igual detecta divergencia (409)
    item_db = db.scalar(select(RequisitionItem).where(RequisitionItem.id == uuid.UUID(item_id)))
    assert item_db is not None
    item_db.quantity = Decimal("95.00")
    db.commit()
    res_lock_db_drift = client.post(
        f"/api/v1/comparisons/{run_id}/lock-budget",
        json={"accept_partial": False, "strategy": "SINGLE_VENDOR", "selected_single_vendor_id": str(vendor.id)},
        headers=headers,
    )
    assert res_lock_db_drift.status_code == 409

    # Restaurar cantidad a 80 y ejecutar recálculo fresco antes de congelar definitivamente
    item_db.quantity = Decimal("80.00")
    db.commit()
    res_cmp4 = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={
            "vendor_ids": [str(vendor.id)],
            "payment_modality": "CASH",
            "include_delivery_fees": True,
            "existing_run_id": run_id,
        },
        headers=headers,
    )
    assert res_cmp4.status_code == 200
    assert res_cmp4.json()["best_single_total_ars"] == pytest.approx(800000.0)

    res_lock_ok = client.post(
        f"/api/v1/comparisons/{run_id}/lock-budget",
        json={"accept_partial": False, "strategy": "SINGLE_VENDOR", "selected_single_vendor_id": str(vendor.id)},
        headers=headers,
    )
    assert res_lock_ok.status_code == 200
    locked_data = res_lock_ok.json()
    assert locked_data["status"] == "LOCKED_BUDGET"
    share_token = locked_data["public_share_token"]

    res_locked_get = client.get(f"/api/v1/comparisons/{run_id}", headers=headers)
    assert res_locked_get.status_code == 200
    assert res_locked_get.json()["is_locked"] is True
    assert res_locked_get.json()["is_stale"] is False
    assert res_locked_get.json()["best_single_total_ars"] == pytest.approx(800000.0)

    res_public = client.get(f"/api/v1/public/comparisons/{share_token}")
    assert res_public.status_code == 200
    pub = res_public.json()
    assert pub["signature_verified"] is True
    assert pub["is_simulation"] is False
    assert pub["status"] == "LOCKED_BUDGET"
    assert pub["grand_total_ars"] == pytest.approx(800000.0)


def test_h39_alembic_0004_upgrade_downgrade_sqlite_roundtrip(tmp_path: Path):
    """H-39: Verifica la migración 0004_audit_h37_h39 (upgrade -> downgrade -> upgrade) en SQLite."""
    db_file = tmp_path / "alembic_h39_roundtrip.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(alembic_cfg, "head")
    engine_up = create_engine(db_url)
    try:
        insp = sa.inspect(engine_up)
        assert "version" in {c["name"] for c in insp.get_columns("requisitions")}
        assert {"requisition_version", "requisition_version_hash", "is_stale"}.issubset(
            {c["name"] for c in insp.get_columns("comparison_runs")}
        )
    finally:
        engine_up.dispose()

    command.downgrade(alembic_cfg, "0003_audit_h27_h36")
    engine_down = create_engine(db_url)
    try:
        insp_down = sa.inspect(engine_down)
        assert "version" not in {c["name"] for c in insp_down.get_columns("requisitions")}
        assert "is_stale" not in {c["name"] for c in insp_down.get_columns("comparison_runs")}
    finally:
        engine_down.dispose()

    command.upgrade(alembic_cfg, "head")
    engine_reup = create_engine(db_url)
    try:
        insp_reup = sa.inspect(engine_reup)
        assert "version" in {c["name"] for c in insp_reup.get_columns("requisitions")}
        assert {"requisition_version", "requisition_version_hash", "is_stale"}.issubset(
            {c["name"] for c in insp_reup.get_columns("comparison_runs")}
        )
    finally:
        engine_reup.dispose()
