"""Seguridad: JWT Auth, bcrypt, CSRF, firma HMAC-SHA256 con hash de snapshot, uploads acotados y rate limiting compartido."""

import hashlib
import hmac
import json
import logging
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Deque, Dict, Optional

import bcrypt
import jwt
import redis
from fastapi import HTTPException, UploadFile, status
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
AUTH_COOKIE_NAME = "compulsa_access_token"
CSRF_COOKIE_NAME = "compulsa_csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

_SNAPSHOT_EXCLUDED_KEYS = {"public_share_token", "snapshot_content_hash"}

_REDIS_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local cutoff = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local window = tonumber(ARGV[4])
local member = ARGV[5]

redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)
local current = redis.call('ZCARD', key)
if current >= limit then
    return 0
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, math.ceil(window) + 5)
return 1
"""


def get_password_hash(password: str) -> str:
    """Genera hash bcrypt seguro para contraseñas de usuarios."""
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > 72:
        raise HTTPException(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            detail="La contraseña no puede superar los 72 bytes UTF-8.",
        )
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña contra su hash bcrypt."""
    try:
        if not plain_password or not hashed_password:
            return False
        pwd_bytes = plain_password.encode("utf-8")
        if len(pwd_bytes) > 72:
            return False
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
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


def generate_csrf_token() -> str:
    """Genera token aleatorio para protección Double-Submit Cookie CSRF (H-21, H-33)."""
    return secrets.token_urlsafe(32)


def verify_csrf_token(cookie_token: Optional[str], header_token: Optional[str]) -> bool:
    """Verifica en tiempo constante coincidencia entre cookie CSRF y cabecera X-CSRF-Token."""
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)


