"""Servicio de envío transaccional de correos de verificación (H-22, H-29)."""

from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
import hashlib
import json
import logging
from pathlib import Path
import smtplib
import ssl
from threading import Lock
from typing import List, Optional
from urllib.parse import quote_plus

from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(HTTPException):
    """Error 503 cuando el proveedor SMTP no puede entregar el correo de verificación."""

    def __init__(self, detail: str = "No se pudo enviar el correo de verificación en este momento."):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )


@dataclass(frozen=True)
class SentEmailRecord:
    """Registro estructurado de correo emitido (para auditoría en memoria/archivo en tests)."""

    recipient: str
    subject: str
    verification_token: str
    verification_url: str
    workspace_name: str
    expires_minutes: int
    sent_at: str


def hash_verification_token(raw_token: str) -> str:
    """Genera el digest SHA-256 hex (64 chars) para almacenar tokens sin texto plano en BD."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


class EmailService:
    """Despachador transaccional SMTP con backends memory/file para pruebas automatizadas."""

    _lock = Lock()
    _memory_outbox: List[SentEmailRecord] = []

    @classmethod
    def clear_outbox(cls) -> None:
        with cls._lock:
            cls._memory_outbox.clear()
        if settings.EMAIL_FILE_SINK.strip():
            sink = Path(settings.EMAIL_FILE_SINK.strip())
            if sink.exists():
                try:
                    sink.unlink()
                except OSError:
                    pass

    @classmethod
    def get_outbox(cls, recipient: Optional[str] = None) -> List[SentEmailRecord]:
        with cls._lock:
            records = list(cls._memory_outbox)
        if recipient:
            norm = recipient.strip().lower()
            records = [r for r in records if r.recipient.lower() == norm]
        return records

    @classmethod
    def build_verification_url(cls, recipient_email: str, verification_token: str) -> str:
        base = settings.FRONTEND_PUBLIC_URL.rstrip("/")
        return (
            f"{base}/verificar-correo"
            f"?email={quote_plus(recipient_email)}&token={quote_plus(verification_token)}"
        )

    @classmethod
    def send_verification_email(
        cls,
        *,
        recipient_email: str,
        verification_token: str,
        workspace_name: str,
        expires_minutes: int,
    ) -> SentEmailRecord:
        verification_url = cls.build_verification_url(recipient_email, verification_token)
        subject = "Verificá tu correo en CompulsaObra"
        sent_at = datetime.now(timezone.utc).isoformat()
        record = SentEmailRecord(
            recipient=recipient_email,
            subject=subject,
            verification_token=verification_token,
            verification_url=verification_url,
            workspace_name=workspace_name,
            expires_minutes=expires_minutes,
            sent_at=sent_at,
        )

        backend = settings.EMAIL_BACKEND
        if backend == "smtp":
            cls._send_via_smtp(record)
        elif backend == "memory":
            with cls._lock:
                cls._memory_outbox.append(record)
            if settings.EMAIL_FILE_SINK.strip():
                cls._append_to_file_sink(record)
        elif backend == "file":
            if settings.ENVIRONMENT.lower() == "production":
                raise EmailDeliveryError("Backend de correo 'file' no permitido en producción.")
            cls._append_to_file_sink(record)
        else:
            raise EmailDeliveryError(f"Backend de correo no soportado: {backend}")

        return record

    @classmethod
    def _build_mime_message(cls, record: SentEmailRecord) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = record.subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = record.recipient
        msg["X-Compulsa-Token"] = record.verification_token

        text_body = (
            f"Hola,\n\n"
            f"Recibimos el registro del espacio de trabajo '{record.workspace_name}' en CompulsaObra.\n"
            f"Para activar tu cuenta y operar presupuestos privados, verificá tu correo en el siguiente enlace "
            f"(válido durante {record.expires_minutes} minutos):\n\n"
            f"{record.verification_url}\n\n"
            f"Código de verificación manual: {record.verification_token}\n\n"
            f"Si no solicitaste esta cuenta, podés ignorar este mensaje.\n"
        )
        msg.set_content(text_body)
        return msg

    @classmethod
    def _send_via_smtp(cls, record: SentEmailRecord) -> None:
        if not settings.SMTP_HOST.strip():
            raise EmailDeliveryError("SMTP_HOST no está configurado para envío de verificación.")
        mime_msg = cls._build_mime_message(record)
        try:
            if settings.SMTP_USE_SSL:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    settings.SMTP_HOST,
                    settings.SMTP_PORT,
                    timeout=10,
                    context=context,
                ) as server:
                    if settings.SMTP_USER.strip():
                        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(mime_msg)
            else:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                    server.ehlo()
                    if settings.SMTP_USE_TLS:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                        server.ehlo()
                    if settings.SMTP_USER.strip():
                        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(mime_msg)
        except Exception as exc:
            logger.exception("Error enviando correo SMTP a %s: %s", record.recipient, exc)
            raise EmailDeliveryError(
                "No pudimos entregar el correo de verificación al servidor SMTP. Reintentá en unos instantes."
            ) from exc

    @classmethod
    def _append_to_file_sink(cls, record: SentEmailRecord) -> None:
        sink_path = settings.EMAIL_FILE_SINK.strip()
        if not sink_path:
            raise EmailDeliveryError("EMAIL_FILE_SINK no está configurado.")
        path = Path(sink_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "recipient": record.recipient,
            "subject": record.subject,
            "verification_token": record.verification_token,
            "verification_url": record.verification_url,
            "workspace_name": record.workspace_name,
            "expires_minutes": record.expires_minutes,
            "sent_at": record.sent_at,
        }
        with cls._lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
