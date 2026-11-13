# CompulsaObra (`compulsa-obra`)

Plataforma inteligente de elaboración de presupuestos y compulsa multi-negocio de materiales de construcción para estudios, presupuestadores profesionales (`ESTIMATOR`) y compradores finales (`BUYER`) del NOA (San Salvador de Jujuy, Palpalá, Perico y El Carmen).

---

## Arquitectura del Sistema

- **Backend (`backend/`)**: API REST en Python 3.12+ / FastAPI, validación estricta con Pydantic v2, persistencia SQLAlchemy 2.0 (PostgreSQL 16 con `pg_trgm`, `unaccent` y `TSVECTOR` en producción/Docker; SQLite en testing), migraciones Alembic, extracción multimodal opcional vía Google GenAI (`gemini-2.5-flash`), importación incremental `.xlsx`/`.xls`/`.csv` con `openpyxl` + `xlrd` y generación de PDFs vectoriales con `fpdf2`. Ver [backend/README.md](backend/README.md).
- **Frontend (`frontend/`)**: SPA/PWA en React 18 + TypeScript 5 (`strict: true`, cero `any`) + Vite + Zustand + Tailwind CSS, con sistema visual técnico *Industrial Utilitarian & Swiss Technical Grid* y accesibilidad WCAG 2.2 AA.

## Invariantes Técnicos y de Seguridad

1. **Normalización Física vs. Nominal por Familia**: Diferencia pulgadas nominales comerciales según familia de material (p. ej. `PVC 4"` $\rightarrow$ `110.0 mm` vs. `Acero 4"` $\rightarrow$ `101.6 mm`, y `Termofusión 3/4"` compatible con `19.05 mm` / `20.0 mm`).
2. **Guardia Dimensional HITL y Filtro Duro SQL**: Bloquea cualquier ítem con atributos críticos faltantes antes de cotizar y aplica tolerancias estrictas en SQL (`diameter_mm`, `length_m`, `weight_kg`, `material_type`) más umbrales de confianza y desempate para evitar sustituciones ciegas.
3. **Unidades Comerciales y Precisión Decimal**: Convierte unidades solicitadas frente a presentaciones de venta (`ROLLO`, `BARRA`, `BOLSA`, etc.) con redondeo seguro (`math.ceil`) y aritmética financiera exacta en `Decimal` (`ROUND_HALF_UP`).
4. **Optimizador Branch-and-Bound y Consistencia de Estrategia**: Evalúa compra en Proveedor Único vs. Carrito Dividido (*Split Cart*) considerando fletes únicos por comercio, propagando la estrategia elegida de forma consistente hacia el congelamiento (`LOCKED_BUDGET`), vista pública y generación de PDFs.
5. **Presupuestos Inmutables y Firma HMAC-SHA256**: Al congelar (`lock-budget`), se sellan en el snapshot bloqueado el título, cliente, estrategia, importes congelados y timestamp (`is_locked`, `locked_snapshot_hash`). El enlace público `/api/v1/public/comparisons/{token}` prohíbe sobreescrituras por `?strategy=`/`?mode=`, expone únicamente el DTO whitelist `PublicClientBudgetResponse` y verifica la firma HMAC sobre el hash completo del snapshot.
6. **Seguridad Web y Operación**: Sesiones web exclusivas mediante cookies `HttpOnly` (`SameSite=Lax`, sin JWT en JSON ni en `localStorage`) protegidas con Double-Submit CSRF (`compulsa_csrf_token` / `X-CSRF-Token`), rate limiting y lockout distribuidos en Redis (con respaldo transaccional `SELECT ... FOR UPDATE` en PostgreSQL `auth_security_counters`), verificación obligatoria de correo vía SMTP con tokens SHA-256 con expiración y reenvío con cooldown (`Mailpit` en Docker), proxy inverso Nginx `/api/v1/` $\rightarrow$ `backend:8000`, y métricas auditadas en `/traccion` basadas en usuarios verificados, presupuestos congelados (`is_locked`) y tabla `traction_events`.

---

## Puesta en Marcha

### 1. Despliegue con Docker Compose (Producción)

Configura tus variables a partir de [`.env.example`](.env.example) con secretos criptográficos fuertes y ejecuta:

```bash
docker compose up --build -d
```

### 2. Entorno de Desarrollo con Docker Override

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

### 3. Desarrollo Local Directo (SQLite + Vite)

```bash
# Backend
cd backend
python -m pip install -e .
python -m uvicorn app.main:app --port 8001 --reload

# Frontend (en otra terminal)
cd frontend
npm install
npm run dev
```

La interfaz local se expone en `http://localhost:5174` con proxy `/api/v1` hacia `http://127.0.0.1:8001`.

---

## Verificación y Pruebas Automatizadas

```bash
# 1. Empaquetado y modelos Backend
cd backend
python -m pip install --no-build-isolation --no-deps -e .
python -c "from app.models import Workspace, Vendor, PriceList, VendorProduct, Requisition, ComparisonRun; print('MODELS_OK')"

# 2. Lint y suite completa Pytest (E2E-01..E2E-05, CO-01..CO-16 y H-01..H-36)
python -m ruff check .
python -m pytest -v

# 2b. Integración real PostgreSQL 16 + Alembic + Redis 7 (requiere TEST_POSTGRES_URL)
TEST_POSTGRES_URL="postgresql://compulsa_test:StrongTestPass2026@127.0.0.1:5432/compulsa_test" \
REDIS_URL="redis://127.0.0.1:6379/0" \
python -m pytest tests/test_postgres_integration.py -v

# 3. Typecheck estricto, build de producción y E2E Playwright Frontend
cd ../frontend
npm run typecheck && npm run build && npm run test:e2e
```
