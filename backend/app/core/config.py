"""Configuración centralizada y tipada con Pydantic Settings V2."""

import secrets
from typing import List, Literal, Optional, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_KNOWN_SECRETS = {
    "compulsa_super_secret_jwt_key_2026_noa",
    "compulsa_hmac_share_secret_2026_noa",
    "compulsa_obra_jujuy_super_secret_jwt_key_2026_production_ready",
    "compulsa_obra_hmac_share_secret_2026",
    "CHANGE_ME_GENERATE_WITH_OPENSSL_RAND_HEX_32",
    "changeme",
    "secret",
    "supersecret",
    "test-secret",
}

INSECURE_DB_PASSWORDS = ("compulsa_pass", ":postgres@", ":password@", ":changeme@")


def normalize_postgres_url(url: str) -> str:
    """Fuerza el driver psycopg2 en URIs postgres/postgresql genéricas bajo SQLAlchemy 2.1+."""
    raw = str(url).strip()
    if raw.startswith("postgres://"):
        return "postgresql+psycopg2://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg2://" + raw[len("postgresql://") :]
    return raw


class Settings(BaseSettings):
    PROJECT_NAME: str = "CompulsaObra"
    ENVIRONMENT: str = "development"

    # Persistencia Híbrida: SQLite por defecto para dev local y pytest; PostgreSQL en Docker/producción
    DATABASE_URL: str = Field(default="sqlite:///./compulsaobra.db")

    # Seguridad JWT y HMAC (secretos efímeros independientes en memoria para dev/test; obligatorios en producción)
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    HMAC_SHARE_SECRET: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 horas

    # Políticas de seguridad de autenticación (H-22, H-28, H-29, H-33, H-34)
    REQUIRE_EMAIL_VERIFICATION: bool = True
    AUTH_RATE_LIMIT_MAX_REQUESTS: int = 15
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60
    AUTH_LOCKOUT_THRESHOLD: int = 5
    AUTH_LOCKOUT_DURATION_SECONDS: int = 300
    COOKIE_SECURE: Optional[bool] = None

    # Correo electrónico transaccional (H-29)
    EMAIL_BACKEND: Literal["smtp", "memory", "file"] = "memory"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_FROM_EMAIL: str = "no-reply@compulsaobra.local"
    SMTP_FROM_NAME: str = "CompulsaObra"
    EMAIL_VERIFICATION_EXPIRE_MINUTES: int = 60
    EMAIL_RESEND_COOLDOWN_SECONDS: int = 60
    EMAIL_FILE_SINK: str = ""
    FRONTEND_PUBLIC_URL: str = "http://localhost:5174"

    # Almacén compartido para rate limiting / lockouts entre procesos (H-34)
    REDIS_URL: str = Field(default="")

    # Ingesta y Carga de Archivos
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # Ingesta Multimodal (Google GenAI Gemini 2.5 Flash)
    GEMINI_API_KEY: str = Field(default="")

    # CORS
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
    ])

    @property
    def cookie_secure_effective(self) -> bool:
        if self.COOKIE_SECURE is not None:
            return self.COOKIE_SECURE
        return self.ENVIRONMENT.lower() == "production"

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.ENVIRONMENT.lower() == "production":
            if "SECRET_KEY" not in self.model_fields_set:
                raise ValueError("En entorno de producción debe definirse explícitamente SECRET_KEY.")
            if "HMAC_SHARE_SECRET" not in self.model_fields_set:
                raise ValueError("En entorno de producción debe definirse explícitamente HMAC_SHARE_SECRET.")
            if (
                not self.SECRET_KEY.strip()
                or len(self.SECRET_KEY.strip()) < 32
                or self.SECRET_KEY.strip() in INSECURE_KNOWN_SECRETS
            ):
                raise ValueError(
                    "SECRET_KEY inválido para producción: debe tener al menos 32 caracteres y no ser un valor por defecto."
                )
            if (
                not self.HMAC_SHARE_SECRET.strip()
                or len(self.HMAC_SHARE_SECRET.strip()) < 32
                or self.HMAC_SHARE_SECRET.strip() in INSECURE_KNOWN_SECRETS
            ):
                raise ValueError(
                    "HMAC_SHARE_SECRET inválido para producción: debe tener al menos 32 caracteres y no ser un valor por defecto."
                )
            if self.SECRET_KEY == self.HMAC_SHARE_SECRET:
                raise ValueError("En producción SECRET_KEY y HMAC_SHARE_SECRET deben ser distintos.")
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("En entorno de producción no se permite SQLite; utilice PostgreSQL 16.")
            if any(bad in self.DATABASE_URL for bad in INSECURE_DB_PASSWORDS):
                raise ValueError("DATABASE_URL contiene credenciales por defecto inseguras para producción.")
            if not self.REQUIRE_EMAIL_VERIFICATION:
                raise ValueError("En entorno de producción REQUIRE_EMAIL_VERIFICATION debe estar habilitado (true).")
            if self.EMAIL_BACKEND != "smtp" or not self.SMTP_HOST.strip() or not self.SMTP_FROM_EMAIL.strip():
                raise ValueError(
                    "En entorno de producción debe configurarse EMAIL_BACKEND='smtp', SMTP_HOST y SMTP_FROM_EMAIL."
                )
            if not self.REDIS_URL.strip():
                raise ValueError(
                    "En entorno de producción debe configurarse REDIS_URL para el rate limiting compartido."
                )
        return self

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        return normalize_postgres_url(v)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str) and v.startswith("["):
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except Exception:
                pass
        return v if isinstance(v, list) else [str(v)]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
