"""Endpoints para gestión de Comercios, Reglas de Acopio e Importación de Catálogos."""

import uuid
import json
from decimal import Decimal
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.security import read_upload_file_bounded
from app.models.workspace import Workspace
from app.models.vendor import Vendor, PriceList, VendorProduct
from app.schemas.vendor import (
    VendorCreateRequest,
    VendorResponse,
    ColumnMappingSchema,
    CatalogImportSummary,
    VendorProductResponse,
)
from app.api.deps import get_current_workspace
from app.services.catalog_importer import CatalogImporterService
from app.services.traction_service import record_traction_event

router = APIRouter(prefix="/vendors", tags=["Comercios y Catálogos"])


@router.get("", response_model=List[VendorResponse])
def list_vendors(
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Lista los comercios asociados al workspace y los del directorio público."""
    vendors = db.scalars(
        select(Vendor)
        .where(or_(Vendor.workspace_id == current_ws.id, Vendor.is_public_directory.is_(True)))
        .order_by(Vendor.created_at.asc())
    ).all()

    return [
        VendorResponse(
            id=v.id,
            workspace_id=v.workspace_id,
            name=v.name,
            locality=v.locality,
            whatsapp_phone=v.whatsapp_phone,
            is_public_directory=v.is_public_directory,
            cash_discount_pct=float(v.cash_discount_pct),
            estimate_delivery_fee_ars=float(v.estimate_delivery_fee_ars),
            acopio_config_json=v.acopio_config_json,
            created_at=v.created_at,
        )
        for v in vendors
    ]


@router.post("", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
def create_vendor(
    payload: VendorCreateRequest,
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Registra un nuevo comercio o corralón en el espacio de trabajo."""
    acopio_dict = payload.acopio_config.model_dump() if payload.acopio_config else {
        "enabled": False,
        "min_down_payment_pct": 100.0,
        "freeze_days": 30,
        "max_withdrawal_days": 60,
        "min_notice_hours": 24,
    }

    vendor = Vendor(
        id=uuid.uuid4(),
        workspace_id=current_ws.id,
        name=payload.name,
        locality=payload.locality,
        whatsapp_phone=payload.whatsapp_phone,
        is_public_directory=False,
        cash_discount_pct=Decimal(str(payload.cash_discount_pct)),
        estimate_delivery_fee_ars=Decimal(str(payload.estimate_delivery_fee_ars)),
        acopio_config_json=acopio_dict,
    )
    db.add(vendor)
    db.commit()

    return VendorResponse(
        id=vendor.id,
        workspace_id=vendor.workspace_id,
        name=vendor.name,
        locality=vendor.locality,
        whatsapp_phone=vendor.whatsapp_phone,
        is_public_directory=vendor.is_public_directory,
        cash_discount_pct=float(vendor.cash_discount_pct),
        estimate_delivery_fee_ars=float(vendor.estimate_delivery_fee_ars),
        acopio_config_json=vendor.acopio_config_json,
        created_at=vendor.created_at,
    )


@router.get("/{vendor_id}", response_model=VendorResponse)
def get_vendor_detail(
    vendor_id: uuid.UUID,
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Obtiene el detalle comercial y configuración de acopio de un negocio."""
    vendor = db.scalar(
        select(Vendor).where(
            Vendor.id == vendor_id,
            or_(Vendor.workspace_id == current_ws.id, Vendor.is_public_directory.is_(True)),
        )
    )
    if not vendor:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")

    return VendorResponse(
        id=vendor.id,
        workspace_id=vendor.workspace_id,
        name=vendor.name,
        locality=vendor.locality,
        whatsapp_phone=vendor.whatsapp_phone,
        is_public_directory=vendor.is_public_directory,
        cash_discount_pct=float(vendor.cash_discount_pct),
        estimate_delivery_fee_ars=float(vendor.estimate_delivery_fee_ars),
        acopio_config_json=vendor.acopio_config_json,
        created_at=vendor.created_at,
    )


@router.get("/{vendor_id}/products", response_model=List[VendorProductResponse])
def get_vendor_active_products(
    vendor_id: uuid.UUID,
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Lista los productos de la versión activa de precios de un comercio."""
    vendor = db.scalar(
        select(Vendor).where(
            Vendor.id == vendor_id,
            or_(Vendor.workspace_id == current_ws.id, Vendor.is_public_directory.is_(True)),
        )
    )
    if not vendor:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")

    active_pl = db.scalar(
        select(PriceList)
        .where(PriceList.vendor_id == vendor.id, PriceList.is_active.is_(True))
        .order_by(PriceList.version_number.desc(), PriceList.created_at.desc())
        .limit(1)
    )
    if not active_pl:
        return []

    prods = db.scalars(
        select(VendorProduct).where(VendorProduct.price_list_id == active_pl.id)
    ).all()

    return [
        VendorProductResponse(
            id=p.id,
            sku=p.sku,
            raw_description=p.raw_description,
            normalized_description=p.normalized_description,
            brand=p.brand,
            brand_tier=p.brand_tier,
            category=p.category,
            sale_unit=p.sale_unit,
            price_cash_ars=float(p.price_cash_ars),
            price_list_ars=float(p.price_list_ars),
            stock_available=p.stock_available,
            diameter_mm=float(p.diameter_mm) if p.diameter_mm is not None else None,
            length_m=float(p.length_m) if p.length_m is not None else None,
            weight_kg=float(p.weight_kg) if p.weight_kg is not None else None,
            material_type=p.material_type,
            row_sha256=p.row_sha256,
        )
        for p in prods
    ]


@router.post("/{vendor_id}/catalogs/import", response_model=CatalogImportSummary)
async def import_vendor_catalog(
    vendor_id: uuid.UUID,
    file: UploadFile = File(...),
    mapping_json: str = Form(default="{}"),
    current_ws: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Importa una lista de precios .xlsx o .csv con deduplicación incremental SHA-256."""
    file_bytes = await read_upload_file_bounded(file, settings.MAX_UPLOAD_SIZE_BYTES)
    if not file_bytes:
        raise HTTPException(status_code=400, detail="El archivo enviado está vacío")

    vendor = db.scalar(select(Vendor).where(Vendor.id == vendor_id))
    if not vendor:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")

    # Invariante SEC-02: Prohibir sobrescritura sobre el directorio público o comercios ajenos
    if vendor.is_public_directory or vendor.workspace_id != current_ws.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: solo puede importar listas de precios sobre comercios propios de su espacio de trabajo.",
        )

    mapping = ColumnMappingSchema()
    if mapping_json and mapping_json.strip() and mapping_json.strip() != "{}":
        try:
            mapping_dict = json.loads(mapping_json)
            mapping = ColumnMappingSchema(**mapping_dict)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error en el esquema de mapeo de columnas (mapping_json): {str(e)}",
            )

    summary = CatalogImporterService.import_vendor_catalog(
        db=db,
        vendor_id=vendor_id,
        file_bytes=file_bytes,
        filename=file.filename or "catalogo.csv",
        mapping=mapping,
        workspace_id=current_ws.id,
    )
    record_traction_event(
        db,
        event_type="VENDOR_CATALOG_IMPORTED",
        workspace_id=current_ws.id,
        is_demo=current_ws.is_demo,
        metadata={
            "vendor_id": str(vendor_id),
            "total_rows": summary.total_rows,
            "new_or_updated_rows": summary.new_or_updated_rows,
        },
    )
    db.commit()
    return summary


@router.get("/sample-template/download", response_class=PlainTextResponse)
def download_sample_csv():
    """Descarga una planilla CSV de ejemplo calibrada para probar la importación en un clic."""
    csv_content = CatalogImporterService.generate_sample_csv()
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=plantilla_materiales_ejemplo.csv"},
    )
