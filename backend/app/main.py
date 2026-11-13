"""Punto de entrada principal de FastAPI para CompulsaObra."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import SessionLocal, run_migrations
from app.core.exceptions import CompulsaDomainException, domain_exception_handler
from app.api.v1.router import api_router
from app.services.seed import seed_demo_data_if_needed


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

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Agrega cabeceras de endurecimiento CSP y defensa XSS en todas las respuestas (H-21)."""
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
