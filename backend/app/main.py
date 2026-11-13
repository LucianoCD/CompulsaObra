"""Punto de entrada principal de FastAPI para CompulsaObra."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import SessionLocal, run_migrations
from app.core.exceptions import CompulsaDomainException, domain_exception_handler
from app.core.security import (
    AUTH_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    verify_csrf_token,
)
from app.api.v1.router import api_router
from app.services.seed import seed_demo_data_if_needed

_CSRF_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_CSRF_EXEMPT_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/resend-verification",
    "/api/v1/auth/demo-session",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialización de esquema mediante migraciones Alembic y datos semilla ilustrativos de Jujuy (CO-13)
    run_migrations()
    with SessionLocal() as db:
        seed_demo_data_if_needed(db)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="Sistema Inteligente de Elaboración de Presupuestos y Comparación Multi-Negocio de Materiales de Construcción",
    lifespan=lifespan,
)


@app.middleware("http")
async def security_headers_and_csrf_middleware(request: Request, call_next):
    """Valida CSRF Double-Submit Cookie en sesiones basadas en cookie e inyecta cabeceras CSP/seguridad (H-21, H-33)."""
    auth_cookie = request.cookies.get(AUTH_COOKIE_NAME)
    auth_header = request.headers.get("Authorization")
    if (
        request.method.upper() in _CSRF_MUTATING_METHODS
        and request.url.path not in _CSRF_EXEMPT_PATHS
        and auth_cookie
        and not auth_header
    ):
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        csrf_header = request.headers.get(CSRF_HEADER_NAME)
        if not verify_csrf_token(csrf_cookie, csrf_header):
            return JSONResponse(
                status_code=403,
                content={"detail": "Fallo de validación CSRF: falta o no coincide X-CSRF-Token."},
            )

    response = await call_next(request)
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


# Configuración CORS (registrado último para envolver también respuestas de middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Manejadores de excepciones de dominio
app.add_exception_handler(CompulsaDomainException, domain_exception_handler)

# Registro de rutas de API v1
app.include_router(api_router)


@app.get("/health", tags=["Salud"])
def health_check():
    """Endpoint de comprobación de salud del servicio."""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
    }
