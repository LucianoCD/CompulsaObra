"""Router maestro de la API v1 de CompulsaObra."""

from fastapi import APIRouter
from app.api.v1.endpoints import auth, vendors, requisitions, comparisons, public

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(vendors.router)
api_router.include_router(requisitions.router)
api_router.include_router(comparisons.router)
api_router.include_router(public.router)
