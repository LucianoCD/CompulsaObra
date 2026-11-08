"""Dependencias de inyección para autenticación, sesión y workspace_id."""

import uuid
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.workspace import Workspace, User
from app.services.seed import seed_demo_data_if_needed


def get_current_workspace(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    x_workspace_id: Optional[str] = Header(None),
) -> Workspace:
    """Resuelve el Workspace activo con validación estricta de identidad para espacios no-Demo.
    
    Cierra vulnerabilidades SEC-01 / CO-01:
    - X-Workspace-Id sin token solo es permitido si apunta al Workspace Demo público.
    - Token inválido o expirado devuelve 401 Unauthorized (sin degradación silenciosa a Demo).
    - Para workspaces privados se comprueba que el token sea válido y que el usuario exista y pertenezca al espacio.
    """
    # 1. Si se envía encabezado Authorization
    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Formato de encabezado Authorization inválido. Use 'Bearer <token>'.",
            )
        token = authorization.split(" ", 1)[1].strip()
        payload = decode_access_token(token)
        if not payload or "workspace_id" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de sesión inválido o expirado.",
            )
        try:
            token_ws_id = uuid.UUID(str(payload["workspace_id"]))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Identificador de workspace corrupto en el token.",
            )

        # Si además se envía X-Workspace-Id, debe coincidir con el del token firmado
        if x_workspace_id and str(token_ws_id) != x_workspace_id.strip():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: X-Workspace-Id no coincide con el token autenticado.",
            )

        ws = db.scalar(select(Workspace).where(Workspace.id == token_ws_id))
        if not ws:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El espacio de trabajo asociado a la sesión no existe.",
            )

        # En espacios privados o tokens emitidos para usuarios, validar existencia de usuario
        if not ws.is_demo:
            user_id = payload.get("user_id")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="El token de acceso para un espacio real debe incluir un user_id autenticado.",
                )
            try:
                u_uuid = uuid.UUID(str(user_id))
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Identificador de usuario corrupto en el token.",
                )
            user = db.scalar(
                select(User).where(User.id == u_uuid, User.workspace_id == ws.id)
            )
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Usuario no autorizado o no perteneciente a este espacio de trabajo.",
                )

        return ws

    # 2. Si no hay Authorization pero se envía X-Workspace-Id
    if x_workspace_id:
        try:
            ws_id = uuid.UUID(x_workspace_id.strip())
            ws = db.scalar(select(Workspace).where(Workspace.id == ws_id))
            if ws and ws.is_demo:
                return ws
        except (ValueError, TypeError):
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere token Bearer para acceder a un espacio de trabajo privado.",
        )

    # 3. Fallback determinista: Workspace Demo Jujuy (arranque automático sin credenciales)
    demo_ws = seed_demo_data_if_needed(db)
    return demo_ws


def get_current_user_optional(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> Optional[User]:
    """Obtiene el usuario autenticado a partir del token si existe y es válido."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("user_id") or payload.get("real_user_id")
    if not user_id:
        return None
    try:
        u_uuid = uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        return None
    return db.scalar(select(User).where(User.id == u_uuid))


