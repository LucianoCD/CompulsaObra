"""Endpoints de autenticación, cookies HttpOnly, rate limiting, verificación y alternancia de perfiles."""

import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional, get_current_workspace
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    auth_rate_limiter,
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.models.workspace import User, Workspace
from app.services.seed import seed_demo_data_if_needed

router = APIRouter(prefix="/auth", tags=["Autenticación"])
AUTH_COOKIE_NAME = "compulsa_access_token"


def _client_rate_key(request: Request, action: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{action}"


def _set_auth_cookie(response: Response, token: str) -> None:
    """Emite la sesión JWT en una cookie HttpOnly segura (H-21)."""
    is_prod = settings.ENVIRONMENT.lower() == "production"
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=is_prod,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    workspace_id: uuid.UUID
    workspace_name: str
    is_demo: bool
    role: str
    email: str
    email_verified: bool = True
    verification_required: bool = False
    verification_token: Optional[str] = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    workspace_name: Optional[str] = "Mi Estudio / Obra Real"
    role: Optional[str] = "ESTIMATOR"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    token: str


class SwitchModeRequest(BaseModel):
    is_demo: bool
    workspace_name: Optional[str] = "Mi Espacio Real"
    role: Optional[str] = "ESTIMATOR"


class RoleUpdateRequest(BaseModel):
    role: str  # 'BUYER' | 'ESTIMATOR'


class RoleUpdateResponse(BaseModel):
    status: str
    role: str
    access_token: str


@router.post("/register", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def register_user_and_workspace(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Registra una cuenta real nueva con su propio Workspace privado aislado y token de verificación."""
    auth_rate_limiter.check_rate_limit(_client_rate_key(request, "register"))

    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya se encuentra registrado.",
        )

    target_role = payload.role if payload.role in ["BUYER", "ESTIMATOR"] else "ESTIMATOR"

    new_ws = Workspace(
        id=uuid.uuid4(),
        name=payload.workspace_name or "Mi Estudio / Obra Real",
        owner_role=target_role,
        is_demo=False,
    )
    db.add(new_ws)
    db.flush()

    verification_token = secrets.token_urlsafe(24)
    new_user = User(
        id=uuid.uuid4(),
        workspace_id=new_ws.id,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        role=target_role,
        email_verified=False,
        verification_token=verification_token,
        failed_login_attempts=0,
    )
    db.add(new_user)
    db.commit()

    token = create_access_token({
        "sub": new_user.email,
        "user_id": str(new_user.id),
        "workspace_id": str(new_ws.id),
        "role": new_user.role,
        "is_demo": False,
    })
    _set_auth_cookie(response, token)

    expose_verification_token = (
        verification_token if settings.ENVIRONMENT.lower() != "production" else None
    )

    return SessionResponse(
        access_token=token,
        workspace_id=new_ws.id,
        workspace_name=new_ws.name,
        is_demo=False,
        role=new_user.role,
        email=new_user.email,
        email_verified=new_user.email_verified,
        verification_required=settings.REQUIRE_EMAIL_VERIFICATION,
        verification_token=expose_verification_token,
    )


@router.post("/verify-email")
def verify_user_email(
    payload: VerifyEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Confirma la propiedad del correo electrónico mediante token seguro (H-22)."""
    auth_rate_limiter.check_rate_limit(_client_rate_key(request, "verify_email"))

    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not user.verification_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de verificación inválido o expirado.",
        )

    if not hmac.compare_digest(payload.token, user.verification_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de verificación inválido.",
        )

    user.email_verified = True
    user.verification_token = None
    db.commit()
    return {"status": "verified", "email": user.email}


@router.post("/login", response_model=SessionResponse)
def login_user(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Inicia sesión autenticada con protección contra fuerza bruta y emisión de cookie HttpOnly."""
    auth_rate_limiter.check_rate_limit(_client_rate_key(request, "login"))
    normalized_email = payload.email.strip().lower()
    auth_rate_limiter.ensure_not_locked(normalized_email)

    user = db.scalar(select(User).where(User.email == payload.email))
    now = datetime.now(timezone.utc)
    if user and user.locked_until is not None:
        locked_until = (
            user.locked_until.replace(tzinfo=timezone.utc)
            if user.locked_until.tzinfo is None
            else user.locked_until
        )
        if locked_until > now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Cuenta temporalmente bloqueada por múltiples intentos fallidos.",
            )

    if not user or not verify_password(payload.password, user.password_hash):
        auth_rate_limiter.record_failed_attempt(normalized_email)
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= settings.AUTH_LOCKOUT_THRESHOLD:
                user.locked_until = now + timedelta(
                    seconds=settings.AUTH_LOCKOUT_DURATION_SECONDS
                )
            db.commit()
            if user.failed_login_attempts >= settings.AUTH_LOCKOUT_THRESHOLD:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Cuenta bloqueada temporalmente tras exceder el límite de intentos fallidos.",
                )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de acceso inválidas.",
        )

    if settings.REQUIRE_EMAIL_VERIFICATION and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debe verificar su correo electrónico antes de iniciar sesión.",
        )

    auth_rate_limiter.clear_failed_attempts(normalized_email)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    ws = db.scalar(select(Workspace).where(Workspace.id == user.workspace_id))
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El espacio de trabajo del usuario no existe.",
        )

    token = create_access_token({
        "sub": user.email,
        "user_id": str(user.id),
        "workspace_id": str(ws.id),
        "role": user.role,
        "is_demo": ws.is_demo,
    })
    _set_auth_cookie(response, token)

    return SessionResponse(
        access_token=token,
        workspace_id=ws.id,
        workspace_name=ws.name,
        is_demo=ws.is_demo,
        role=user.role,
        email=user.email,
        email_verified=user.email_verified,
        verification_required=settings.REQUIRE_EMAIL_VERIFICATION,
    )


@router.post("/demo-session", response_model=SessionResponse)
def get_or_create_demo_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Inicia o recupera la sesión demo ilustrativa con los 3 corralones de Jujuy."""
    auth_rate_limiter.check_rate_limit(_client_rate_key(request, "demo_session"))
    demo_ws = seed_demo_data_if_needed(db)
    token = create_access_token({
        "sub": "demo@compulsaobra.com.ar",
        "workspace_id": str(demo_ws.id),
        "role": demo_ws.owner_role,
        "is_demo": True,
    })
    _set_auth_cookie(response, token)
    return SessionResponse(
        access_token=token,
        workspace_id=demo_ws.id,
        workspace_name=demo_ws.name,
        is_demo=demo_ws.is_demo,
        role=demo_ws.owner_role,
        email="demo@compulsaobra.com.ar",
        email_verified=True,
    )


@router.post("/logout")
def logout_user(response: Response):
    """Elimina la cookie HttpOnly de sesión (H-21)."""
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@router.post("/switch-mode", response_model=SessionResponse)
def switch_workspace_mode(
    payload: SwitchModeRequest,
    response: Response,
    current_ws: Workspace = Depends(get_current_workspace),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Permite conmutar entre Modo Demo y el Espacio de Trabajo Real del usuario autenticado."""
    if payload.is_demo:
        demo_ws = seed_demo_data_if_needed(db)
        token_claims = {
            "sub": "demo@compulsaobra.com.ar",
            "workspace_id": str(demo_ws.id),
            "role": demo_ws.owner_role,
            "is_demo": True,
        }
        if current_user:
            token_claims["real_user_id"] = str(current_user.id)
        token = create_access_token(token_claims)
        _set_auth_cookie(response, token)
        return SessionResponse(
            access_token=token,
            workspace_id=demo_ws.id,
            workspace_name=demo_ws.name,
            is_demo=True,
            role=demo_ws.owner_role,
            email=current_user.email if current_user else "demo@compulsaobra.com.ar",
            email_verified=True,
        )
    else:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Para operar en un espacio de trabajo real auditado, debe iniciar sesión o registrarse.",
            )

        user_ws = db.scalar(
            select(Workspace).where(
                Workspace.id == current_user.workspace_id,
                Workspace.is_demo.is_(False),
            )
        )
        if not user_ws:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró un espacio de trabajo real asociado a su cuenta de usuario.",
            )

        token = create_access_token({
            "sub": current_user.email,
            "user_id": str(current_user.id),
            "workspace_id": str(user_ws.id),
            "role": current_user.role,
            "is_demo": False,
        })
        _set_auth_cookie(response, token)
        return SessionResponse(
            access_token=token,
            workspace_id=user_ws.id,
            workspace_name=user_ws.name,
            is_demo=False,
            role=current_user.role,
            email=current_user.email,
            email_verified=current_user.email_verified,
        )


@router.patch("/role", response_model=RoleUpdateResponse)
def update_current_role(
    payload: RoleUpdateRequest,
    response: Response,
    current_ws: Workspace = Depends(get_current_workspace),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Actualiza el rol operativo activo (BUYER vs ESTIMATOR) y emite un token JWT actualizado."""
    if payload.role not in ["BUYER", "ESTIMATOR"]:
        raise HTTPException(status_code=400, detail="Rol inválido. Elija 'BUYER' o 'ESTIMATOR'")
    current_ws.owner_role = payload.role

    users = db.scalars(select(User).where(User.workspace_id == current_ws.id)).all()
    for u in users:
        u.role = payload.role
    db.commit()

    token_claims = {
        "workspace_id": str(current_ws.id),
        "role": current_ws.owner_role,
        "is_demo": current_ws.is_demo,
    }
    if current_user:
        token_claims["sub"] = current_user.email
        token_claims["user_id"] = str(current_user.id)
    else:
        token_claims["sub"] = "demo@compulsaobra.com.ar"

    new_token = create_access_token(token_claims)
    _set_auth_cookie(response, new_token)

    return RoleUpdateResponse(
        status="success",
        role=current_ws.owner_role,
        access_token=new_token,
    )


@router.get("/me", response_model=Dict[str, Any])
def get_current_session_info(current_ws: Workspace = Depends(get_current_workspace)):
    """Retorna información del estado de sesión actual."""
    return {
        "workspace_id": current_ws.id,
        "workspace_name": current_ws.name,
        "is_demo": current_ws.is_demo,
        "role": current_ws.owner_role,
    }
