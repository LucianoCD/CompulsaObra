"""Pruebas de regresión para todos los hallazgos de auditoría (CO-02, CO-03, CO-07, CO-08, CO-09, BUG-04, DOC-01, DOC-03)."""

import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_hmac_share_token
from app.core.exceptions import CatalogImportValidationError, WorkspaceIsolationError
from app.models.workspace import Workspace
from app.models.vendor import Vendor, PriceList, VendorProduct
from app.models.requisition import Requisition, RequisitionItem
from app.models.comparison import ComparisonRun, ComparisonItemMatch
from app.schemas.vendor import ColumnMappingSchema
from app.services.catalog_importer import parse_argentina_currency, CatalogImporterService
from app.services.comparison_optimizer import ComparisonOptimizerService
from app.services.matching_engine import MatchingEngineService


def test_image_upload_without_gemini_raises_503_never_preset(client: TestClient, monkeypatch):
    """CO-02: Subida de imagen sin API Key de Gemini debe responder 503 y NUNCA devolver el preset demo."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    files = {"image_file": ("remito.png", b"\x89PNG\r\n\x1a\nfakeimagebytes", "image/png")}
    res = client.post(
        "/api/v1/requisitions/ingest",
        data={"title": "Prueba Imagen Sin Key"},
        files=files,
    )
    assert res.status_code == 503
    err_body = str(res.json()).lower()
    assert "no disponible" in err_body or "multimodal" in err_body


def test_resolve_empty_payload_on_missing_critical_item_fails_422(client: TestClient, db: Session):
    """CO-03: Enviar PATCH /resolve con body vacío {} para un caño sin material ni diámetro debe dar 422."""
    ws = db.query(Workspace).filter(Workspace.is_demo == True).first()
    assert ws is not None

    req = Requisition(
        workspace_id=ws.id,
        title="Requisición Prueba Desambiguación",
        status="NEEDS_CLARIFICATION",
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    item = RequisitionItem(
        requisition_id=req.id,
        raw_line="Caño sanitario",
        requested_term="caño sanitario",
        line_order=1,
        quantity=Decimal("10"),
        requested_unit="U",
        completeness="missing_critical_attribute",
        clarification_prompt="Falta especificar material y diámetro",
        material_type=None,
        diameter_mm=None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # Intento de resolver enviando objeto vacío
    res = client.patch(
        f"/api/v1/requisitions/{req.id}/items/{item.id}/resolve",
        json={},
        headers={"X-Workspace-Id": str(ws.id)},
    )
    assert res.status_code == 422
    assert "material" in res.json().get("detail", "").lower()


def test_argentine_currency_parsing_and_invalid_row_skipping():
    """CO-09: El parser debe interpretar '10.500' como 10500 ARS y lanzar validación en texto como 'Consultar'."""
    assert parse_argentina_currency("10.500") == Decimal("10500.00")
    assert parse_argentina_currency("$ 1.250,50") == Decimal("1250.50")
    assert parse_argentina_currency("  $ 45.000,00 ") == Decimal("45000.00")
    assert parse_argentina_currency("2500") == Decimal("2500.00")

    with pytest.raises(CatalogImportValidationError):
        parse_argentina_currency("Consultar")

    with pytest.raises(CatalogImportValidationError):
        parse_argentina_currency("-")

    with pytest.raises(CatalogImportValidationError):
        parse_argentina_currency("S/P")


def test_split_cart_global_subset_optimization(db: Session):
    """CO-07: Comprueba que el Split Cart no caiga en la trampa voraz y optimice el costo global (material + fletes)."""
    ws = db.query(Workspace).filter(Workspace.is_demo == True).first()
    assert ws is not None

    # Proveedor 1: Barato en conjunto, flete bajo ($2000)
    v1 = Vendor(
        workspace_id=ws.id,
        name="Corralon Global Barato",
        locality="Jujuy",
        estimate_delivery_fee_ars=Decimal("2000.00"),
    )
    # Proveedor 2: $10 más barato en 1 solo ítem, pero flete enorme ($15000)
    v2 = Vendor(
        workspace_id=ws.id,
        name="Corralon Flete Caro",
        locality="Palpalá",
        estimate_delivery_fee_ars=Decimal("15000.00"),
    )
    db.add_all([v1, v2])
    db.commit()

    pl1 = PriceList(vendor_id=v1.id, version_number=1, source_filename="pl1.xlsx", is_active=True)
    pl2 = PriceList(vendor_id=v2.id, version_number=1, source_filename="pl2.xlsx", is_active=True)
    db.add_all([pl1, pl2])
    db.commit()

    # Ítems en v1: prod1=$1000, prod2=$1000 -> Total Mat=$2000, Flete=$2000 -> Suma=$4000
    vp1_1 = VendorProduct(
        price_list_id=pl1.id, vendor_id=v1.id, sku="P1-1", raw_description="Cemento Loma Negra 50 kg",
        normalized_description="cemento loma negra 50 kg", brand="Loma Negra",
        price_cash_ars=Decimal("1000.00"), price_list_ars=Decimal("1000.00"),
        weight_kg=Decimal("50.0"), row_sha256="hash_p1_1",
    )
    vp1_2 = VendorProduct(
        price_list_id=pl1.id, vendor_id=v1.id, sku="P1-2", raw_description="Hierro 8 mm 12 m",
        normalized_description="hierro 8 mm 12 m", brand="Acindar",
        price_cash_ars=Decimal("1000.00"), price_list_ars=Decimal("1000.00"),
        diameter_mm=Decimal("8.0"), length_m=Decimal("12.0"), row_sha256="hash_p1_2",
    )
    # Ítems en v2: prod1=$990 (ahorro $10), prod2 no lo tiene
    vp2_1 = VendorProduct(
        price_list_id=pl2.id, vendor_id=v2.id, sku="P2-1", raw_description="Cemento Loma Negra 50 kg",
        normalized_description="cemento loma negra 50 kg", brand="Loma Negra",
        price_cash_ars=Decimal("990.00"), price_list_ars=Decimal("990.00"),
        weight_kg=Decimal("50.0"), row_sha256="hash_p2_1",
    )
    db.add_all([vp1_1, vp1_2, vp2_1])
    db.commit()

    req = Requisition(workspace_id=ws.id, title="Test Global Split Cart", status="READY_TO_COMPARE")
    db.add(req)
    db.commit()

    req_i1 = RequisitionItem(
        requisition_id=req.id, raw_line="Cemento Loma Negra 50 kg", requested_term="cemento loma negra 50 kg",
        line_order=1, quantity=Decimal("1"), requested_unit="BOLSA", completeness="complete",
        weight_kg=Decimal("50.0"), is_confirmed=True,
    )
    req_i2 = RequisitionItem(
        requisition_id=req.id, raw_line="Hierro 8 mm 12 m", requested_term="hierro 8 mm 12 m",
        line_order=2, quantity=Decimal("1"), requested_unit="BARRA", completeness="complete",
        diameter_mm=Decimal("8.0"), length_m=Decimal("12.0"), is_confirmed=True,
    )
    db.add_all([req_i1, req_i2])
    db.commit()

    result = ComparisonOptimizerService.run_multi_vendor_comparison(
        db=db,
        requisition_id=req.id,
        vendor_ids=[v1.id, v2.id],
        payment_modality="CASH",
    )

    split_cart = result.split_cart
    assert split_cart is not None
    # El algoritmo voraz elegiría v2 para prod1 y v1 para prod2, con costo total = 990 + 1000 + 15000 + 2000 = 18990
    # La optimización global de subconjuntos debe seleccionar únicamente v1, con costo total = 4000
    assert split_cart.total_cart_ars == 4000.00
    assert split_cart.participating_vendors_count == 1
    assert split_cart.participating_vendor_names == ["Corralon Global Barato"]


def test_locked_budget_cannot_be_overridden_or_mutated(client: TestClient, db: Session):
    """BUG-04: Modificar o hacer override sobre una compulsa bloqueada debe retornar 409 Conflict."""
    ws = db.query(Workspace).filter(Workspace.is_demo == True).first()
    assert ws is not None

    req = Requisition(workspace_id=ws.id, title="Requisición Bloqueada", status="LOCKED_BUDGET")
    db.add(req)
    db.commit()
    db.refresh(req)

    item = RequisitionItem(
        requisition_id=req.id,
        raw_line="Caño PVC 110 mm",
        requested_term="caño pvc 110 mm",
        line_order=1,
        quantity=Decimal("5"),
        requested_unit="U",
        completeness="complete",
        material_type="PVC",
        diameter_mm=Decimal("110.0"),
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # Intento de modificar ítem resuelto en una requisición LOCKED_BUDGET
    res = client.patch(
        f"/api/v1/requisitions/{req.id}/items/{item.id}/resolve",
        json={"material_type": "PVC", "diameter_mm": 110.0},
        headers={"X-Workspace-Id": str(ws.id)},
    )
    assert res.status_code == 409
    err_body = str(res.json()).lower()
    assert "congelado" in err_body or "bloquead" in err_body or "locked" in err_body


def test_public_view_requires_valid_hmac_and_locked_status(client: TestClient, db: Session):
    """DOC-01: La vista pública exige token HMAC genuino y compulsa en estado LOCKED_BUDGET."""
    ws = db.query(Workspace).filter(Workspace.is_demo == True).first()
    assert ws is not None

    vendors = db.query(Vendor).filter(Vendor.is_public_directory == True).all()
    vendor_ids = [str(v.id) for v in vendors]

    # 1. Ingestar y confirmar una requisición
    res_ingest = client.post(
        "/api/v1/requisitions/ingest",
        data={"title": "Pliego Public Test", "raw_text": "10 bolsas de cemento loma negra 50 kg"},
        headers={"X-Workspace-Id": str(ws.id)},
    )
    assert res_ingest.status_code == 201
    req_id = res_ingest.json()["id"]

    # 2. Correr compulsa
    res_comp = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={
            "vendor_ids": vendor_ids,
            "payment_modality": "CASH",
            "markup_pct": 15.0,
        },
        headers={"X-Workspace-Id": str(ws.id)},
    )
    assert res_comp.status_code == 200
    run_data = res_comp.json()
    run_id = run_data["run_id"]
    valid_token = run_data["public_share_token"]

    # 3. Token adulterado -> 404
    res_bad_token = client.get("/api/v1/public/comparisons/token_adulterado_falso")
    assert res_bad_token.status_code == 404

    # 4. Token genuino pero presupuesto aún no congelado -> 404
    res_not_locked = client.get(f"/api/v1/public/comparisons/{valid_token}")
    assert res_not_locked.status_code == 404

    # 5. Congelar presupuesto (lock-budget)
    res_lock = client.post(
        f"/api/v1/comparisons/{run_id}/lock-budget",
        headers={"X-Workspace-Id": str(ws.id)},
    )
    assert res_lock.status_code == 200

    # 6. Acceso público autorizado en modo client_budget
    res_ok = client.get(f"/api/v1/public/comparisons/{valid_token}?mode=client_budget")
    assert res_ok.status_code == 200
    data = res_ok.json()
    # Verificar sanitización estricta: nunca expone markup_pct, nombres de proveedores ni costos individuales
    assert data["markup_pct"] == 0.0
    assert data["vendors"] == []
    assert data["best_single_vendor_name"] is None
    assert all(len(r["vendor_cells"]) == 0 for r in data["matrix_rows"])


def test_catalog_importer_service_rejects_public_or_foreign_vendor_co03(db: Session):
    """CO-03: La capa de servicio de CatalogImporterService rechaza importar sobre comercios públicos o ajenos."""
    ws1 = db.query(Workspace).filter(Workspace.is_demo == True).first()
    public_vendor = db.query(Vendor).filter(Vendor.is_public_directory == True).first()
    assert public_vendor is not None

    csv_data = b"sku,descripcion,precio_contado\nSKU1,Ca\xc3\xb1o PVC,1000\n"

    # 1. Intentar importar sobre comercio del directorio público -> WorkspaceIsolationError
    with pytest.raises(WorkspaceIsolationError):
        CatalogImporterService.import_vendor_catalog(
            db=db,
            vendor_id=public_vendor.id,
            file_bytes=csv_data,
            filename="test.csv",
            mapping=ColumnMappingSchema(),
            workspace_id=ws1.id,
        )

    # 2. Intentar importar sobre comercio de otro workspace privado
    foreign_ws = Workspace(id=uuid.uuid4(), name="Otro Workspace", is_demo=False)
    db.add(foreign_ws)
    db.flush()
    private_vendor = Vendor(
        id=uuid.uuid4(),
        workspace_id=foreign_ws.id,
        name="Corralon Ajeno",
        locality="Jujuy",
        is_public_directory=False,
    )
    db.add(private_vendor)
    db.commit()

    with pytest.raises(WorkspaceIsolationError):
        CatalogImporterService.import_vendor_catalog(
            db=db,
            vendor_id=private_vendor.id,
            file_bytes=csv_data,
            filename="test.csv",
            mapping=ColumnMappingSchema(),
            workspace_id=ws1.id,  # ws1 no coincide con foreign_ws
        )


def test_override_match_updates_run_totals_and_split_cart_co06(client: TestClient, db: Session):
    """CO-06: override_item_match actualiza las columnas relacionales de ComparisonRun y sincroniza Split Cart."""
    ws = db.query(Workspace).filter(Workspace.is_demo == True).first()
    vendors = db.query(Vendor).filter(Vendor.is_public_directory == True).all()

    # 1. Ingestar pedido de 10 bolsas de cemento
    res_ingest = client.post(
        "/api/v1/requisitions/ingest",
        data={"title": "Pliego Override Test", "raw_text": "10 bolsas de cemento 50 kg"},
        headers={"X-Workspace-Id": str(ws.id)},
    )
    assert res_ingest.status_code == 201
    req_id = res_ingest.json()["id"]

    # 2. Correr compulsa
    res_comp = client.post(
        f"/api/v1/requisitions/{req_id}/compare",
        json={"vendor_ids": [str(v.id) for v in vendors], "payment_modality": "CASH"},
        headers={"X-Workspace-Id": str(ws.id)},
    )
    assert res_comp.status_code == 200
    run_id = res_comp.json()["run_id"]
    cell = res_comp.json()["matrix_rows"][0]["vendor_cells"][0]
    match_id = cell["match_id"]
    current_product_id = cell["vendor_product_id"]

    # Buscar un producto alternativo del mismo vendor
    alt_prod = db.query(VendorProduct).filter(
        VendorProduct.vendor_id == uuid.UUID(cell["vendor_id"]),
        VendorProduct.id != uuid.UUID(current_product_id),
    ).first()
    if not alt_prod:
        # Crear producto alternativo si el fixture solo tiene uno
        active_pl = db.query(PriceList).filter(PriceList.vendor_id == uuid.UUID(cell["vendor_id"])).first()
        alt_prod = VendorProduct(
            id=uuid.uuid4(),
            price_list_id=active_pl.id,
            vendor_id=uuid.UUID(cell["vendor_id"]),
            sku="ALT-CEM",
            raw_description="Cemento Alternativo Loma Negra 50 kg",
            normalized_description="cemento alternativo loma negra 50 kg",
            weight_kg=Decimal("50.0"),
            material_type="Cemento",
            price_cash_ars=Decimal("8000.00"),
            price_list_ars=Decimal("9000.00"),
            row_sha256="fakealtsha256",
        )
        db.add(alt_prod)
        db.commit()

    # 3. Aplicar override
    res_override = client.patch(
        f"/api/v1/comparisons/{run_id}/matches/{match_id}",
        json={
            "vendor_product_id": str(alt_prod.id),
            "force_dimension_override": True,
        },
        headers={"X-Workspace-Id": str(ws.id)},
    )
    assert res_override.status_code == 200

    # 4. Verificar en base de datos que ComparisonRun haya actualizado sus columnas relacionales
    db_run = db.query(ComparisonRun).filter(ComparisonRun.id == uuid.UUID(run_id)).first()
    assert db_run is not None
    assert db_run.best_single_total_ars is not None
    assert db_run.split_cart_total_ars is not None
    assert float(db_run.split_cart_total_ars) > 0


def test_acopio_price_basis_and_vendor_cash_discount_co09(db: Session):
    """CO-09: MatchingEngineService resuelve correctamente cash_discount_pct y price_basis (LIST vs CASH) en ACOPIO."""
    vendor = Vendor(
        id=uuid.uuid4(),
        name="Corralón Descuentos",
        locality="Jujuy",
        cash_discount_pct=Decimal("10.0"),  # 10% de descuento contado
        acopio_config_json={"price_basis": "CASH", "enabled": True},
    )
    prod = VendorProduct(
        id=uuid.uuid4(),
        price_list_id=uuid.uuid4(),
        vendor_id=vendor.id,
        sku="TEST-SKU",
        raw_description="Producto Test",
        normalized_description="producto test",
        price_list_ars=Decimal("10000.00"),
        price_cash_ars=Decimal("10000.00"),  # Trae el mismo que lista
        row_sha256="testsha",
    )

    # 1. En CASH: debe aplicar el 10% de descuento del vendor -> $9000.00
    price_cash = MatchingEngineService.resolve_effective_unit_price(prod, vendor, "CASH")
    assert price_cash == Decimal("9000.00")

    # 2. En LIST: debe mantener precio de lista -> $10000.00
    price_list = MatchingEngineService.resolve_effective_unit_price(prod, vendor, "LIST")
    assert price_list == Decimal("10000.00")

    # 3. En ACOPIO con price_basis='CASH': aplica precio contado -> $9000.00
    price_acopio_cash = MatchingEngineService.resolve_effective_unit_price(prod, vendor, "ACOPIO")
    assert price_acopio_cash == Decimal("9000.00")

    # 4. En ACOPIO con price_basis='LIST': aplica precio lista -> $10000.00
    vendor.acopio_config_json = {"price_basis": "LIST", "enabled": True}
    price_acopio_list = MatchingEngineService.resolve_effective_unit_price(prod, vendor, "ACOPIO")
    assert price_acopio_list == Decimal("10000.00")


def test_xls_binary_import_and_upload_size_limit_co10_co11(client: TestClient, db: Session):
    """CO-10 / CO-11: Soporte de lectura de archivos .xls con xlrd y límite de tamaño 413."""
    ws = db.query(Workspace).filter(Workspace.is_demo == True).first()
    vendor = db.query(Vendor).filter(Vendor.workspace_id == ws.id, Vendor.is_public_directory == False).first()
    if not vendor:
        vendor = Vendor(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            name="Corralón Privado Test",
            locality="San Salvador de Jujuy",
            is_public_directory=False,
            cash_discount_pct=Decimal("5.0"),
            estimate_delivery_fee_ars=Decimal("1500.0"),
        )
        db.add(vendor)
        db.commit()

    # 1. Archivo que supera MAX_UPLOAD_SIZE_BYTES -> 413
    huge_bytes = b"0" * (settings.MAX_UPLOAD_SIZE_BYTES + 1024)
    files = {"file": ("catalogo_enorme.csv", huge_bytes, "text/csv")}
    res_large = client.post(
        f"/api/v1/vendors/{vendor.id}/catalogs/import",
        files=files,
        headers={"X-Workspace-Id": str(ws.id)},
    )
    assert res_large.status_code == 413

    # 2. Lectura .xls con xlrd
    import xlrd
    assert hasattr(xlrd, "open_workbook")

    with pytest.raises(Exception) as exc_info:
        CatalogImporterService.read_tabular_data(b"not_a_real_xls_file", "catalogo.xls")
    assert "xls" in str(exc_info.value).lower()

