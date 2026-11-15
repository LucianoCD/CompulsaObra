"""Pruebas exhaustivas para los hallazgos pendientes y nuevos (H-02, H-04, H-21, H-22, H-23, H-27 a H-34)."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import email as email_stdlib
from email import policy as email_policy
from pathlib import Path
import re
import socket
import threading
import uuid
import zlib

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError
import sqlalchemy as sa
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, settings
from app.core.database import Base
from app.core.security import (
    AUTH_COOKIE_NAME,
    AuthRateLimiter,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    create_access_token,
)
from app.models.comparison import ComparisonRun
from app.models.requisition import Requisition
from app.models.telemetry import TractionEvent
from app.models.vendor import PriceList, Vendor, VendorProduct
from app.models.workspace import User
from app.services.email_service import EmailService, hash_verification_token


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extrae texto legible de flujos FlateDecode y streams planos PDF (sin deps externas)."""
    chunks: list[bytes] = [pdf_bytes]
    for raw_stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, flags=re.S):
        try:
            chunks.append(zlib.decompress(raw_stream))
        except zlib.error:
            chunks.append(raw_stream)
    return b"\n".join(chunks).decode("latin-1", errors="ignore")


class _MockSMTPServer:
    """Servidor SMTP TCP minimalista en memoria usando stdlib asyncio para validar H-29 real."""

    def __init__(self) -> None:
        self.messages: list[str] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: asyncio.AbstractServer | None = None
        self._thread: threading.Thread | None = None
        self.port: int = 0
        self._ready = threading.Event()

    def start(self) -> int:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)
        return self.port

    def stop(self) -> None:
        if self._loop and self._loop.is_running():
            if self._server:
                self._loop.call_soon_threadsafe(self._server.close)
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            writer.write(b"220 localhost MockSMTP\r\n")
            await writer.drain()
            in_data = False
            data_lines: list[bytes] = []
            while True:
                line = await reader.readline()
                if not line:
                    break
                if in_data:
                    if line in (b".\r\n", b".\n"):
                        in_data = False
                        self.messages.append(b"".join(data_lines).decode("utf-8", errors="replace"))
                        data_lines.clear()
                        writer.write(b"250 OK queued\r\n")
                        await writer.drain()
                    else:
                        data_lines.append(line)
                    continue

                upper = line.decode("utf-8", errors="ignore").strip().upper()
                if upper.startswith("EHLO") or upper.startswith("HELO"):
                    writer.write(b"250-localhost\r\n250 SIZE 10485760\r\n")
                elif upper.startswith("MAIL FROM") or upper.startswith("RCPT TO"):
                    writer.write(b"250 OK\r\n")
                elif upper == "DATA":
                    in_data = True
                    writer.write(b"354 End data with <CR><LF>.<CR><LF>\r\n")
                elif upper == "QUIT":
                    writer.write(b"221 Bye\r\n")
                    await writer.drain()
                    break
                else:
                    writer.write(b"250 OK\r\n")
                await writer.drain()
            writer.close()

        async def bootstrap():
            self._server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
            sock = self._server.sockets[0]
            self.port = sock.getsockname()[1]
            self._ready.set()

        self._loop.run_until_complete(bootstrap())
        self._loop.run_forever()


def _create_verified_cookie_user(client: TestClient, suffix: str) -> dict:
    email = f"audit_{suffix}_{uuid.uuid4().hex[:6]}@obra.com.ar"
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "PasswordSeguro2026!",
            "full_name": f"Ing. {suffix}",
            "workspace_name": f"Estudio {suffix}",
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


