# Especificación Técnica de Despliegue (`DEPLOY_SPEC_OPTION_A.md`) — CompulsaObra

* **Versión del Documento:** `1.0.0`
* **Arquitectura Objetivo:** **Opción A — Nube Híbrida Desacoplada con Proxy Unificado**
  * **Capa de Presentación y Proxy Edge:** Vercel CDN (`frontend/`)
  * **Capa de Aplicación y Motor de Cómputo:** Contenedor Docker en Render o Koyeb (`backend/Dockerfile`)
  * **Capa de Persistencia Relacional:** Neon Serverless PostgreSQL 16 (`pg_trgm` + `unaccent`)
* **Régimen de Operación:** $24 \times 7$ en la nube (100% autónomo, sin dependencia de equipos locales encendidos)
* **Límite de Carga de Archivos:** Hasta $12\text{ MB}$ para catálogos `.xlsx`/`.xls`/`.csv` y fotografías de obra

---

## 1. Resumen Arquitectónico y Topología de Red

El sistema **CompulsaObra** utiliza sesiones autenticadas mediante cookies `HttpOnly` (`compulsa_access_token`) junto con validación CSRF de doble envío (`compulsa_csrf_token` y cabecera `X-CSRF-Token`). Para que los navegadores modernos (especialmente Safari en iOS y Chrome con bloqueo de cookies de terceros) acepten y envíen estas cookies sin rechazos de seguridad, el frontend y el backend deben operar bajo **un único dominio público**.

En el entorno Docker original, esta unificación la realiza `frontend/nginx.conf`. En la **Opción A**, la red global de **Vercel** reemplaza a Nginx mediante reglas de reescritura (`rewrites` en `frontend/vercel.json`), actuando como proxy inverso transparente hacia el contenedor de FastAPI alojado en **Render** o **Koyeb**.

```text
[ Navegador Web / Móvil ] (Tu PC puede estar apagada)
           │
           ▼  HTTPS (Dominio único: https://compulsa-obra.vercel.app)
┌──────────────────────────────────────────────────────────────────────┐
│ VERCEL EDGE NETWORK (Root Directory: frontend/)                      │
│  ├─ Rutas UI (/, /traccion, /p/:token) ──► Sirve SPA React (dist/)   │
│  └─ Rutas API (/api/v1/*, /health)     ──► Proxy transparente HTTPS  │
└──────────────────────────────────────────────────────┬───────────────┘
                                                       │
                                                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│ RENDER / KOYEB WEB SERVICE (Root Directory: backend/)                │
│  ├─ Contenedor Docker (Python 3.12 + FastAPI + Uvicorn + fpdf2)      │
│  ├─ Lifespan Startup: Ejecuta `alembic upgrade head` (0001..0004)    │
│  └─ Lifespan Startup: Ejecuta `seed_demo_data_if_needed()` (Jujuy)   │
└──────────────────────────────────────────────────────┬───────────────┘
                                                       │
                                                       ▼  TLS (psycopg2)
┌──────────────────────────────────────────────────────────────────────┐
│ NEON SERVERLESS POSTGRESQL 16                                        │
│  └─ Extensiones `pg_trgm` y `unaccent` + 10 tablas + telemetría      │
└──────────────────────────────────────────────────────────────────────┘
```

### Ventajas Técnicas de la Opción A
1. **Cero pérdida de datos:** Al utilizar PostgreSQL 16 en Neon en lugar de archivos SQLite efímeros, los presupuestos congelados (`LOCKED_BUDGET`), los tokens públicos firmados con `HMAC-SHA256` (`/p/:token`) y las métricas de `/traccion` persisten indefinidamente.
2. **Soporte completo de archivos pesados ($\le 12\text{ MB}$):** A diferencia de las funciones Serverless puras (limitadas a $4.5\text{ MB}$), el contenedor Docker en Render/Koyeb admite la carga de listas de precios extensas y fotos de remitos de hasta $12\text{ MB}$.
3. **Cookies de primera parte (`SameSite=Lax`):** El usuario nunca interactúa directamente con la URL de Render/Koyeb; todo el tráfico entra por `https://<tu-proyecto>.vercel.app`.

---

## 2. Preparación del Repositorio (Archivos Requeridos)

