"""Pruebas unitarias de configuración híbrida SQLite / Neon PostgreSQL (pooled + unpooled)."""

from pathlib import Path
from pydantic import ValidationError
import pytest

from app.core.config import _REPO_ROOT_DIR, Settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_neon_pooled_and_unpooled_urls_normalization_and_migrations_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Normaliza DATABASE_URL y DATABASE_URL_UNPOOLED y prioriza unpooled en migraciones Postgres."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_UNPOOLED", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql://user:StrongP4ss!@ep-demo-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require\n"
        "DATABASE_URL_UNPOOLED=postgresql://user:StrongP4ss!@ep-demo.sa-east-1.aws.neon.tech/neondb?sslmode=require\n",
        encoding="utf-8",
    )

    loaded = Settings(_env_file=str(env_file))
    assert loaded.DATABASE_URL.startswith("postgresql+psycopg2://user:StrongP4ss!@ep-demo-pooler.")
    assert loaded.DATABASE_URL_UNPOOLED.startswith("postgresql+psycopg2://user:StrongP4ss!@ep-demo.")
    assert loaded.migrations_database_url == loaded.DATABASE_URL_UNPOOLED

    pooled_only = Settings(
        DATABASE_URL="postgres://user:StrongP4ss!@ep-demo-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require",
        DATABASE_URL_UNPOOLED="",
    )
    assert pooled_only.DATABASE_URL.startswith("postgresql+psycopg2://")
    assert pooled_only.migrations_database_url == pooled_only.DATABASE_URL

    sqlite_override = Settings(
        DATABASE_URL="sqlite:///./local.db",
        DATABASE_URL_UNPOOLED="postgresql://user:StrongP4ss!@ep-demo.sa-east-1.aws.neon.tech/neondb?sslmode=require",
    )
    assert sqlite_override.migrations_database_url == "sqlite:///./local.db"


def test_repo_root_dir_and_unpooled_production_password_guard():
    """Garantiza resolución hacia .env en raíz y rechazo de credenciales inseguras en unpooled."""
    assert _REPO_ROOT_DIR == REPO_ROOT

    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+psycopg2://app:Str0ngP@ss!2026@ep-pooler.neon.tech/neondb",
            DATABASE_URL_UNPOOLED="postgresql+psycopg2://postgres:postgres@ep.neon.tech/neondb",
            REDIS_URL="redis://redis:6379/0",
            SECRET_KEY="a-very-strong-production-jwt-secret-key-32chars",
            HMAC_SHARE_SECRET="b-another-strong-production-hmac-secret-32chars",
            COOKIE_SECURE=True,
            EMAIL_BACKEND="smtp",
            SMTP_HOST="smtp.resend.com",
            SMTP_PORT=587,
            SMTP_USE_TLS=True,
            SMTP_FROM_EMAIL="no-reply@compulsaobra.ar",
            FRONTEND_PUBLIC_URL="https://app.compulsaobra.ar",
        )