def _add_real_vendor(
    db: Session,
    workspace_id: uuid.UUID,
    name: str,
    delivery_fee: str,
    cement_price: str,
) -> Vendor:
    v = Vendor(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        name=name,
        locality="San Salvador de Jujuy",
        is_public_directory=False,
        cash_discount_pct=Decimal("0.00"),
        estimate_delivery_fee_ars=Decimal(delivery_fee),
        acopio_config_json={"enabled": False},
    )
    db.add(v)
    db.flush()
    pl = PriceList(id=uuid.uuid4(), vendor_id=v.id, source_filename="lista.csv", is_active=True)
    db.add(pl)
    db.flush()
    db.add(
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl.id,
            vendor_id=v.id,
            sku=f"SKU-{name[:4].upper()}",
            raw_description="Cemento Portland 50 kg",
            normalized_description="cemento portland 50 kg",
            sale_unit="BOLSA",
            price_cash_ars=Decimal(cement_price),
            price_list_ars=Decimal(cement_price),
            weight_kg=Decimal("50.00"),
            material_type="Cemento",
            row_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
            stock_available=True,
        )
    )
    db.commit()
    return v


def test_h02_h31_immutable_strategy_and_simulation_vs_issued_pdf(client: TestClient, db: Session):
    """H-02 / H-31: Simulación PDF rotulada distinta al emitido y bloqueo de alteraciones de estrategia al congelar."""
    session = _create_verified_cookie_user(client, "h31")
    ws_id = uuid.UUID(session["workspace_id"])
    headers = {"X-Workspace-Id": str(ws_id), CSRF_HEADER_NAME: session["csrf_token"]}

    v1 = _add_real_vendor(db, ws_id, "Corralon Uno", "1000.00", "9000.00")
    v2 = _add_real_vendor(db, ws_id, "Corralon Dos", "500.00", "9500.00")

    res_in = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Edificio Norte", "client_name": "Arq. Salvatierra", "raw_text": "2 bolsas cemento 50 kg"},
        headers=headers,
    )
    assert res_in.status_code == 201
    req_id = res_in.json()["id"]

    res_cmp = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={
            "vendor_ids": [str(v1.id), str(v2.id)],
            "payment_modality": "CASH",
            "markup_pct": 10.0,
            "budget_strategy": "SPLIT_CART",
        },
        headers=headers,
    )
    assert res_cmp.status_code == 200
    run_id = res_cmp.json()["run_id"]

    # 1. PDF ANTES de bloquear: marcado explícitamente como SIMULACION / BORRADOR (H-31)
    sim_pdf = client.get(
        f"/api/v1/comparisons/{run_id}/pdf?mode=client_budget&strategy=SINGLE_VENDOR&single_vendor_id={v2.id}",
        headers={"X-Workspace-Id": str(ws_id)},
    )
    assert sim_pdf.status_code == 200
    sim_text = _extract_pdf_text(sim_pdf.content)
    assert "SIMULACION" in sim_text
    assert "BORRADOR" in sim_text
    assert "PRESUPUESTO DEFINITIVO EMITIDO" not in sim_text

    # 2. Congelar eligiendo SINGLE_VENDOR = v2
    lock_res = client.post(
        f"/api/v1/comparisons/{run_id}/lock-budget",
        json={"strategy": "SINGLE_VENDOR", "selected_single_vendor_id": str(v2.id)},
        headers=headers,
    )
    assert lock_res.status_code == 200
    share_token = lock_res.json()["public_share_token"]

    # 3. Reintentar lock-budget cambiando a SPLIT_CART -> 409
    relock_diff = client.post(
        f"/api/v1/comparisons/{run_id}/lock-budget",
        json={"strategy": "SPLIT_CART"},
        headers=headers,
    )
    assert relock_diff.status_code == 409

    # 4. Intentar descargar PDF privado cambiando estrategia -> 409
    bad_pdf = client.get(
        f"/api/v1/comparisons/{run_id}/pdf?mode=client_budget&strategy=SPLIT_CART",
        headers={"X-Workspace-Id": str(ws_id)},
    )
    assert bad_pdf.status_code == 409

    # 5. Descargar PDF emitido definitivo -> contiene rótulo emitido y NO borrador
    issued_pdf = client.get(
        f"/api/v1/comparisons/{run_id}/pdf?mode=client_budget",
        headers={"X-Workspace-Id": str(ws_id)},
    )
    assert issued_pdf.status_code == 200
    issued_text = _extract_pdf_text(issued_pdf.content)
    assert "PRESUPUESTO DEFINITIVO EMITIDO" in issued_text
    assert "SIMULACION / BORRADOR" not in issued_text

    # 6. Endpoint público rechaza ?strategy=... (400) y ?mode=comparison (403)
    assert client.get(f"/api/v1/public/comparisons/{share_token}?strategy=SPLIT_CART").status_code == 400
    assert client.get(f"/api/v1/public/comparisons/{share_token}?mode=comparison").status_code == 403
    assert client.get(f"/api/v1/public/comparisons/{share_token}").status_code == 200


