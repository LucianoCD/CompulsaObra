"""Dependencias de inyección para autenticación (Bearer o cookie HttpOnly), sesión y workspace_id."""

import uuid
from typing import Optional
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.workspace import User, Workspace
from app.services.seed import seed_demo_data_if_needed

AUTH_COOKIE_NAME = "compulsa_access_token"


def _extract_jwt_token(request: Request, authorization: Optional[str]) -> Optional[str]:
    """Extrae el JWT desde el header Authorization Bearer o desde la cookie HttpOnly (H-21)."""
    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Formato de encabezado Authorization inválido. Use 'Bearer <token>'.",
            )
        return authorization.split(" ", 1)[1].strip()
    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    if cookie_token:
        return cookie_token.strip()
    return None


def get_current_workspace(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    x_workspace_id: Optional[str] = Header(None),
) -> Workspace:
    """Resuelve el Workspace activo con validación estricta de identidad para espacios no-Demo."""
    token = _extract_jwt_token(request, authorization)

    if token:
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
            detail="Se requiere token o sesión autenticada para acceder a un espacio de trabajo privado.",
        )

    demo_ws = seed_demo_data_if_needed(db)
    return demo_ws


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> Optional[User]:
    """Obtiene el usuario autenticado a partir del header Bearer o cookie HttpOnly si existe y es válido."""
    try:
        token = _extract_jwt_token(request, authorization)
    except HTTPException:
        return None
    if not token:
        return None
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
