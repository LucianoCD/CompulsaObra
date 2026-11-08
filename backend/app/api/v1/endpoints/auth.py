"""Endpoints de autenticación, sesión Demo y alternancia de perfiles."""

import uuid
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.workspace import Workspace, User
from app.api.deps import get_current_workspace
from app.services.seed import seed_demo_data_if_needed

router = APIRouter(prefix="/auth", tags=["Autenticación"])


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    workspace_id: uuid.UUID
    workspace_name: str
    is_demo: bool
    role: str
    email: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    workspace_name: Optional[str] = "Mi Estudio / Obra Real"
    role: Optional[str] = "ESTIMATOR"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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
    db: Session = Depends(get_db),
):
    """Registra una cuenta real nueva con su propio Workspace privado aislado."""
    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya se encuentra registrado.",
        )

    target_role = payload.role if payload.role in ["BUYER", "ESTIMATOR"] else "ESTIMATOR"

    # Crear Workspace privado exclusivo
    new_ws = Workspace(
        id=uuid.uuid4(),
        name=payload.workspace_name or "Mi Estudio / Obra Real",
        owner_role=target_role,
        is_demo=False,
    )
    db.add(new_ws)
    db.flush()

    # Crear Usuario propietario
    new_user = User(
        id=uuid.uuid4(),
        workspace_id=new_ws.id,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        role=target_role,
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

    return SessionResponse(
        access_token=token,
        workspace_id=new_ws.id,
        workspace_name=new_ws.name,
        is_demo=False,
        role=new_user.role,
        email=new_user.email,
    )


@router.post("/login", response_model=SessionResponse)
def login_user(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """Inicia sesión autenticada y resuelve el Workspace privado del usuario."""
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de acceso inválidas.",
        )

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

    return SessionResponse(
        access_token=token,
        workspace_id=ws.id,
        workspace_name=ws.name,
        is_demo=ws.is_demo,
        role=user.role,
        email=user.email,
    )


@router.post("/demo-session", response_model=SessionResponse)
def get_or_create_demo_session(db: Session = Depends(get_db)):
    """Inicia o recupera la sesión demo ilustrativa con los 3 corralones de Jujuy."""
    demo_ws = seed_demo_data_if_needed(db)
    token = create_access_token({
        "sub": "demo@compulsaobra.com.ar",
        "workspace_id": str(demo_ws.id),
        "role": demo_ws.owner_role,
        "is_demo": True,
    })
    return SessionResponse(
        access_token=token,
        workspace_id=demo_ws.id,
        workspace_name=demo_ws.name,
        is_demo=demo_ws.is_demo,
        role=demo_ws.owner_role,
        email="demo@compulsaobra.com.ar",
    )


@router.post("/switch-mode", response_model=SessionResponse)
def switch_workspace_mode(
    payload: SwitchModeRequest,
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Permite conmutar entre Modo Demo y un Espacio de Trabajo Real auditado."""
    if payload.is_demo:
        demo_ws = seed_demo_data_if_needed(db)
        token = create_access_token({
            "sub": "demo@compulsaobra.com.ar",
            "workspace_id": str(demo_ws.id),
            "role": demo_ws.owner_role,
            "is_demo": True,
        })
        return SessionResponse(
            access_token=token,
            workspace_id=demo_ws.id,
            workspace_name=demo_ws.name,
            is_demo=True,
            role=demo_ws.owner_role,
            email="demo@compulsaobra.com.ar",
        )
    else:
        # Si la sesión actual ya pertenece a un espacio real, mantenerlo
        if not current_ws.is_demo:
            token = create_access_token({
                "sub": f"usuario_{str(current_ws.id)[:6]}@compulsaobra.com.ar",
                "workspace_id": str(current_ws.id),
                "role": current_ws.owner_role,
                "is_demo": False,
            })
            return SessionResponse(
                access_token=token,
                workspace_id=current_ws.id,
                workspace_name=current_ws.name,
                is_demo=False,
                role=current_ws.owner_role,
                email=f"usuario_{str(current_ws.id)[:6]}@compulsaobra.com.ar",
            )

        # Crear un espacio real NUEVO e independiente para esta sesión (evita colisión global BUG-03)
        target_role = payload.role if payload.role in ["BUYER", "ESTIMATOR"] else "ESTIMATOR"
        new_real_ws = Workspace(
            id=uuid.uuid4(),
            name=payload.workspace_name or "Mi Estudio / Obra Real",
            owner_role=target_role,
            is_demo=False,
        )
        db.add(new_real_ws)
        db.flush()

        real_user = User(
            id=uuid.uuid4(),
            workspace_id=new_real_ws.id,
            email=f"usuario_{str(new_real_ws.id)[:6]}@compulsaobra.com.ar",
            full_name="Usuario Real Obra",
            password_hash=get_password_hash("realpass123"),
            role=target_role,
        )
        db.add(real_user)
        db.commit()

        token = create_access_token({
            "sub": real_user.email,
            "user_id": str(real_user.id),
            "workspace_id": str(new_real_ws.id),
            "role": new_real_ws.owner_role,
            "is_demo": False,
        })
        return SessionResponse(
            access_token=token,
            workspace_id=new_real_ws.id,
            workspace_name=new_real_ws.name,
            is_demo=False,
            role=new_real_ws.owner_role,
            email=real_user.email,
        )


@router.patch("/role", response_model=RoleUpdateResponse)
def update_current_role(
    payload: RoleUpdateRequest,
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Actualiza el rol operativo activo (BUYER vs ESTIMATOR) y emite un token JWT actualizado."""
    if payload.role not in ["BUYER", "ESTIMATOR"]:
        raise HTTPException(status_code=400, detail="Rol inválido. Elija 'BUYER' o 'ESTIMATOR'")
    current_ws.owner_role = payload.role

    # Actualizar también rol en usuarios del workspace
    users = db.scalars(select(User).where(User.workspace_id == current_ws.id)).all()
    for u in users:
        u.role = payload.role
    db.commit()

    new_token = create_access_token({
        "sub": f"user_{str(current_ws.id)[:6]}@compulsaobra.com.ar",
        "workspace_id": str(current_ws.id),
        "role": current_ws.owner_role,
        "is_demo": current_ws.is_demo,
    })

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