def test_h04_h32_full_metadata_snapshot_hmac_protection(client: TestClient, db: Session):
    """H-04 / H-32: Snapshot firmado protege title, client_name, locked_at y montos incluso si muta Requisition."""
    session = _create_verified_cookie_user(client, "h32")
    ws_id = uuid.UUID(session["workspace_id"])
    headers = {"X-Workspace-Id": str(ws_id), CSRF_HEADER_NAME: session["csrf_token"]}

    vendor = _add_real_vendor(db, ws_id, "Corralon HMAC", "1000.00", "8000.00")
    res_in = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Título Original Inmutable", "client_name": "Cliente Original", "raw_text": "1 bolsa cemento 50 kg"},
        headers=headers,
    )
    req_id = res_in.json()["id"]

    res_cmp = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={"vendor_ids": [str(vendor.id)], "payment_modality": "CASH"},
        headers=headers,
    )
    run_id = res_cmp.json()["run_id"]
    lock_res = client.post(
        f"/api/v1/comparisons/{run_id}/lock-budget",
        json={"strategy": "SINGLE_VENDOR", "selected_single_vendor_id": str(vendor.id)},
        headers=headers,
    )
    token = lock_res.json()["public_share_token"]

    # Mutar título y cliente en Requisition: vista pública debe preservar valores congelados del snapshot
    req_obj = db.scalar(select(Requisition).where(Requisition.id == uuid.UUID(req_id)))
    assert req_obj is not None
    req_obj.title = "Título Modificado Posterior"
    req_obj.client_name = "Otro Comitente"
    db.commit()

    pub_ok = client.get(f"/api/v1/public/comparisons/{token}")
    assert pub_ok.status_code == 200
    assert pub_ok.json()["title"] == "Título Original Inmutable"
    assert pub_ok.json()["client_name"] == "Cliente Original"

    # Adulterar metadatos dentro de comparison_matrix_json o locked_snapshot_hash -> 403
    run_obj = db.scalar(select(ComparisonRun).where(ComparisonRun.id == uuid.UUID(run_id)))
    assert run_obj is not None
    original_matrix = dict(run_obj.comparison_matrix_json)

    for key, tampered_val in [
        ("title", "Adulterado"),
        ("client_name", "Adulterado"),
        ("locked_at", "2020-01-01T00:00:00+00:00"),
    ]:
        mutated = dict(original_matrix)
        mutated[key] = tampered_val
        run_obj.comparison_matrix_json = mutated
        db.commit()
        assert client.get(f"/api/v1/public/comparisons/{token}").status_code == 403

    run_obj.comparison_matrix_json = original_matrix
    run_obj.locked_strategy = "SPLIT_CART"
    db.commit()
    assert client.get(f"/api/v1/public/comparisons/{token}").status_code == 403


