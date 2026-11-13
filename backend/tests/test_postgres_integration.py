"""Pruebas de integración reales contra PostgreSQL 16 + Alembic + pg_trgm + Redis (H-36)."""

import os
from pathlib import Path
import uuid

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import normalize_postgres_url
from app.core.database import get_db
from app.core.security import AuthRateLimiter, CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.main import app
from app.services.email_service import EmailService
from app.services.seed import seed_demo_data_if_needed

TEST_POSTGRES_URL = normalize_postgres_url(os.getenv("TEST_POSTGRES_URL", ""))

pytestmark = pytest.mark.skipif(
    not TEST_POSTGRES_URL,
    reason="Defina TEST_POSTGRES_URL para ejecutar la suite de integración PostgreSQL 16.",
)


def test_postgres_16_alembic_migrations_and_end_to_end_flow():
    """H-36: Ejecuta migraciones Alembic desde 0 en PostgreSQL 16, extensions, matching pg_trgm y lock-budget."""
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_POSTGRES_URL)

    engine = create_engine(TEST_POSTGRES_URL, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent;"))

    # Aplicar migración completa hasta head (incluyendo 0003) y verificar downgrade/upgrade en Postgres 16
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "0002_audit_h01_h26")
    command.upgrade(alembic_cfg, "head")

    PgSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with PgSession() as session:
        seed_demo_data_if_needed(session)

    def override_get_db():
        s = PgSession()
        try:
            yield s
        finally:
            s.close()

    EmailService.clear_outbox()
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            email = f"pg16_{uuid.uuid4().hex[:8]}@obra.com.ar"
            res_reg = client.post(
                "/api/v1/auth/register",
                json={
                    "email": email,
                    "password": "PostgresPassword2026!",
                    "full_name": "Ing. Postgres",
                    "workspace_name": "Obra PG16",
                },
            )
            assert res_reg.status_code == 201
            token = EmailService.get_outbox(email)[-1].verification_token

            res_ver = client.post("/api/v1/auth/verify-email", json={"email": email, "token": token})
            assert res_ver.status_code == 200
            csrf = client.cookies.get(CSRF_COOKIE_NAME)
            ws_id = res_ver.json()["workspace_id"]
            headers = {"X-Workspace-Id": ws_id, CSRF_HEADER_NAME: csrf or ""}

            # Subir comercio real + catálogo para ejercitar Postgres matching y /traccion real
            res_v = client.post(
                "/api/v1/vendors",
                json={"name": "Corralón PG16", "locality": "San Salvador de Jujuy", "estimate_delivery_fee_ars": 1500},
                headers=headers,
            )
            assert res_v.status_code == 201
            vendor_id = res_v.json()["id"]

            csv_bytes = (
                "SKU,DESCRIPCION,PRECIO_CONTADO,UNIDAD\n"
                "PG-CEM,Cemento Portland Loma Negra 50 kg,10500,BOLSA\n"
                "PG-HIERRO,Barra Hierro Aletado 8 mm x 12 m,9800,BARRA\n"
            ).encode("utf-8")
            res_imp = client.post(
                f"/api/v1/vendors/{vendor_id}/catalogs/import",
                files={"file": ("catalogo.csv", csv_bytes, "text/csv")},
                data={
                    "mapping_json": '{"sku_col":"SKU","desc_col":"DESCRIPCION","price_cash_col":"PRECIO_CONTADO","unit_col":"UNIDAD"}'
                },
                headers=headers,
            )
            assert res_imp.status_code == 200

            res_ing = client.post(
                "/api/v1/requisitions/ingest-json",
                json={"title": "Cimentación PG16", "raw_text": "10 bolsas cemento 50 kg y 5 barras del 8"},
                headers=headers,
            )
            assert res_ing.status_code == 201
            req_id = res_ing.json()["id"]

            res_cmp = client.post(
                f"/api/v1/requisitions/{req_id}/compare",
                json={"vendor_ids": [vendor_id], "payment_modality": "CASH", "markup_pct": 12.0},
                headers=headers,
            )
            assert res_cmp.status_code == 200
            run_id = res_cmp.json()["run_id"]

            res_lock = client.post(
                f"/api/v1/comparisons/{run_id}/lock-budget",
                json={"strategy": "SINGLE_VENDOR", "selected_single_vendor_id": vendor_id},
                headers=headers,
            )
            assert res_lock.status_code == 200
            share_token = res_lock.json()["public_share_token"]

            res_pub = client.get(f"/api/v1/public/comparisons/{share_token}")
            assert res_pub.status_code == 200
            assert res_pub.json()["signature_verified"] is True

            res_traction = client.get("/api/v1/public/traction")
            assert res_traction.status_code == 200
            assert res_traction.json()["real_budgets_generated"] >= 1

        # Verificar Rate Limiter compartido con Postgres / Redis (SELECT ... FOR UPDATE)
        rl_a = AuthRateLimiter()
        rl_b = AuthRateLimiter()
        with PgSession() as s_rl:
            rl_key = f"pg_rl_{uuid.uuid4().hex[:6]}"
            rl_a.check_rate_limit(rl_key, max_requests=2, window_seconds=60, db=s_rl)
            rl_b.check_rate_limit(rl_key, max_requests=2, window_seconds=60, db=s_rl)
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc:
                rl_a.check_rate_limit(rl_key, max_requests=2, window_seconds=60, db=s_rl)
            assert exc.value.status_code == 429

        with engine.connect() as conn:
            tables = sa.inspect(conn).get_table_names()
            assert "traction_events" in tables
            assert "auth_security_counters" in tables
    finally:
        app.dependency_overrides.clear()
        EmailService.clear_outbox()
        engine.dispose()
