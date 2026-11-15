"""Endpoints de autenticación basada en cookies HttpOnly + CSRF, verificación por email y alternancia de perfiles."""

import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional, get_current_workspace, get_demo_role_from_token
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    AUTH_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    auth_rate_limiter,
    create_access_token,
    generate_csrf_token,
    get_password_hash,
    verify_password,
)
from app.models.workspace import User, Workspace
from app.services.email_service import EmailDeliveryError, EmailService, hash_verification_token
from app.services.seed import seed_demo_data_if_needed
from app.services.traction_service import record_traction_event

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _client_rate_key(request: Request, action: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{action}"


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _set_session_cookies(response: Response, token: str) -> None:
    """Emite la sesión JWT en cookie HttpOnly y el token CSRF Double-Submit (H-21, H-33)."""
    secure_flag = settings.cookie_secure_effective
    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=secure_flag,
        max_age=max_age,
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=generate_csrf_token(),
        httponly=False,
        samesite="lax",
        secure=secure_flag,
        max_age=max_age,
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")


class SessionResponse(BaseModel):
    authenticated: bool = True
    workspace_id: uuid.UUID
    workspace_name: str
    is_demo: bool
    role: str
    email: str
    email_verified: bool = True
    verification_required: bool = False
    message: Optional[str] = None


_DUMMY_BCRYPT_HASH = get_password_hash("compulsa-dummy-timing-guard-v1")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=2, max_length=120)
    workspace_name: Optional[str] = Field(default="Mi Estudio / Obra Real", max_length=140)
    role: Optional[str] = "ESTIMATOR"

    @field_validator("password")
    @classmethod
    def validate_password_utf8_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("La contraseña no puede superar los 72 bytes UTF-8.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class SwitchModeRequest(BaseModel):
    is_demo: bool
    workspace_name: Optional[str] = "Mi Espacio Real"
    role: Optional[str] = "ESTIMATOR"


class RoleUpdateRequest(BaseModel):
    role: str  # 'BUYER' | 'ESTIMATOR'


class RoleUpdateResponse(BaseModel):
    status: str
    role: str
    workspace_id: uuid.UUID


@router.post("/register", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def register_user_and_workspace(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Registra cuenta y workspace real SIN emitir sesión hasta verificar el correo (H-28, H-29)."""
    auth_rate_limiter.check_rate_limit(_client_rate_key(request, "register"), db=db)

    normalized_email = payload.email.strip().lower()
    existing_user = db.scalar(
        select(User).where(sa.func.lower(User.email) == normalized_email)
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya se encuentra registrado.",
        )

    target_role = payload.role if payload.role in ["BUYER", "ESTIMATOR"] else "ESTIMATOR"
    now = datetime.now(timezone.utc)

    new_ws = Workspace(
        id=uuid.uuid4(),
        name=payload.workspace_name or "Mi Estudio / Obra Real",
        owner_role=target_role,
        is_demo=False,
    )
    db.add(new_ws)
    db.flush()

    raw_verification_token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(minutes=settings.EMAIL_VERIFICATION_EXPIRE_MINUTES)
    new_user = User(
        id=uuid.uuid4(),
        workspace_id=new_ws.id,
        email=normalized_email,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        role=target_role,
        email_verified=False,
        verification_token_hash=hash_verification_token(raw_verification_token),
        verification_token_expires_at=expires_at,
        verification_sent_at=now,
        failed_login_attempts=0,
    )
    db.add(new_user)
    db.flush()

    try:
        EmailService.send_verification_email(
            recipient_email=new_user.email,
            verification_token=raw_verification_token,
            workspace_name=new_ws.name,
            expires_minutes=settings.EMAIL_VERIFICATION_EXPIRE_MINUTES,
        )
    except EmailDeliveryError:
        db.rollback()
        raise

    record_traction_event(
        db,
        event_type="USER_REGISTERED",
        workspace_id=new_ws.id,
        user_id=new_user.id,
        is_demo=False,
    )
    db.commit()

    return SessionResponse(
        authenticated=False,
        workspace_id=new_ws.id,
        workspace_name=new_ws.name,
        is_demo=False,
        role=new_user.role,
        email=new_user.email,
        email_verified=False,
        verification_required=settings.REQUIRE_EMAIL_VERIFICATION,
        message="Cuenta creada. Revisá tu correo electrónico para verificar la dirección antes de iniciar sesión.",
    )


@router.post("/verify-email", response_model=SessionResponse)
def verify_user_email(
    payload: VerifyEmailRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Confirma la propiedad del correo con token con hash SHA-256 + vencimiento e inicia sesión en cookie HttpOnly."""
    auth_rate_limiter.check_rate_limit(_client_rate_key(request, "verify_email"), db=db)

    normalized_email = payload.email.strip().lower()
    user = db.scalar(select(User).where(sa.func.lower(User.email) == normalized_email))
    if not user or not user.verification_token_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de verificación inválido o expirado.",
        )

    now = datetime.now(timezone.utc)
    expires_at = _as_utc(user.verification_token_expires_at)
    if expires_at is None or expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace o token de verificación ha expirado. Solicitá un reenvío.",
        )

    submitted_hash = hash_verification_token(payload.token)
    if not hmac.compare_digest(submitted_hash, user.verification_token_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de verificación inválido.",
        )

    ws = db.scalar(select(Workspace).where(Workspace.id == user.workspace_id))
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El espacio de trabajo del usuario no existe.",
        )

    user.email_verified = True
    user.verification_token_hash = None
    user.verification_token_expires_at = None

    record_traction_event(
        db,
        event_type="USER_EMAIL_VERIFIED",
        workspace_id=ws.id,
        user_id=user.id,
        is_demo=ws.is_demo,
    )
    db.commit()

    token = create_access_token({
        "sub": user.email,
        "user_id": str(user.id),
        "workspace_id": str(ws.id),
        "role": user.role,
        "is_demo": ws.is_demo,
    })
    _set_session_cookies(response, token)

    return SessionResponse(
        authenticated=True,
        workspace_id=ws.id,
        workspace_name=ws.name,
        is_demo=ws.is_demo,
        role=user.role,
        email=user.email,
        email_verified=True,
        verification_required=settings.REQUIRE_EMAIL_VERIFICATION,
        message="Correo verificado correctamente.",
    )