def test_h21_h33_cookie_only_and_csrf_double_submit_protection(client: TestClient):
    """H-21 / H-33: Sin access_token en respuestas JSON; mutaciones cookie exigen X-CSRF-Token."""
    session = _create_verified_cookie_user(client, "h33")
    assert "access_token" not in session
    assert AUTH_COOKIE_NAME in client.cookies
    assert CSRF_COOKIE_NAME in client.cookies

    # Mutación privada por cookie SIN cabecera X-CSRF-Token -> 403
    no_csrf = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Sin CSRF", "raw_text": "2 bolsas cemento"},
        headers={"X-Workspace-Id": session["workspace_id"]},
    )
    assert no_csrf.status_code == 403

    # Con cabecera X-CSRF-Token incorrecta -> 403
    bad_csrf = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "CSRF Malo", "raw_text": "2 bolsas cemento"},
        headers={"X-Workspace-Id": session["workspace_id"], CSRF_HEADER_NAME: "valor-invalido"},
    )
    assert bad_csrf.status_code == 403

    # Con cabecera X-CSRF-Token válida -> 201
    ok_csrf = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "CSRF OK", "raw_text": "2 bolsas cemento"},
        headers={
            "X-Workspace-Id": session["workspace_id"],
            CSRF_HEADER_NAME: session["csrf_token"],
        },
    )
    assert ok_csrf.status_code == 201

    # /auth/me confirma sesión válida sin token JWT en payload
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert "access_token" not in me_res.json()


def test_h22_h28_h29_email_verification_gate_expiry_resend_and_smtp_delivery(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    """H-22 / H-28 / H-29: Token hasheado, bloqueo de JWT previo a verificar, expiración, resend y envío SMTP real."""
    smtp_srv = _MockSMTPServer()
    port = smtp_srv.start()
    try:
        monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
        monkeypatch.setattr(settings, "EMAIL_BACKEND", "smtp")
        monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
        monkeypatch.setattr(settings, "SMTP_PORT", port)
        monkeypatch.setattr(settings, "SMTP_USE_TLS", False)
        monkeypatch.setattr(settings, "SMTP_USE_SSL", False)
        monkeypatch.setattr(settings, "EMAIL_RESEND_COOLDOWN_SECONDS", 60)

        email = f"smtp_{uuid.uuid4().hex[:6]}@constructora.com.ar"
        res_reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "PasswordSeguro2026!",
                "full_name": "Ing. SMTP",
                "workspace_name": "Empresa SMTP",
            },
        )
        assert res_reg.status_code == 201
        reg_json = res_reg.json()
        assert reg_json["authenticated"] is False
        assert AUTH_COOKIE_NAME not in res_reg.cookies
        assert len(smtp_srv.messages) == 1
        assert "/verificar-correo" in smtp_srv.messages[0]

        # Extraer token del cuerpo MIME enviado por SMTP y confirmar ausencia de cabecera X-Compulsa-Token
        parsed_msg_1 = email_stdlib.message_from_string(smtp_srv.messages[0], policy=email_policy.default)
        assert "X-Compulsa-Token" not in parsed_msg_1
        match = re.search(r"Código de verificación manual:\s*([^\r\n]+)", str(parsed_msg_1.get_content()))
        assert match is not None
        first_token = match.group(1).strip()

        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        assert user.email_verified is False
        assert user.verification_token_hash == hash_verification_token(first_token)

        # Even if alguien fabricara un JWT para ese usuario antes de verificar -> deps bloquea con 403 (H-28)
        forged_unverified_jwt = create_access_token(
            {
                "sub": user.email,
                "user_id": str(user.id),
                "workspace_id": str(user.workspace_id),
                "role": user.role,
                "is_demo": False,
            }
        )
        res_blocked_api = client.get(
            "/api/v1/requisitions",
            headers={"Authorization": f"Bearer {forged_unverified_jwt}"},
        )
        assert res_blocked_api.status_code == 403

        # Resend inmediato dentro del cooldown -> 429
        res_cooldown = client.post("/api/v1/auth/resend-verification", json={"email": email})
        assert res_cooldown.status_code == 429

        # Avanzar tiempo simulando paso del cooldown y reenviar -> nuevo token invalida el anterior
        user.verification_sent_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        db.commit()
        res_resend = client.post("/api/v1/auth/resend-verification", json={"email": email})
        assert res_resend.status_code == 200
        assert len(smtp_srv.messages) == 2

        parsed_msg_2 = email_stdlib.message_from_string(smtp_srv.messages[1], policy=email_policy.default)
        assert "X-Compulsa-Token" not in parsed_msg_2
        match2 = re.search(r"Código de verificación manual:\s*([^\r\n]+)", str(parsed_msg_2.get_content()))
        assert match2 is not None
        second_token = match2.group(1).strip()
        assert second_token != first_token

        # Token anterior ya no sirve
        assert (
            client.post("/api/v1/auth/verify-email", json={"email": email, "token": first_token}).status_code
            == 400
        )

        # Token expirado falla con 400
        user.verification_token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        assert (
            client.post("/api/v1/auth/verify-email", json={"email": email, "token": second_token}).status_code
            == 400
        )

        # Restaurar expiración -> verify-email exitoso y otorga sesión cookie
        user.verification_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.commit()
        res_ok = client.post("/api/v1/auth/verify-email", json={"email": email, "token": second_token})
        assert res_ok.status_code == 200
        assert AUTH_COOKIE_NAME in res_ok.cookies
        assert res_ok.json()["authenticated"] is True
    finally:
        smtp_srv.stop()

    # Si SMTP cae en registro -> 503 y rollback limpio sin usuario huérfano
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    dead_port = sock.getsockname()[1]
    sock.close()
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "smtp")
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_PORT", dead_port)
    fail_email = f"fail_{uuid.uuid4().hex[:6]}@constructora.com.ar"
    res_fail = client.post(
        "/api/v1/auth/register",
        json={
            "email": fail_email,
            "password": "PasswordSeguro2026!",
            "full_name": "Sin SMTP",
        },
    )
    assert res_fail.status_code == 503
    assert db.scalar(select(User).where(User.email == fail_email)) is None


