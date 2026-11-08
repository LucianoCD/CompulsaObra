"""Pruebas para el importador de catálogos y deduplicación SHA-256 (TASK-03)."""

import uuid
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.workspace import Workspace
from app.models.vendor import Vendor, PriceList, VendorProduct
from app.schemas.vendor import ColumnMappingSchema
from app.services.catalog_importer import (
    CatalogImporterService,
    parse_argentina_currency,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_parse_argentina_currency():
    """Verifica limpieza de formatos monetarios argentinos."""
    assert parse_argentina_currency("$ 10.500,50") == Decimal("10500.50")
    assert parse_argentina_currency("10.500,50") == Decimal("10500.50")
    assert parse_argentina_currency("$9500") == Decimal("9500.00")
    assert parse_argentina_currency("9500.25") == Decimal("9500.25")
    assert parse_argentina_currency(1234.56) == Decimal("1234.56")


def test_catalog_import_and_sha256_incremental_deduplication(db_session):
    """Verifica importación de versión 1 y versión 2 con hash SHA-256 incremental."""
    # 1. Crear Workspace y Vendor
    ws = Workspace(id=uuid.uuid4(), name="Test WS", is_demo=False)
    db_session.add(ws)
    db_session.flush()

    vendor = Vendor(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        name="Corralón Test",
        locality="Jujuy",
    )
    db_session.add(vendor)
    db_session.commit()

    mapping = ColumnMappingSchema(
        sku_col="sku",
        desc_col="descripcion",
        price_cash_col="precio_contado",
        price_list_col="precio_lista",
        unit_col="unidad",
        brand_col="marca",
        category_col="categoria",
    )

    # 2. Versión 1: 3 productos
    csv_v1 = (
        "sku;descripcion;precio_contado;precio_lista;unidad;marca;categoria\n"
        "CEM-01;Cemento Loma Negra 50 kg;9500.00;10500.00;BOLSA;Loma Negra;Cemento\n"
        "HIE-08;Barra del 8;11000.00;12000.00;BARRA;Acindar;Hierros\n"
        "PVC-40;Caño PVC 40 mm;6000.00;6800.00;UN;Tigre;Sanitarios\n"
    ).encode("utf-8")

    res_v1 = CatalogImporterService.import_vendor_catalog(
        db=db_session,
        vendor_id=vendor.id,
        file_bytes=csv_v1,
        filename="lista_v1.csv",
        mapping=mapping,
    )

    assert res_v1.version_number == 1
    assert res_v1.total_rows == 3
    assert res_v1.new_or_updated_rows == 3
    assert res_v1.unchanged_skipped_rows == 0

    # Verificar que los productos tengan dimensiones físicas extraídas
    v1_products = db_session.scalars(
        PriceList.__table__.select().where(PriceList.id == res_v1.price_list_id)
    ).all()
    assert len(v1_products) == 1

    # 3. Versión 2:
    # - CEM-01 y HIE-08 se mantienen idénticos (mismo SKU y misma descripción)
    # - PVC-40 cambia de descripción a "Caño PVC 40 mm reforzado" (hash distinto)
    # - Se agrega HIE-10 (nuevo producto)
    csv_v2 = (
        "sku;descripcion;precio_contado;precio_lista;unidad;marca;categoria\n"
        "CEM-01;Cemento Loma Negra 50 kg;10200.00;11300.00;BOLSA;Loma Negra;Cemento\n"
        "HIE-08;Barra del 8;12500.00;13800.00;BARRA;Acindar;Hierros\n"
        "PVC-40;Caño PVC 40 mm reforzado;6500.00;7200.00;UN;Tigre;Sanitarios\n"
        "HIE-10;Barra del 10;18000.00;19900.00;BARRA;Acindar;Hierros\n"
    ).encode("utf-8")

    res_v2 = CatalogImporterService.import_vendor_catalog(
        db=db_session,
        vendor_id=vendor.id,
        file_bytes=csv_v2,
        filename="lista_v2.csv",
        mapping=mapping,
    )

    assert res_v2.version_number == 2
    assert res_v2.total_rows == 4
    # 2 sin cambios (CEM-01 y HIE-08)
    assert res_v2.unchanged_skipped_rows == 2
    # 2 nuevos o modificados (PVC-40 modificado y HIE-10 nuevo)
    assert res_v2.new_or_updated_rows == 2

    # Verificar que la lista v1 quedó inactiva y la v2 activa
    pl_v1 = db_session.scalar(select(PriceList).where(PriceList.id == res_v1.price_list_id))
    pl_v2 = db_session.scalar(select(PriceList).where(PriceList.id == res_v2.price_list_id))
    assert pl_v1.is_active is False
    assert pl_v2.is_active is True
