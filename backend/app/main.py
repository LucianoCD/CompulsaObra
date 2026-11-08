"""Punto de entrada principal de FastAPI para CompulsaObra."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.core.exceptions import CompulsaDomainException, domain_exception_handler
from app.api.v1.router import api_router
from app.services.seed import seed_demo_data_if_needed


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialización de esquema y datos semilla ilustrativos de Jujuy
    Base.metadata.create_all(bind=engine)
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
