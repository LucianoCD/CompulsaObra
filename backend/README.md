# CompulsaObra — Backend API

API REST construida con **FastAPI 0.115+**, **SQLAlchemy 2.0** y **Pydantic v2** para la normalización dimensional de pedidos de materiales, compulsa multi-negocio de corralones, optimización de compra dividida (Branch-and-Bound con precisión `Decimal`), simulación de acopio y generación de presupuestos PDF firmados con HMAC-SHA256.

## Requisitos
- Python 3.12+
- PostgreSQL 16 (producción / Docker, con extensiones `pg_trgm` y `unaccent`) o SQLite (desarrollo local y pruebas automatizadas).
- Redis 7 (rate limiting y bloqueo distribuidos en producción, con respaldo transaccional `auth_security_counters` en SQL).

## Instalación en modo editable

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Variables de Entorno Clave
- `ENVIRONMENT`: `development` | `production` (en `production` exige `SECRET_KEY`, `HMAC_SHARE_SECRET` distintos entre sí de al menos 32 caracteres, PostgreSQL, `REDIS_URL`, `REQUIRE_EMAIL_VERIFICATION=true`, `EMAIL_BACKEND=smtp`, `SMTP_HOST` y `SMTP_FROM_EMAIL`).
- `DATABASE_URL`: cadena de conexión SQLAlchemy 2.0.
- `REDIS_URL`: URI Redis para rate limiter y bloqueo progresivo distribuido.
- `SECRET_KEY`: clave secreta para firma JWT en cookies `HttpOnly`.
- `HMAC_SHARE_SECRET`: clave independiente para firma HMAC-SHA256 de enlaces y snapshots públicos.
- `COOKIE_SECURE`: bandera `Secure` de cookies de sesión y CSRF.
- `EMAIL_BACKEND`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, `FRONTEND_PUBLIC_URL`: transporte SMTP real (Mailpit incluido en `docker-compose.yml`), expiración (`EMAIL_VERIFICATION_EXPIRE_MINUTES`) y cooldown de reenvío (`EMAIL_RESEND_COOLDOWN_SECONDS`).
- `GEMINI_API_KEY`: clave opcional para extracción multimodal de imágenes con Gemini 2.5 Flash.

## Migraciones y Verificación

```bash
# Aplicar migraciones
alembic upgrade head

# Linter estático
python -m ruff check .

# Suite de pruebas completa
python -m pytest -v
```
