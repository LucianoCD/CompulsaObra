"""Excepciones de dominio y manejadores HTTP deterministas."""

from fastapi import Request, status
from fastapi.responses import JSONResponse


class CompulsaDomainException(Exception):
    """Base para todas las excepciones de dominio del sistema."""
    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class AmbiguousItemCannotBeMatchedError(CompulsaDomainException):
    """Lanzada cuando matching_engine recibe un ítem con completeness == 'missing_critical_attribute'."""
    def __init__(self, item_id: str, message: str = "El ítem requiere aclaración técnica previa al emparejamiento."):
        super().__init__(message=f"{message} (item_id: {item_id})", code="AMBIGUOUS_ITEM_BLOCKED")
        self.item_id = item_id


class DimensionMismatchOverrideError(CompulsaDomainException):
    """Lanzada cuando un override manual viola la dimensión física sin force_override."""
    def __init__(self, message: str = "El producto seleccionado viola la dimensión física solicitada."):
        super().__init__(message=message, code="DIMENSION_MISMATCH")


class LockedBudgetModificationError(CompulsaDomainException):
    """Lanzada cuando se intenta alterar una requisición o compulsa congelada (LOCKED_BUDGET)."""
    def __init__(self, message: str = "El presupuesto está congelado (LOCKED_BUDGET) y no admite modificaciones."):
        super().__init__(message=message, code="LOCKED_BUDGET_IMMUTABLE")


class MultimodalExtractionUnavailableError(CompulsaDomainException):
    """Lanzada cuando la extracción multimodal no está disponible o falla sin inventar datos."""
    def __init__(self, message: str = "El servicio de extracción multimodal no está disponible."):
        super().__init__(message=message, code="MULTIMODAL_EXTRACTION_UNAVAILABLE")


class WorkspaceIsolationError(CompulsaDomainException):
    """Lanzada ante intentos de acceso o mutación cruzada entre workspaces."""
    def __init__(self, message: str = "Acceso denegado: el recurso no pertenece al workspace activo."):
        super().__init__(message=message, code="WORKSPACE_ISOLATION_VIOLATION")


class CatalogImportValidationError(CompulsaDomainException):
    """Lanzada cuando el archivo de lista de precios no cumple los requisitos mínimos."""
    def __init__(self, message: str = "Error en la estructura o validación del catálogo importado."):
        super().__init__(message=message, code="CATALOG_IMPORT_INVALID")


async def domain_exception_handler(request: Request, exc: CompulsaDomainException) -> JSONResponse:
    status_code = status.HTTP_400_BAD_REQUEST
    if isinstance(exc, WorkspaceIsolationError):
        status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, LockedBudgetModificationError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, (DimensionMismatchOverrideError, AmbiguousItemCannotBeMatchedError)):
        status_code = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
    elif isinstance(exc, MultimodalExtractionUnavailableError):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
    )
