"""Pruebas de seguridad, cookies HttpOnly, CSRF, aislamiento multitenant y autenticación (SEC-01, CO-01, H-21, H-28, H-33)."""

import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import AUTH_COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.models.workspace import Workspace
from app.models.vendor import Vendor
from app.services.email_service import EmailService


def _register_and_verify_cookie_session(
    client: TestClient,
    email: str,
    password: str,
    full_name: str,
    workspace_name: str,
    role: str = "ESTIMATOR",
) -> dict:
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "workspace_name": workspace_name,
            "role": role,
        },
    )
    assert res_reg.status_code == 201
    reg_json = res_reg.json()
    assert reg_json["authenticated"] is False
    assert "access_token" not in reg_json
    assert AUTH_COOKIE_NAME not in res_reg.cookies

    outbox = EmailService.get_outbox(email)
    assert len(outbox) >= 1
    ver_token = outbox[-1].verification_token

    res_ver = client.post(
        "/api/v1/auth/verify-email",
        json={"email": email, "token": ver_token},
    )
    assert res_ver.status_code == 200
    ver_json = res_ver.json()
    assert ver_json["authenticated"] is True
    assert ver_json["email_verified"] is True
    assert AUTH_COOKIE_NAME in client.cookies
    assert CSRF_COOKIE_NAME in client.cookies
    return ver_json


def _csrf_headers(client: TestClient, extra: dict | None = None) -> dict:
    headers = dict(extra or {})
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    if csrf:
        headers[CSRF_HEADER_NAME] = csrf
    return headers


def test_private_workspace_without_token_returns_401(client: TestClient, db: Session):
    """Verifica que solicitar un workspace privado sin sesión autenticada retorne 401 y no degrade a demo."""
    private_ws = Workspace(
        name="Constructora Privada Test",
        is_demo=False,
    )
    db.add(private_ws)
    db.commit()
    db.refresh(private_ws)

    res = client.get(
        "/api/v1/requisitions",
        headers={"X-Workspace-Id": str(private_ws.id)},
    )
    assert res.status_code == 401
    assert "sesión" in res.json().get("detail", "").lower() or "token" in res.json().get("detail", "").lower()


def test_corrupted_token_returns_401_never_falls_back_to_demo(client: TestClient):
    """Verifica que un token corrupto arroje 401 y no caiga a demo silenciosamente."""
    res = client.get(
        "/api/v1/requisitions",
        headers={"Authorization": "Bearer token_completamente_invalido_xyz"},
    )
    assert res.status_code == 401


def test_user_cannot_access_another_workspace(client: TestClient, db: Session):
    """Verifica que un usuario autenticado por cookie de Workspace A no pueda operar en Workspace B (403)."""
    _register_and_verify_cookie_session(
        client,
        email="user_a@test.com",
        password="Password123!",
        full_name="Usuario A",
        workspace_name="Empresa A",
    )

    ws_b = Workspace(name="Empresa B", is_demo=False)
    db.add(ws_b)
    db.commit()
    db.refresh(ws_b)

    res_forbidden = client.get(
        "/api/v1/requisitions",
        headers={"X-Workspace-Id": str(ws_b.id)},
    )
    assert res_forbidden.status_code == 403
    assert "denegado" in res_forbidden.json().get("detail", "").lower()