@router.post("/resend-verification")
def resend_verification_email(
    payload: ResendVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Reenvía el correo de verificación respetando cooldown y vencimiento (H-29)."""
    auth_rate_limiter.check_rate_limit(_client_rate_key(request, "resend_verification"), db=db)

    normalized_email = payload.email.strip().lower()
    user = db.scalar(select(User).where(sa.func.lower(User.email) == normalized_email))
    if not user or user.email_verified:
        return {
            "status": "ok",
            "message": "Si la cuenta existe y está pendiente de verificación, se enviará un nuevo correo.",
        }

    now = datetime.now(timezone.utc)
    last_sent = _as_utc(user.verification_sent_at)
    if last_sent is not None:
        elapsed = (now - last_sent).total_seconds()
        if elapsed < settings.EMAIL_RESEND_COOLDOWN_SECONDS:
            wait_s = int(settings.EMAIL_RESEND_COOLDOWN_SECONDS - elapsed) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Debés esperar {wait_s}s antes de solicitar otro correo de verificación.",
            )

    ws = db.scalar(select(Workspace).where(Workspace.id == user.workspace_id))
    ws_name = ws.name if ws else "CompulsaObra"

    raw_verification_token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(minutes=settings.EMAIL_VERIFICATION_EXPIRE_MINUTES)
    user.verification_token_hash = hash_verification_token(raw_verification_token)
    user.verification_token_expires_at = expires_at
    user.verification_sent_at = now

    try:
        EmailService.send_verification_email(
            recipient_email=user.email,
            verification_token=raw_verification_token,
            workspace_name=ws_name,
            expires_minutes=settings.EMAIL_VERIFICATION_EXPIRE_MINUTES,
        )
    except EmailDeliveryError:
        db.rollback()
        raise

    db.commit()
    return {
        "status": "sent",
        "message": "Correo de verificación reenviado correctamente.",
    }


@router.post("/login", response_model=SessionResponse)
def login_user(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Inicia sesión autenticada con protección distribuida contra fuerza bruta y cookie HttpOnly + CSRF."""
    auth_rate_limiter.check_rate_limit(_client_rate_key(request, "login"), db=db)
    normalized_email = payload.email.strip().lower()
    auth_rate_limiter.ensure_not_locked(normalized_email, db=db)

    user = db.scalar(select(User).where(sa.func.lower(User.email) == normalized_email))
    now = datetime.now(timezone.utc)
    if user and user.locked_until is not None:
        locked_until = _as_utc(user.locked_until)
        if locked_until and locked_until > now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Cuenta temporalmente bloqueada por múltiples intentos fallidos.",
            )
        user.failed_login_attempts = 0
        user.locked_until = None

    password_valid = (
        verify_password(payload.password, user.password_hash)
        if user
        else (verify_password(payload.password, _DUMMY_BCRYPT_HASH) and False)
    )
    if not user or not password_valid:
        auth_rate_limiter.record_failed_attempt(normalized_email, db=db)
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
                    detail="Cuenta temporalmente bloqueada por múltiples intentos fallidos.",
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

    auth_rate_limiter.clear_failed_attempts(normalized_email, db=db)
    user.failed_login_attempts = 0
    user.locked_until = None

    ws = db.scalar(select(Workspace).where(Workspace.id == user.workspace_id))
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El espacio de trabajo del usuario no existe.",
        )

    record_traction_event(
        db,
        event_type="WORKSPACE_LOGIN",
        workspace_id=ws.id,
        user_id=user.id,
        is_demo=ws.is_demo,
    )
    db.commit()

    token = create_access_token({
        "sub": user.email,
        "user_id": str(user.id),
        "workspace_id": str(ws.id),
        "role": user.role,
        "is_demo": ws.is_demo,
    })
    _set_session_cookies(response, token)

    return SessionResponse(
        authenticated=True,
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
    """Inicia o recupera la sesión demo ilustrativa con los 3 corralones de Jujuy en cookies seguras."""
    auth_rate_limiter.check_rate_limit(_client_rate_key(request, "demo_session"), db=db)
    demo_ws = seed_demo_data_if_needed(db)
    token = create_access_token({
        "sub": "demo@compulsaobra.com.ar",
        "workspace_id": str(demo_ws.id),
        "role": demo_ws.owner_role,
        "is_demo": True,
    })
    _set_session_cookies(response, token)
    return SessionResponse(
        authenticated=True,
        workspace_id=demo_ws.id,
        workspace_name=demo_ws.name,
        is_demo=demo_ws.is_demo,
        role=demo_ws.owner_role,
        email="demo@compulsaobra.com.ar",
        email_verified=True,
        verification_required=settings.REQUIRE_EMAIL_VERIFICATION,
    )


@router.post("/logout")
def logout_user(response: Response):
    """Elimina cookies HttpOnly y CSRF de sesión (H-21, H-33)."""
    _clear_session_cookies(response)
    return {"status": "logged_out"}


@router.post("/switch-mode", response_model=SessionResponse)
def switch_workspace_mode(
    payload: SwitchModeRequest,
    response: Response,
    current_ws: Workspace = Depends(get_current_workspace),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Permite conmutar entre Modo Demo y el Espacio de Trabajo Real verificado del usuario."""
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
        _set_session_cookies(response, token)
        return SessionResponse(
            authenticated=True,
            workspace_id=demo_ws.id,
            workspace_name=demo_ws.name,
            is_demo=True,
            role=demo_ws.owner_role,
            email=current_user.email if current_user else "demo@compulsaobra.com.ar",
            email_verified=True,
            verification_required=settings.REQUIRE_EMAIL_VERIFICATION,
        )
    else:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Para operar en un espacio de trabajo real auditado, debe iniciar sesión con su correo verificado.",
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
        _set_session_cookies(response, token)
        return SessionResponse(
            authenticated=True,
            workspace_id=user_ws.id,
            workspace_name=user_ws.name,
            is_demo=False,
            role=current_user.role,
            email=current_user.email,
            email_verified=current_user.email_verified,
            verification_required=settings.REQUIRE_EMAIL_VERIFICATION,
        )


@router.patch("/role", response_model=RoleUpdateResponse)
def update_current_role(
    payload: RoleUpdateRequest,
    response: Response,
    current_ws: Workspace = Depends(get_current_workspace),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Actualiza el rol operativo activo (BUYER vs ESTIMATOR) en la cookie de sesión."""
    if payload.role not in ["BUYER", "ESTIMATOR"]:
        raise HTTPException(status_code=400, detail="Rol inválido. Elija 'BUYER' o 'ESTIMATOR'")
    effective_role = payload.role
    if not current_ws.is_demo:
        current_ws.owner_role = effective_role

        users = db.scalars(select(User).where(User.workspace_id == current_ws.id)).all()
        for u in users:
            u.role = effective_role
        db.commit()

    token_claims = {
        "workspace_id": str(current_ws.id),
        "role": effective_role,
        "is_demo": current_ws.is_demo,
    }
    if current_user:
        token_claims["sub"] = current_user.email
        if current_ws.is_demo:
            token_claims["real_user_id"] = str(current_user.id)
        else:
            token_claims["user_id"] = str(current_user.id)
    else:
        token_claims["sub"] = "demo@compulsaobra.com.ar"

    new_token = create_access_token(token_claims)
    _set_session_cookies(response, new_token)

    return RoleUpdateResponse(
        status="success",
        role=effective_role,
        workspace_id=current_ws.id,
    )


@router.get("/me", response_model=SessionResponse)
def get_current_session_info(
    request: Request,
    response: Response,
    current_ws: Workspace = Depends(get_current_workspace),
    current_user: Optional[User] = Depends(get_current_user_optional),
    session_role: Optional[str] = Depends(get_demo_role_from_token),
):
    """Retorna estado de sesión actual y asegura cookie CSRF si hay sesión por cookie."""
    if request.cookies.get(AUTH_COOKIE_NAME) and not request.cookies.get(CSRF_COOKIE_NAME):
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=generate_csrf_token(),
            httponly=False,
            samesite="lax",
            secure=settings.cookie_secure_effective,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
        )
    effective_role = (
        session_role
        if (current_ws.is_demo and session_role in ("BUYER", "ESTIMATOR"))
        else current_ws.owner_role
    )
    return SessionResponse(
        authenticated=True,
        workspace_id=current_ws.id,
        workspace_name=current_ws.name,
        is_demo=current_ws.is_demo,
        role=effective_role,
        email=current_user.email if current_user else "demo@compulsaobra.com.ar",
        email_verified=current_user.email_verified if current_user else True,
        verification_required=settings.REQUIRE_EMAIL_VERIFICATION,
    )
