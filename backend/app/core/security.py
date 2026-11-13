"""Seguridad: JWT Auth, bcrypt, firma HMAC-SHA256 con hash de snapshot, uploads acotados y rate limiting."""

import hashlib
import hmac
import json
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Deque, Dict, Optional

import bcrypt
import jwt
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

ALGORITHM = "HS256"
_SNAPSHOT_EXCLUDED_KEYS = {"public_share_token", "snapshot_content_hash"}


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


def compute_matrix_snapshot_hash(matrix_data: Optional[Dict[str, Any]]) -> str:
    """Calcula un hash SHA-256 canónico del contenido del snapshot (H-04)."""
    if not isinstance(matrix_data, dict):
        return hashlib.sha256(b"empty_snapshot").hexdigest()[:32]

    sanitized = {
        k: v for k, v in matrix_data.items() if k not in _SNAPSHOT_EXCLUDED_KEYS
    }
    canonical_json = json.dumps(
        sanitized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:32]


def generate_hmac_share_token(
    comparison_run_id: str,
    requisition_id: str,
    matrix_data: Optional[Dict[str, Any]] = None,
) -> str:
    """Genera un token público firmado con HMAC-SHA256 ligado al contenido del snapshot (H-04)."""
    snapshot_hash = compute_matrix_snapshot_hash(matrix_data)
    message = f"{comparison_run_id}:{requisition_id}:{snapshot_hash}".encode("utf-8")
    secret = settings.HMAC_SHARE_SECRET.encode("utf-8")
    signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return f"{comparison_run_id}.{signature}"


def verify_hmac_share_token(
    token: str,
    requisition_id: str,
    matrix_data: Optional[Dict[str, Any]] = None,
) -> bool:
    """Verifica la autenticidad del token HMAC y la integridad del snapshot usando compare_digest (H-04)."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False
        run_id, _ = parts
        expected_token = generate_hmac_share_token(
            run_id,
            requisition_id,
            matrix_data=matrix_data,
        )
        return hmac.compare_digest(token, expected_token)
    except Exception:
        return False


async def read_upload_file_bounded(
    upload_file: UploadFile,
    max_bytes: int,
    chunk_size: int = 65536,
) -> bytes:
    """Lee un archivo subido en bloques acotados y aborta con HTTP 413 al superar max_bytes (H-17)."""
    buffer = bytearray()
    while True:
        chunk = await upload_file.read(chunk_size)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            max_mb = max(1, max_bytes // (1024 * 1024))
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"El archivo excede el tamaño máximo permitido de {max_mb} MB.",
            )
    return bytes(buffer)


class AuthRateLimiter:
    """Limitador de tasa por ventana deslizante y bloqueo progresivo en memoria (H-22)."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._failed_attempts: Dict[str, int] = defaultdict(int)
        self._lockouts: Dict[str, float] = {}

    def check_rate_limit(
        self,
        key: str,
        max_requests: Optional[int] = None,
        window_seconds: Optional[int] = None,
    ) -> None:
        limit = max_requests if max_requests is not None else settings.AUTH_RATE_LIMIT_MAX_REQUESTS
        window = window_seconds if window_seconds is not None else settings.AUTH_RATE_LIMIT_WINDOW_SECONDS
        now = time.monotonic()
        with self._lock:
            q = self._requests[key]
            cutoff = now - window
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Demasiadas solicitudes de autenticación. Intente nuevamente en unos segundos.",
                )
            q.append(now)

    def ensure_not_locked(self, identifier: str) -> None:
        now = time.monotonic()
        with self._lock:
            until = self._lockouts.get(identifier)
            if until and until > now:
                remaining = int(until - now) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Cuenta temporalmente bloqueada por múltiples intentos fallidos. Reintente en {remaining}s.",
                )
            if until and until <= now:
                self._lockouts.pop(identifier, None)

    def record_failed_attempt(self, identifier: str) -> int:
        threshold = settings.AUTH_LOCKOUT_THRESHOLD
        base_duration = settings.AUTH_LOCKOUT_DURATION_SECONDS
        now = time.monotonic()
        with self._lock:
            attempts = self._failed_attempts[identifier] + 1
            self._failed_attempts[identifier] = attempts
            if attempts >= threshold:
                multiplier = 2 ** min(4, attempts - threshold)
                self._lockouts[identifier] = now + (base_duration * multiplier)
            return attempts

    def clear_failed_attempts(self, identifier: str) -> None:
        with self._lock:
            self._failed_attempts.pop(identifier, None)
            self._lockouts.pop(identifier, None)

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()
            self._failed_attempts.clear()
            self._lockouts.clear()


auth_rate_limiter = AuthRateLimiter()