Antes de conectar el repositorio con los proveedores en la nube, debes asegurarte de incluir un archivo nuevo en `frontend/vercel.json` y verificar el comando de arranque en `backend/Dockerfile`.

### 2.1. Crear `frontend/vercel.json`

Crea el archivo `frontend/vercel.json` reemplazando `https://tu-backend-compulsa.onrender.com` por la URL que te asigne Render o Koyeb en el Paso 4:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "rewrites": [
    {
      "source": "/api/v1/:path*",
      "destination": "https://tu-backend-compulsa.onrender.com/api/v1/:path*"
    },
    {
      "source": "/health",
      "destination": "https://tu-backend-compulsa.onrender.com/health"
    },
    {
      "source": "/((?!assets/|favicon\\.svg).*)",
      "destination": "/index.html"
    }
  ]
}
```

> **Nota sobre el orden de reglas:** Vercel evalúa `rewrites` de arriba hacia abajo. Las peticiones a `/api/v1/*` y `/health` se redirigen al contenedor FastAPI, los archivos estáticos (`/assets/*` y `/favicon.svg`) se sirven directamente desde el CDN, y cualquier ruta de navegación (`/traccion`, `/p/:token`, `/verificar-correo`) entrega `/index.html` para que el router SPA de `App.tsx` tome el control sin arrojar error `404`.

### 2.2. Verificar puerto dinámico en `backend/Dockerfile`

Plataformas como Render y Koyeb inyectan una variable de entorno `$PORT` en tiempo de ejecución. Verifica que la última línea de `backend/Dockerfile` utilice la forma shell para respetar `${PORT:-8000}`:

```dockerfile
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

---

## 3. Paso 1: Base de Datos Persistente en Neon.tech (PostgreSQL 16)

1. Ingresa a [Neon.tech](https://neon.tech) y crea una cuenta gratuita (puedes autenticarte con tu cuenta de GitHub).
2. Crea un nuevo proyecto con los siguientes parámetros:
   * **Project Name:** `compulsa-obra-db`
   * **Postgres Version:** `16`
   * **Region:** Elige la misma región donde alojarás el backend en Render/Koyeb (por ejemplo, `US East (Ohio)` o `US East (N. Virginia)` para minimizar la latencia entre el backend y la base de datos).
3. En el panel principal (**Dashboard** de Neon), copia la cadena de conexión (**Connection string**) asegurándote de que tenga activado el parámetro SSL:
   ```text
   postgresql://neondb_owner:TuPasswordNeon@ep-ejemplo-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
4. **Inicialización automática:** No necesitas ejecutar scripts SQL manuales. El validador `normalize_database_url` en `backend/app/core/config.py` convierte automáticamente el esquema `postgresql://` a `postgresql+psycopg2://`, y al encender el backend por primera vez ejecutará `0001_initial_schema.py` (creando las extensiones `pg_trgm` y `unaccent`), aplicará hasta la migración `0004_audit_h37_h39.py` y cargará los 3 corralones semilla de Jujuy (`Corralón El Pórtico`, `Ferretería Industrial Cuyaya` y `Sanitarios y Materiales Palpalá`).

---

## 4. Paso 2: Despliegue del Backend Docker en Render (o Koyeb)

1. Ingresa a [Render.com](https://render.com) (o [Koyeb.com](https://www.koyeb.com)) con tu cuenta de GitHub.
2. Haz clic en **New +** $\rightarrow$ **Web Service** y selecciona tu repositorio de **CompulsaObra**.
3. Configura los parámetros de construcción del servicio:
   * **Name:** `compulsa-obra-backend`
   * **Root Directory:** `backend` *(Importante: especifica `backend` para que lea `backend/Dockerfile` y `backend/pyproject.toml`)*.
   * **Runtime / Environment:** `Docker`
   * **Instance Type:** `Free`
   * **Health Check Path:** `/health`

### 4.1. Configuración de Variables de Entorno del Backend

El backend de CompulsaObra cuenta con validaciones de seguridad estrictas en `backend/app/core/config.py`. Puedes elegir entre **dos perfiles de configuración** según el propósito de tu despliegue:

#### Perfil A1 (Recomendado para Despliegue Rápido / Demo y Evaluación sin Redis ni SMTP externo)
Este perfil utiliza `ENVIRONMENT=development` sobre PostgreSQL de Neon. Permite que el limitador de tasa utilice automáticamente la tabla transaccional `auth_security_counters` en PostgreSQL (sin requerir un servidor Redis externo) y permite crear cuentas o usar el **Workspace Demo Jujuy** sin exigir verificación de correo por SMTP externo, manteniendo igualmente las cookies seguras (`COOKIE_SECURE=true`) para HTTPS:

| Variable | Valor a configurar en Render / Koyeb |
| :--- | :--- |
| `ENVIRONMENT` | `development` |
| `DATABASE_URL` | `postgresql://neondb_owner:...@ep-...neon.tech/neondb?sslmode=require` *(tu URI de Neon)* |
| `SECRET_KEY` | Genera una cadena aleatoria de $\ge 32$ caracteres (ej. `c9f8e7d6b5a4_compulsa_jwt_secret_key_2026_noa_jujuy`) |
| `HMAC_SHARE_SECRET` | Genera otra cadena distinta de $\ge 32$ caracteres (ej. `a1b2c3d4e5f6_compulsa_hmac_share_secret_2026_jujuy`) |
| `COOKIE_SECURE` | `true` |
| `REQUIRE_EMAIL_VERIFICATION` | `false` |
| `EMAIL_BACKEND` | `memory` |
| `FRONTEND_PUBLIC_URL` | `https://tu-proyecto.vercel.app` *(la URL final de tu proyecto en Vercel)* |
| `CORS_ORIGINS` | `["https://tu-proyecto.vercel.app"]` |
| `GEMINI_API_KEY` | *(Opcional)* Tu API Key de Google AI Studio para habilitar lectura de fotos manuscritas |

#### Perfil A2 (Producción Endurecida — Cumple validaciones H-18, H-37 y H-38)
Si deseas operar con `ENVIRONMENT=production`, el validador `Settings.validate_production_secrets` exige obligatoriamente una instancia Redis (puedes crear una gratis en [Upstash.com](https://upstash.com)) y un servidor SMTP real (puedes crear una cuenta gratuita en [Resend.com](https://resend.com)):

| Variable | Valor a configurar en Render / Koyeb |
| :--- | :--- |
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql://neondb_owner:...@ep-...neon.tech/neondb?sslmode=require` |
| `REDIS_URL` | `rediss://default:TuPasswordUpstash@tu-instancia.upstash.io:6379` |
| `SECRET_KEY` | Cadena criptográfica única de $\ge 32$ caracteres |
| `HMAC_SHARE_SECRET` | Cadena criptográfica única distinta de `SECRET_KEY` de $\ge 32$ caracteres |
| `COOKIE_SECURE` | `true` |
| `REQUIRE_EMAIL_VERIFICATION` | `true` |
| `EMAIL_BACKEND` | `smtp` |
| `SMTP_HOST` | `smtp.resend.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USE_TLS` | `true` |
| `SMTP_USE_SSL` | `false` |
| `SMTP_USER` | `resend` |
| `SMTP_PASSWORD` | `re_TuApiKeyDeResend` |
| `SMTP_FROM_EMAIL` | `no-reply@tudominioverificado.com` |
| `FRONTEND_PUBLIC_URL` | `https://tu-proyecto.vercel.app` |
| `CORS_ORIGINS` | `["https://tu-proyecto.vercel.app"]` |
| `GEMINI_API_KEY` | *(Opcional)* Tu API Key de Google AI Studio |

4. Haz clic en **Create Web Service**. Una vez finalizado el build de Docker, copia la URL pública del servicio (por ejemplo, `https://compulsa-obra-backend.onrender.com`) y comprueba que al abrir `https://compulsa-obra-backend.onrender.com/health` en el navegador responda:
   ```json
   {"status":"healthy","project":"CompulsaObra","environment":"development"}
   ```

---

## 5. Paso 3: Despliegue del Frontend SPA en Vercel

1. Asegúrate de que el archivo `frontend/vercel.json` (creado en la Sección 2.1) tenga la URL exacta de tu backend de Render/Koyeb en la propiedad `destination` y sube el cambio a GitHub (`git commit` y `git push`).
2. Ingresa a [Vercel.com](https://vercel.com) con tu cuenta de GitHub y haz clic en **Add New...** $\rightarrow$ **Project**.
3. Importa el repositorio de **CompulsaObra** y configura los siguientes ajustes en la pantalla de configuración:
   * **Project Name:** `compulsa-obra`
   * **Framework Preset:** `Vite`
   * **Root Directory:** Haz clic en **Edit** y selecciona `frontend`.
   * **Build and Output Settings:**
     * **Build Command:** `npm run build`
     * **Output Directory:** `dist`
     * **Install Command:** `npm install`
4. No necesitas cargar variables de entorno secretas en Vercel, ya que el cliente HTTP (`frontend/src/services/apiClient.ts`) apunta a rutas relativas (`BASE_URL = '/api/v1'`) que Vercel redirige internamente hacia el backend.
5. Haz clic en **Deploy**. En aproximadamente $45\text{ segundos}$ Vercel publicará tu aplicación en un dominio `https://compulsa-obra.vercel.app`.
6. Si el nombre del dominio asignado por Vercel difiere del que pusiste provisionalmente en `FRONTEND_PUBLIC_URL` y `CORS_ORIGINS` dentro de Render/Koyeb, actualiza esas dos variables en Render/Koyeb con la URL definitiva de Vercel.

---

## 6. Paso 4: Configuración de Vigilia $24 \times 7$ (Evitar hibernación con tu PC apagada)

Los servicios gratuitos de contenedores en Render entran en modo de reposo (*spin down*) tras $15\text{ minutos}$ sin recibir tráfico, demorando entre $30\text{ y }50\text{ segundos}$ en responder a la primera visita posterior. Para mantener el contenedor activo las 24 horas de forma gratuita y sin depender de tu computadora:

1. Crea una cuenta gratuita en [Cron-job.org](https://cron-job.org) o [UptimeRobot.com](https://uptimerobot.com).
2. Crea un nuevo monitor / tarea programada con estos datos:
   * **Title:** `CompulsaObra Keep-Alive`
   * **URL:** `https://tu-proyecto.vercel.app/health` *(al pasar por el rewrite de Vercel, mantiene activo tanto el enlace de proxy como el contenedor FastAPI en Render)*.
   * **Schedule / Interval:** Cada **10 minutos** ($6\text{ ejecuciones por hora}$).
   * **Request Method:** `GET`
3. Guarda y activa el monitor. Como el endpoint `/health` en `backend/app/main.py` devuelve un JSON estático en menos de $5\text{ ms}$ sin abrir conexiones a la base de datos de Neon, este pulso mantiene encendido el contenedor de FastAPI permanentemente sin consumir horas de cómputo innecesarias en la base de datos.

---

## 7. Lista de Verificación Post-Despliegue (Smoke Test)

Una vez completados los pasos anteriores, puedes apagar tu computadora y verificar desde cualquier teléfono móvil o navegador en modo incógnito los siguientes puntos:

- [ ] **Salud del Proxy e Infraestructura:** Al navegar a `https://<tu-proyecto>.vercel.app/health` se visualiza `{"status":"healthy","project":"CompulsaObra",...}`.
- [ ] **Sesión Demo Automática y Cookies Seguras:** Al ingresar a `https://<tu-proyecto>.vercel.app/`, la barra superior muestra **"Modo Exploración · 3 corralones de Jujuy"** y en las herramientas de desarrollador (*Application $\rightarrow$ Cookies*) aparecen `compulsa_access_token` (`HttpOnly`, `Secure`) y `compulsa_csrf_token`.
- [ ] **Ingesta y Desambiguación HITL:** Al pulsar el botón **Manuscrito de Obra (Guardia HITL)** en el Paso 1, la tabla del Paso 2 solicita definir el material para `4 caño de 3/4` y permite elegir `PVC Cloacal / Agua`.
- [ ] **Compulsa, Lock-Budget y PDF:** Al pulsar **Ejecutar Compulsa Multi-Corralón** y luego **Congelar Presupuesto Definitivo (Lock-Budget)**, el botón **PDF Cliente** descarga un archivo `%PDF-1.` válido.
- [ ] **Rutas SPA y Enlace Público Inmutable:** Al abrir el enlace copiado `/p/<token>` o recargar directamente `https://<tu-proyecto>.vercel.app/traccion` con `F5`, Vercel sirve la aplicación React sin errores `404` y exhibe el sello `Snapshot Inmutable HMAC-SHA256 Verificado`.
