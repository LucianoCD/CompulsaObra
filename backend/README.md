# CompulsaObra — Backend API

API REST construida con **FastAPI 0.115+**, **SQLAlchemy 2.0** y **Pydantic v2** para la normalización dimensional de pedidos de materiales, compulsa multi-negocio de corralones, optimización de compra dividida (Branch-and-Bound con precisión `Decimal`), simulación de acopio y generación de presupuestos PDF firmados con HMAC-SHA256.

## Requisitos
- Python 3.12+
- PostgreSQL 16 (producción / Docker, con extensiones `pg_trgm` y `unaccent`) o SQLite (desarrollo local y pruebas automatizadas).

## Instalación en modo editable

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Variables de Entorno Clave
- `ENVIRONMENT`: `development` | `production` (en `production` exige `SECRET_KEY`, `HMAC_SHARE_SECRET` distintos entre sí de al menos 32 caracteres y base PostgreSQL).
- `DATABASE_URL`: cadena de conexión SQLAlchemy 2.0.
- `SECRET_KEY`: clave secreta para firma JWT.
- `HMAC_SHARE_SECRET`: clave independiente para firma HMAC-SHA256 de enlaces y snapshots públicos.
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
