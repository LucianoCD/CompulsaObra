"""Pruebas de seguridad, aislamiento multitenant y autenticación (SEC-01, SEC-02, CO-01, CO-04, BUG-03)."""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.workspace import Workspace, User
from app.models.vendor import Vendor


def test_private_workspace_without_token_returns_401(client: TestClient, db: Session):
    """Verifica que solicitar un workspace privado sin Bearer token retorne 401 y no degrade a demo."""
    private_ws = Workspace(
        name="Constructora Privada Test",
        is_demo=False,
    )
    db.add(private_ws)
    db.commit()
    db.refresh(private_ws)

    # Intento de acceso a endpoint privado sin Authorization
    res = client.get(
        "/api/v1/requisitions/",
        headers={"X-Workspace-Id": str(private_ws.id)},
    )
    assert res.status_code == 401
    assert "token" in res.json().get("detail", "").lower()


def test_corrupted_token_returns_401_never_falls_back_to_demo(client: TestClient):
    """Verifica que un token corrupto o inválido arroje 401 y no caiga a demo silenciosamente."""
    res = client.get(
        "/api/v1/requisitions/",
        headers={"Authorization": "Bearer token_completamente_invalido_xyz"},
    )
    assert res.status_code == 401


def test_user_cannot_access_another_workspace(client: TestClient, db: Session):
    """Verifica que un usuario con token de Workspace A no pueda operar en Workspace B (403)."""
    # 1. Registrar usuario en Workspace A
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user_a@test.com",
            "password": "Password123!",
            "full_name": "Usuario A",
            "workspace_name": "Empresa A",
            "role": "ESTIMATOR",
        },
    )
    assert res_reg.status_code == 201
    token_a = res_reg.json()["access_token"]
    ws_a_id = res_reg.json()["workspace_id"]

    # 2. Crear Workspace B
    ws_b = Workspace(name="Empresa B", is_demo=False)
    db.add(ws_b)
    db.commit()
    db.refresh(ws_b)

    # 3. Usuario A intenta enviar X-Workspace-Id de B
    res_forbidden = client.get(
        "/api/v1/requisitions/",
        headers={
            "Authorization": f"Bearer {token_a}",
            "X-Workspace-Id": str(ws_b.id),
        },
    )
    assert res_forbidden.status_code == 403
    assert "denegado" in res_forbidden.json().get("detail", "").lower()


def test_auth_register_and_login_flow(client: TestClient):
    """Verifica el flujo completo de registro, login con bcrypt y prevención de duplicados."""
    email = f"test_{uuid.uuid4().hex[:6]}@obra.com"
    password = "SeguraPassword2026!"

    # 1. Registro exitoso
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
    assert "access_token" in reg_data

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

    # 3. Login con clave errónea (401)
    res_bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "ClaveIncorrecta!"},
    )
    assert res_bad_login.status_code == 401

    # 4. Login correcto (200)
    res_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert res_login.status_code == 200
    assert "access_token" in res_login.json()
    assert res_login.json()["workspace_id"] == reg_data["workspace_id"]


def test_cannot_upload_catalog_to_public_directory_vendor(client: TestClient, db: Session):
    """Verifica que no se permita modificar catálogos de corralones públicos desde la API de usuario (SEC-02)."""
    # Obtener un proveedor de directorio público del seed
    public_vendor = db.query(Vendor).filter(Vendor.is_public_directory == True).first()
    assert public_vendor is not None

    # Intentar subir catálogo con multipart/form-data
    files = {"file": ("catalogo.csv", b"codigo,descripcion,precio\n1,clavo,100\n", "text/csv")}
    res = client.post(
        f"/api/v1/vendors/{public_vendor.id}/catalogs/import",
        files=files,
    )
    assert res.status_code == 403
    assert "público" in res.json().get("detail", "").lower() or "denegado" in res.json().get("detail", "").lower()


def test_switch_mode_creates_dedicated_real_workspaces(client: TestClient):
    """Verifica que dos llamadas a switch-mode para modo real no colisionen en el mismo workspace (BUG-03)."""
    res1 = client.post(
        "/api/v1/auth/switch-mode",
        json={"is_demo": False, "role": "ESTIMATOR"},
    )
    assert res1.status_code == 200
    ws1_id = res1.json()["workspace_id"]

    res2 = client.post(
        "/api/v1/auth/switch-mode",
        json={"is_demo": False, "role": "BUYER"},
    )
    assert res2.status_code == 200
    ws2_id = res2.json()["workspace_id"]

    assert ws1_id != ws2_id, "Cada switch a modo real debe generar su propio workspace aislado"