def test_h18_production_requires_smtp_and_redis(monkeypatch: pytest.MonkeyPatch):
    """H-18 / H-29 / H-34: Entorno production rechaza configuración sin SMTP o sin Redis."""
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+psycopg://app:Str0ngP@ss!2026@db:5432/compulsa",
            SECRET_KEY="a-very-strong-production-jwt-secret-key-32chars",
            HMAC_SHARE_SECRET="b-another-strong-production-hmac-secret-32chars",
            EMAIL_BACKEND="memory",
            REDIS_URL="redis://redis:6379/0",
        )

    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+psycopg://app:Str0ngP@ss!2026@db:5432/compulsa",
            SECRET_KEY="a-very-strong-production-jwt-secret-key-32chars",
            HMAC_SHARE_SECRET="b-another-strong-production-hmac-secret-32chars",
            EMAIL_BACKEND="smtp",
            SMTP_HOST="smtp.resend.com",
            SMTP_FROM_EMAIL="no-reply@compulsa.ar",
            REDIS_URL="",
        )


def test_h23_h30_traction_ignores_preliminary_runs_and_measures_locked_at(client: TestClient, db: Session):
    """H-23 / H-30: /traccion ignora preliminares sin lock, mide (locked_at - req.created_at) y eventos reales."""
    before = client.get("/api/v1/public/traction").json()

    # Registrar un segundo usuario SIN verificar -> no altera métricas
    unverified_email = f"nover_{uuid.uuid4().hex[:6]}@obra.com.ar"
    client.post(
        "/api/v1/auth/register",
        json={"email": unverified_email, "password": "PasswordSeguro2026!", "full_name": "Sin Verificar"},
    )
    after_unverified = client.get("/api/v1/public/traction").json()
    assert after_unverified["active_real_workspaces"] == before["active_real_workspaces"]
    assert after_unverified["active_real_users"] == before["active_real_users"]

    # Usuario real verificado pero sin requisiciones aún -> tampoco infla workspaces activos
    session = _create_verified_cookie_user(client, "h30")
    after_empty_verified = client.get("/api/v1/public/traction").json()
    assert after_empty_verified["active_real_workspaces"] == before["active_real_workspaces"]

    ws_id = uuid.UUID(session["workspace_id"])
    headers = {"X-Workspace-Id": str(ws_id), CSRF_HEADER_NAME: session["csrf_token"]}
    vendor = _add_real_vendor(db, ws_id, "Corralon Medicion", "400.00", "7500.00")

    res_in = client.post(
        "/api/v1/requisitions/ingest-json",
        json={"title": "Obra Medida H30", "raw_text": "3 bolsas cemento 50 kg"},
        headers=headers,
    )
    assert res_in.status_code == 201
    req_id = res_in.json()["id"]

    # Retrotraer creación de la requisición 200 segundos para validar cálculo exacto (locked_at - created_at)
    req_obj = db.scalar(select(Requisition).where(Requisition.id == uuid.UUID(req_id)))
    assert req_obj is not None
    req_obj.created_at = datetime.now(timezone.utc) - timedelta(seconds=200)
    db.commit()

    # Ejecutar 2 corridas preliminares: solo bloquearemos la 2da
    res_c1 = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={"vendor_ids": [str(vendor.id)], "payment_modality": "CASH"},
        headers=headers,
    )
    res_c2 = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={"vendor_ids": [str(vendor.id)], "payment_modality": "LIST"},
        headers=headers,
    )
    assert res_c1.status_code == 200 and res_c2.status_code == 200
    run_id_2 = res_c2.json()["run_id"]

    res_lock = client.post(f"/api/v1/comparisons/{run_id_2}/lock-budget", headers=headers)
    assert res_lock.status_code == 200

    after = client.get("/api/v1/public/traction").json()
    assert after["active_real_workspaces"] == before["active_real_workspaces"] + 1
    assert after["active_real_users"] == before["active_real_users"] + 1
    assert after["real_budgets_generated"] == before["real_budgets_generated"] + 1
    assert after["real_vendors_compared"] >= before["real_vendors_compared"] + 1
    assert after["total_lines_processed"] == before["total_lines_processed"] + 1
    assert after["verified_usage_events"] > before["verified_usage_events"]
    assert after["median_elaboration_seconds"] > 0

    events_count = db.scalar(
        sa.select(sa.func.count(TractionEvent.id)).where(TractionEvent.workspace_id == ws_id)
    )
    assert (events_count or 0) >= 4  # USER_REGISTERED, USER_EMAIL_VERIFIED, REQUISITION_CREATED, COMPARISON_EXECUTED x2, BUDGET_LOCKED


