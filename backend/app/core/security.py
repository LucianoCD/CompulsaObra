"""Seguridad: JWT Auth, bcrypt y firma HMAC-SHA256 para enlaces públicos."""

import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
import bcrypt

from app.core.config import settings

ALGORITHM = "HS256"


def get_password_hash(password: str) -> str:
    """Genera hash bcrypt seguro para contraseñas de usuarios."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña contra su hash bcrypt."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Genera un token JWT firmado."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodifica y valida un token JWT."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


def generate_hmac_share_token(comparison_run_id: str, requisition_id: str) -> str:
    """Genera un token público firmado con HMAC-SHA256 inalterable."""
    message = f"{comparison_run_id}:{requisition_id}".encode("utf-8")
    secret = settings.HMAC_SHARE_SECRET.encode("utf-8")
    signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return f"{comparison_run_id}.{signature}"


def verify_hmac_share_token(token: str, requisition_id: str) -> bool:
    """Verifica la autenticidad del token HMAC usando compare_digest."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False
        run_id, signature = parts
        expected_token = generate_hmac_share_token(run_id, requisition_id)
        return hmac.compare_digest(token, expected_token)
    except Exception:
        return False