def compute_requisition_version_hash(req: Any) -> str:
    """Calcula SHA-256 determinístico del contenido técnico, cantidades y unidades del pliego (H-39)."""
    if req is None:
        return hashlib.sha256(b"empty_requisition").hexdigest()

    items_sorted = sorted(
        list(getattr(req, "items", []) or []),
        key=lambda it: (int(getattr(it, "line_order", 0) or 0), str(getattr(it, "id", ""))),
    )
    payload = {
        "requisition_id": str(getattr(req, "id", "")),
        "version": int(getattr(req, "version", 1) or 1),
        "items": [
            {
                "id": str(getattr(it, "id", "")),
                "line_order": int(getattr(it, "line_order", 0) or 0),
                "requested_term": str(getattr(it, "requested_term", "") or "").strip(),
                "quantity": f"{float(getattr(it, 'quantity', 0) or 0):.4f}",
                "requested_unit": str(getattr(it, "requested_unit", "UN") or "UN").strip().upper(),
                "diameter_mm": f"{float(it.diameter_mm):.4f}" if getattr(it, "diameter_mm", None) is not None else None,
                "length_m": f"{float(it.length_m):.4f}" if getattr(it, "length_m", None) is not None else None,
                "weight_kg": f"{float(it.weight_kg):.4f}" if getattr(it, "weight_kg", None) is not None else None,
                "material_type": str(it.material_type).strip() if getattr(it, "material_type", None) else None,
                "completeness": str(getattr(it, "completeness", "complete") or "complete"),
                "is_confirmed": bool(getattr(it, "is_confirmed", False)),
            }
            for it in items_sorted
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_matrix_snapshot_hash(matrix_data: Optional[Dict[str, Any]]) -> str:
    """Calcula un hash SHA-256 canónico del contenido y metadatos del snapshot (H-04, H-32)."""
    if not isinstance(matrix_data, dict):
        return hashlib.sha256(b"empty_snapshot").hexdigest()

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
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def generate_hmac_share_token(
    comparison_run_id: str,
    requisition_id: str,
    matrix_data: Optional[Dict[str, Any]] = None,
) -> str:
    """Genera un token público firmado con HMAC-SHA256 ligado al contenido y metadatos del snapshot (H-04, H-32)."""
    snapshot_hash = compute_matrix_snapshot_hash(matrix_data)
    message = f"{comparison_run_id}:{requisition_id}:{snapshot_hash}".encode("utf-8")
    secret = settings.HMAC_SHARE_SECRET.encode("utf-8")
    signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return f"{comparison_run_id}.{signature}"


def verify_hmac_share_token(
    token: str,
    requisition_id: str,
    matrix_data: Optional[Dict[str, Any]] = None,
    expected_snapshot_hash: Optional[str] = None,
    expected_run_id: Optional[str] = None,
) -> bool:
    """Verifica HMAC, run_id, snapshot_content_hash interno y locked_snapshot_hash persistido (H-04, H-32, S-H5)."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False
        run_id, _ = parts
        if not run_id:
            return False
        if expected_run_id is not None and not hmac.compare_digest(str(run_id), str(expected_run_id)):
            return False

        if not isinstance(matrix_data, dict):
            return False
        stored_hash = str(matrix_data.get("snapshot_content_hash") or "").strip()
        if not stored_hash:
            return False

        computed_hash = compute_matrix_snapshot_hash(matrix_data)
        if not hmac.compare_digest(stored_hash, computed_hash):
            return False

        if expected_snapshot_hash is not None:
            exp_hash_clean = str(expected_snapshot_hash).strip()
            if not exp_hash_clean or not hmac.compare_digest(exp_hash_clean, computed_hash):
                return False

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
                status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
                detail=f"El archivo excede el tamaño máximo permitido de {max_mb} MB.",
            )
    return bytes(buffer)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class AuthRateLimiter:
    """Limitador de tasa y bloqueo progresivo compartido: Redis primario + respaldo persistente SQL (H-22, H-34)."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._redis_url_cached: Optional[str] = None
        self._redis_client: Optional[redis.Redis] = None
        # Solo fallback efímero si se invoca sin sesión BD y sin Redis válido
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._failed_attempts: Dict[str, int] = defaultdict(int)
        self._lockouts: Dict[str, float] = {}

    def _get_redis(self) -> Optional[redis.Redis]:
        url = settings.REDIS_URL.strip()
        if not url:
            self._redis_client = None
            self._redis_url_cached = None
            return None
        if self._redis_client is None or self._redis_url_cached != url:
            self._redis_client = redis.Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=1.5,
                socket_timeout=1.5,
            )
            self._redis_url_cached = url
        return self._redis_client

    def _open_db_session(self, db: Optional[Session]) -> tuple[Optional[Session], bool]:
        """Retorna (session, owns_session).

        En engines compartibles (PostgreSQL o SQLite archivo) abre una sesión
        independiente para que los contadores persistan incluso ante errores HTTP.
        En SQLite `:memory:` reutiliza la sesión actual.
        """
        if db is not None:
            bind = db.get_bind()
            db_name = getattr(bind.url, "database", None)
            if bind.dialect.name == "sqlite" and db_name in (None, "", ":memory:"):
                return db, False
            IndependentSession = sessionmaker(
                autocommit=False, autoflush=False, bind=bind, expire_on_commit=False
            )
            return IndependentSession(), True

        from app.core.database import SessionLocal

        return SessionLocal(), True

    def check_rate_limit(
        self,
        key: str,
        max_requests: Optional[int] = None,
        window_seconds: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> None:
        limit = max_requests if max_requests is not None else settings.AUTH_RATE_LIMIT_MAX_REQUESTS
        window = window_seconds if window_seconds is not None else settings.AUTH_RATE_LIMIT_WINDOW_SECONDS

        client = self._get_redis()
        if client is not None:
            try:
                now = time.time()
                cutoff = now - window
                member = f"{now}:{secrets.token_hex(6)}"
                allowed = client.eval(
                    _REDIS_SLIDING_WINDOW_LUA,
                    1,
                    f"compulsa:auth:rl:{key}",
                    now,
                    cutoff,
                    limit,
                    window,
                    member,
                )
                if not int(allowed):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Demasiadas solicitudes de autenticación. Intente nuevamente en unos segundos.",
                    )
                return
            except HTTPException:
                raise
            except redis.RedisError as exc:
                logger.warning("Redis no disponible en rate limit, usando respaldo BD: %s", exc)

        self._check_rate_limit_db(key, limit, window, db=db)

    def _check_rate_limit_db(
        self,
        key: str,
        limit: int,
        window: int,
        db: Optional[Session],
    ) -> None:
        from app.models.telemetry import AuthSecurityCounter

        counter_key = f"rl:{key}"
        now = datetime.now(timezone.utc)
        session, owns_session = self._open_db_session(db)
        try:
            with self._lock:
                stmt = sa.select(AuthSecurityCounter).where(
                    AuthSecurityCounter.counter_key == counter_key
                )
                if session.get_bind().dialect.name == "postgresql":
                    stmt = stmt.with_for_update()
                row = session.execute(stmt).scalar_one_or_none()

                if row is None:
                    row = AuthSecurityCounter(
                        counter_key=counter_key,
                        count=1,
                        window_expires_at=now + timedelta(seconds=window),
                        updated_at=now,
                    )
                    session.add(row)
                else:
                    expires_at = _as_utc(row.window_expires_at)
                    if expires_at is None or expires_at <= now:
                        row.count = 1
                        row.window_expires_at = now + timedelta(seconds=window)
                        row.updated_at = now
                    elif row.count >= limit:
                        session.commit()
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Demasiadas solicitudes de autenticación. Intente nuevamente en unos segundos.",
                        )
                    else:
                        row.count += 1
                        row.updated_at = now

                session.commit()
        except HTTPException:
            raise
        except SQLAlchemyError:
            session.rollback()
            self._check_rate_limit_memory(key, limit, window)
        finally:
            if owns_session and session is not None:
                session.close()

    def _check_rate_limit_memory(self, key: str, limit: int, window: int) -> None:
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

    def ensure_not_locked(self, identifier: str, db: Optional[Session] = None) -> None:
        client = self._get_redis()
        if client is not None:
            try:
                lock_val = client.get(f"compulsa:auth:lock:{identifier}")
                if lock_val:
                    until_ts = float(lock_val)
                    now_ts = time.time()
                    if until_ts > now_ts:
                        remaining = int(until_ts - now_ts) + 1
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f"Cuenta temporalmente bloqueada por múltiples intentos fallidos. Reintente en {remaining}s.",
                        )
                    client.delete(f"compulsa:auth:lock:{identifier}")
                return
            except HTTPException:
                raise
            except redis.RedisError as exc:
                logger.warning("Redis no disponible en lockout check, usando respaldo BD: %s", exc)

        self._ensure_not_locked_db(identifier, db=db)

    def _ensure_not_locked_db(self, identifier: str, db: Optional[Session]) -> None:
        from app.models.telemetry import AuthSecurityCounter

        counter_key = f"lock:{identifier}"
        now = datetime.now(timezone.utc)
        session, owns_session = self._open_db_session(db)
        try:
            with self._lock:
                row = session.execute(
                    sa.select(AuthSecurityCounter).where(
                        AuthSecurityCounter.counter_key == counter_key
                    )
                ).scalar_one_or_none()
                if row and row.blocked_until is not None:
                    blocked_until = _as_utc(row.blocked_until)
                    if blocked_until and blocked_until > now:
                        remaining = int((blocked_until - now).total_seconds()) + 1
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f"Cuenta temporalmente bloqueada por múltiples intentos fallidos. Reintente en {remaining}s.",
                        )
                    row.blocked_until = None
                    row.updated_at = now
                    session.commit()
        except HTTPException:
            raise
        except SQLAlchemyError:
            session.rollback()
            now_mono = time.monotonic()
            with self._lock:
                until = self._lockouts.get(identifier)
                if until and until > now_mono:
                    remaining = int(until - now_mono) + 1
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Cuenta temporalmente bloqueada por múltiples intentos fallidos. Reintente en {remaining}s.",
                    )
                if until and until <= now_mono:
                    self._lockouts.pop(identifier, None)
        finally:
            if owns_session and session is not None:
                session.close()

    def record_failed_attempt(self, identifier: str, db: Optional[Session] = None) -> int:
        threshold = settings.AUTH_LOCKOUT_THRESHOLD
        base_duration = settings.AUTH_LOCKOUT_DURATION_SECONDS

        client = self._get_redis()
        if client is not None:
            try:
                fail_key = f"compulsa:auth:fail:{identifier}"
                attempts = int(client.incr(fail_key))
                max_ttl = base_duration * (2 ** 4)
                client.expire(fail_key, max_ttl)
                if attempts >= threshold:
                    multiplier = 2 ** min(4, attempts - threshold)
                    lock_seconds = base_duration * multiplier
                    until_ts = time.time() + lock_seconds
                    client.set(
                        f"compulsa:auth:lock:{identifier}",
                        str(until_ts),
                        ex=lock_seconds,
                    )
                return attempts
            except redis.RedisError as exc:
                logger.warning("Redis no disponible en failed attempt, usando respaldo BD: %s", exc)

        return self._record_failed_attempt_db(identifier, threshold, base_duration, db=db)

    def _record_failed_attempt_db(
        self,
        identifier: str,
        threshold: int,
        base_duration: int,
        db: Optional[Session],
    ) -> int:
        from app.models.telemetry import AuthSecurityCounter

        counter_key = f"lock:{identifier}"
        now = datetime.now(timezone.utc)
        session, owns_session = self._open_db_session(db)
        try:
            with self._lock:
                stmt = sa.select(AuthSecurityCounter).where(
                    AuthSecurityCounter.counter_key == counter_key
                )
                if session.get_bind().dialect.name == "postgresql":
                    stmt = stmt.with_for_update()
                row = session.execute(stmt).scalar_one_or_none()
                if row is None:
                    attempts = 1
                    blocked_until = (
                        now + timedelta(seconds=base_duration)
                        if attempts >= threshold
                        else None
                    )
                    row = AuthSecurityCounter(
                        counter_key=counter_key,
                        count=attempts,
                        blocked_until=blocked_until,
                        updated_at=now,
                    )
                    session.add(row)
                else:
                    attempts = row.count + 1
                    row.count = attempts
                    row.updated_at = now
                    if attempts >= threshold:
                        multiplier = 2 ** min(4, attempts - threshold)
                        row.blocked_until = now + timedelta(seconds=base_duration * multiplier)
                session.commit()
                return attempts
        except SQLAlchemyError:
            session.rollback()
            now_mono = time.monotonic()
            with self._lock:
                attempts = self._failed_attempts[identifier] + 1
                self._failed_attempts[identifier] = attempts
                if attempts >= threshold:
                    multiplier = 2 ** min(4, attempts - threshold)
                    self._lockouts[identifier] = now_mono + (base_duration * multiplier)
                return attempts
        finally:
            if owns_session and session is not None:
                session.close()

    def clear_failed_attempts(self, identifier: str, db: Optional[Session] = None) -> None:
        client = self._get_redis()
        if client is not None:
            try:
                client.delete(
                    f"compulsa:auth:fail:{identifier}",
                    f"compulsa:auth:lock:{identifier}",
                )
                return
            except redis.RedisError as exc:
                logger.warning("Redis no disponible al limpiar lockouts: %s", exc)

        from app.models.telemetry import AuthSecurityCounter

        session, owns_session = self._open_db_session(db)
        try:
            with self._lock:
                session.execute(
                    sa.delete(AuthSecurityCounter).where(
                        AuthSecurityCounter.counter_key == f"lock:{identifier}"
                    )
                )
                session.commit()
        except SQLAlchemyError:
            session.rollback()
            with self._lock:
                self._failed_attempts.pop(identifier, None)
                self._lockouts.pop(identifier, None)
        finally:
            if owns_session and session is not None:
                session.close()

    def reset(self, db: Optional[Session] = None) -> None:
        with self._lock:
            self._requests.clear()
            self._failed_attempts.clear()
            self._lockouts.clear()

        client = self._get_redis()
        if client is not None:
            try:
                keys = list(client.scan_iter("compulsa:auth:*"))
                if keys:
                    client.delete(*keys)
            except redis.RedisError:
                pass

        from app.models.telemetry import AuthSecurityCounter

        session, owns_session = self._open_db_session(db)
        try:
            with self._lock:
                session.execute(sa.delete(AuthSecurityCounter))
                session.commit()
        except SQLAlchemyError:
            session.rollback()
        finally:
            if owns_session and session is not None:
                session.close()


auth_rate_limiter = AuthRateLimiter()