def test_auth_register_and_login_flow(client: TestClient):
    """Verifica registro sin sesión previa, verificación por correo, login con cookie HttpOnly y prevención de duplicados."""
    email = f"test_{uuid.uuid4().hex[:6]}@obra.com"
    password = "SeguraPassword2026!"

    # 1. Registro exitoso NO inicia sesión hasta verificar el correo (H-28)
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Ingeniero Civil",
            "workspace_name": "Estudio de Ingeniería",
            "role": "ESTIMATOR",
        },
    )
    assert res_reg.status_code == 201
    reg_data = res_reg.json()
    assert reg_data["email"] == email
    assert reg_data["is_demo"] is False
    assert reg_data["authenticated"] is False
    assert reg_data["email_verified"] is False
    assert "access_token" not in reg_data
    assert AUTH_COOKIE_NAME not in client.cookies

    # Login bloqueado antes de verificar correo (403)
    res_blocked = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert res_blocked.status_code == 403

    # Verificar usando el token enviado por EmailService
    ver_token = EmailService.get_outbox(email)[-1].verification_token
    res_verify = client.post(
        "/api/v1/auth/verify-email",
        json={"email": email, "token": ver_token},
    )
    assert res_verify.status_code == 200
    assert res_verify.json()["authenticated"] is True
    assert AUTH_COOKIE_NAME in client.cookies

    # 2. Intento de registro duplicado (400)
    res_dup = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "otra_password",
            "full_name": "Otro Nombre",
        },
    )
    assert res_dup.status_code == 400

    # Logout limpiando sesión antes de probar login
    res_out = client.post("/api/v1/auth/logout", headers=_csrf_headers(client))
    assert res_out.status_code == 200

    # 3. Login con clave errónea (401)
    res_bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "ClaveIncorrecta!"},
    )
    assert res_bad_login.status_code == 401

    # 4. Login correcto (200) sin exponer JWT en JSON
    res_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert res_login.status_code == 200
    assert "access_token" not in res_login.json()
    assert res_login.json()["workspace_id"] == reg_data["workspace_id"]
    assert AUTH_COOKIE_NAME in res_login.cookies


def test_cannot_upload_catalog_to_public_directory_vendor(client: TestClient, db: Session):
    """Verifica que no se permita modificar catálogos de corralones públicos desde la API de usuario (SEC-02)."""
    public_vendor = db.query(Vendor).filter(Vendor.is_public_directory.is_(True)).first()
    assert public_vendor is not None

    files = {"file": ("catalogo.csv", b"codigo,descripcion,precio\n1,clavo,100\n", "text/csv")}
    res = client.post(
        f"/api/v1/vendors/{public_vendor.id}/catalogs/import",
        files=files,
    )
    assert res.status_code == 403
    assert "público" in res.json().get("detail", "").lower() or "denegado" in res.json().get("detail", "").lower()


def test_switch_mode_creates_dedicated_real_workspaces(client: TestClient):
    """Verifica que switch-mode a modo real exija usuario autenticado y no mezcle workspaces entre usuarios."""
    unauth_res = client.post(
        "/api/v1/auth/switch-mode",
        json={"is_demo": False, "role": "ESTIMATOR"},
    )
    assert unauth_res.status_code == 401

    # Usuario 2 registrado y verificado en sesión temporal
    ws2_data = _register_and_verify_cookie_session(
        client,
        email="arquitecto2@estudio.com.ar",
        password="PasswordSeguro123!",
        full_name="Arq. Dos",
        workspace_name="Estudio Dos",
    )
    ws2_id = ws2_data["workspace_id"]
    client.cookies.clear()

    # Usuario 1 registrado y verificado
    ws1_data = _register_and_verify_cookie_session(
        client,
        email="arquitecto1@estudio.com.ar",
        password="PasswordSeguro123!",
        full_name="Arq. Uno",
        workspace_name="Estudio Uno",
    )
    ws1_id = ws1_data["workspace_id"]
    assert ws1_id != ws2_id

    # Usuario 1 pasa a Demo y luego regresa a Real usando cookie HttpOnly + CSRF
    demo_switch = client.post(
        "/api/v1/auth/switch-mode",
        json={"is_demo": True},
        headers=_csrf_headers(client),
    )
    assert demo_switch.status_code == 200
    assert demo_switch.json()["is_demo"] is True

    real_switch = client.post(
        "/api/v1/auth/switch-mode",
        json={"is_demo": False},
        headers=_csrf_headers(client),
    )
    assert real_switch.status_code == 200
    assert real_switch.json()["is_demo"] is False
    assert real_switch.json()["workspace_id"] == ws1_id
    assert real_switch.json()["workspace_id"] != ws2_id