def test_h27_nginx_reverse_proxy_and_compose_healthcheck():
    """H-19 / H-27: Nginx proxya /api/v1/ hacia backend:8000 y compose incluye redis + healthcheck."""
    repo_root = Path(__file__).resolve().parents[2]
    nginx_conf = (repo_root / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    compose_yml = (repo_root / "docker-compose.yml").read_text(encoding="utf-8")

    assert "location /api/v1/" in nginx_conf
    assert "proxy_pass http://backend:8000/api/v1/;" in nginx_conf
    assert "client_max_body_size" in nginx_conf
    assert "redis:" in compose_yml
    assert "healthcheck:" in compose_yml


def test_h34_shared_rate_limiter_persists_across_instances(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """H-34: Contadores de rate limit y lockout persisten en almacenamiento compartido entre instancias."""
    monkeypatch.setattr(settings, "REDIS_URL", "")
    db_file = tmp_path / "shared_limiter.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    WorkerSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    limiter_1 = AuthRateLimiter()
    limiter_2 = AuthRateLimiter()

    with WorkerSession() as s1, WorkerSession() as s2:
        for _ in range(settings.AUTH_LOCKOUT_THRESHOLD - 1):
            limiter_1.record_failed_attempt("multiworker@obra.com.ar", db=s1)
        limiter_2.record_failed_attempt("multiworker@obra.com.ar", db=s2)

    # Instancia completamente nueva lee el bloqueo persistido en la BD compartida
    limiter_3 = AuthRateLimiter()
    with WorkerSession() as s3:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            limiter_3.ensure_not_locked("multiworker@obra.com.ar", db=s3)
        assert exc_info.value.status_code == 429

        for _ in range(3):
            limiter_1.check_rate_limit("ip:shared", max_requests=3, window_seconds=60, db=s3)
        with pytest.raises(HTTPException) as rl_exc:
            limiter_2.check_rate_limit("ip:shared", max_requests=3, window_seconds=60, db=s3)
        assert rl_exc.value.status_code == 429
