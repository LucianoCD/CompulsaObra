"""Pruebas para el optimizador de compulsa multi-negocio, Split Cart y Acopio (TASK-06, E2E-03, E2E-04)."""

import uuid
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.workspace import Workspace
from app.models.vendor import Vendor, PriceList, VendorProduct
from app.models.requisition import Requisition, RequisitionItem
from app.services.comparison_optimizer import ComparisonOptimizerService


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


def test_e2e_03_split_cart_optimization_with_delivery_fees(db_session):
    """E2E-03: Optimización de Compra Dividida vs. Proveedor Único.
    - Negocio A: Cemento $9.500, Hierro $11.000, Flete $15.000
    - Negocio B: Cemento $10.500, Hierro $8.800, Flete $15.000
    - Pedido: 50 bolsas cemento + 40 barras del 8
    - Mejor Único: Negocio B ($877.000 + $15.000 = $892.000)
    - Split Cart: Cemento en A ($475.000) + Hierro en B ($352.000) + 2 fletes ($30.000) = $857.000
    - Ahorro neto verificable: $35.000
    """
    ws = Workspace(id=uuid.uuid4(), name="Test WS E2E-03")
    vendor_a = Vendor(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        name="Corralón El Pórtico",
        locality="Jujuy",
        estimate_delivery_fee_ars=Decimal("15000.00"),
    )
    vendor_b = Vendor(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        name="Ferretería Industrial Cuyaya",
        locality="Jujuy",
        estimate_delivery_fee_ars=Decimal("15000.00"),
    )
    db_session.add_all([ws, vendor_a, vendor_b])
    db_session.flush()

    pl_a = PriceList(id=uuid.uuid4(), vendor_id=vendor_a.id, version_number=1, source_filename="a.csv", is_active=True)
    pl_b = PriceList(id=uuid.uuid4(), vendor_id=vendor_b.id, version_number=1, source_filename="b.csv", is_active=True)
    db_session.add_all([pl_a, pl_b])
    db_session.flush()

    # Productos Negocio A
    prod_a_cem = VendorProduct(
        id=uuid.uuid4(),
        price_list_id=pl_a.id,
        vendor_id=vendor_a.id,
        sku="CEM-A",
        raw_description="Cemento Loma Negra 50 kg",
        normalized_description="cemento loma negra 50 kg",
        price_cash_ars=Decimal("9500.00"),
        price_list_ars=Decimal("10500.00"),
        weight_kg=Decimal("50.00"),
        material_type="Cemento",
        row_sha256="hash_a_cem",
    )
    prod_a_hie = VendorProduct(
        id=uuid.uuid4(),
        price_list_id=pl_a.id,
        vendor_id=vendor_a.id,
        sku="HIE-A",
        raw_description="Barra acero aletado Ø 8 mm x 12 m",
        normalized_description="barra acero aletado 8 mm x 12 m",
        price_cash_ars=Decimal("11000.00"),
        price_list_ars=Decimal("12000.00"),
        diameter_mm=Decimal("8.00"),
        length_m=Decimal("12.00"),
        material_type="Acero",
        row_sha256="hash_a_hie",
    )

    # Productos Negocio B
    prod_b_cem = VendorProduct(
        id=uuid.uuid4(),
        price_list_id=pl_b.id,
        vendor_id=vendor_b.id,
        sku="CEM-B",
        raw_description="Cemento Avellaneda 50 kg",
        normalized_description="cemento avellaneda 50 kg",
        price_cash_ars=Decimal("10500.00"),
        price_list_ars=Decimal("11500.00"),
        weight_kg=Decimal("50.00"),
        material_type="Cemento",
        row_sha256="hash_b_cem",
    )
    prod_b_hie = VendorProduct(
        id=uuid.uuid4(),
        price_list_id=pl_b.id,
        vendor_id=vendor_b.id,
        sku="HIE-B",
        raw_description="Barra acero aletado Ø 8 mm x 12 m Acindar",
        normalized_description="barra acero aletado 8 mm x 12 m acindar",
        price_cash_ars=Decimal("8800.00"),
        price_list_ars=Decimal("9800.00"),
        diameter_mm=Decimal("8.00"),
        length_m=Decimal("12.00"),
        material_type="Acero",
        row_sha256="hash_b_hie",
    )
    db_session.add_all([prod_a_cem, prod_a_hie, prod_b_cem, prod_b_hie])
    db_session.flush()

    # Requisición con los dos ítems confirmados
    req = Requisition(id=uuid.uuid4(), workspace_id=ws.id, title="Obra E2E-03", status="READY_TO_COMPARE")
    db_session.add(req)
    db_session.flush()

    item_cem = RequisitionItem(
        id=uuid.uuid4(),
        requisition_id=req.id,
        line_order=1,
        raw_line="50 bolsas de cemento",
        requested_term="Cemento Portland 50 kg",
        quantity=Decimal("50.0"),
        weight_kg=Decimal("50.00"),
        material_type="Cemento",
        completeness="complete",
        is_confirmed=True,
    )
    item_hie = RequisitionItem(
        id=uuid.uuid4(),
        requisition_id=req.id,
        line_order=2,
        raw_line="40 barras del 8",
        requested_term="Barra acero aletado Ø 8 mm x 12 m",
        quantity=Decimal("40.0"),
        diameter_mm=Decimal("8.00"),
        length_m=Decimal("12.00"),
        material_type="Acero",
        completeness="complete",
        is_confirmed=True,
    )
    db_session.add_all([item_cem, item_hie])
    db_session.commit()

    # Ejecutar compulsa en modalidad CASH con fletes
    result = ComparisonOptimizerService.run_multi_vendor_comparison(
        db=db_session,
        requisition_id=req.id,
        vendor_ids=[vendor_a.id, vendor_b.id],
        payment_modality="CASH",
        include_delivery_fees=True,
    )

    # Verificaciones exactas de E2E-03
    assert result.best_single_vendor_id == vendor_b.id
    assert result.best_single_total_ars == 892000.00

    assert result.split_cart.total_materials_ars == 827000.00
    assert result.split_cart.total_delivery_fees_ars == 30000.00
    assert result.split_cart.total_cart_ars == 857000.00
    assert result.split_cart.savings_vs_single_vendor_ars == 35000.00
    assert result.split_cart.is_split_recommended is True
    assert result.split_cart.participating_vendors_count == 2


def test_e2e_04_acopio_rules_and_snapshot(db_session):
    """E2E-04: Comparación de Reglas de Acopio estructuradas y persistencia de snapshot."""
    ws = Workspace(id=uuid.uuid4(), name="Test WS E2E-04")
    
    # Negocio A: 100% anticipo, 30 días congelamiento
    vendor_a = Vendor(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        name="Corralón A",
        locality="Jujuy",
        estimate_delivery_fee_ars=Decimal("10000.00"),
        acopio_config_json={
            "enabled": True,
            "min_down_payment_pct": 100.0,
            "freeze_days": 30,
            "max_withdrawal_days": 60,
            "min_notice_hours": 24,
        },
    )
    # Negocio C: 70% anticipo, 90 días congelamiento, preaviso 48hs
    vendor_c = Vendor(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        name="Sanitarios Palpalá",
        locality="Palpalá",
        estimate_delivery_fee_ars=Decimal("12000.00"),
        acopio_config_json={
            "enabled": True,
            "min_down_payment_pct": 70.0,
            "freeze_days": 90,
            "max_withdrawal_days": 180,
            "min_notice_hours": 48,
        },
    )
    db_session.add_all([ws, vendor_a, vendor_c])
    db_session.flush()

    pl_a = PriceList(id=uuid.uuid4(), vendor_id=vendor_a.id, version_number=1, source_filename="a.csv", is_active=True)
    pl_c = PriceList(id=uuid.uuid4(), vendor_id=vendor_c.id, version_number=1, source_filename="c.csv", is_active=True)
    db_session.add_all([pl_a, pl_c])
    db_session.flush()

    prod_a = VendorProduct(
        id=uuid.uuid4(),
        price_list_id=pl_a.id,
        vendor_id=vendor_a.id,
        sku="P-A",
        raw_description="Cemento Loma Negra 50 kg",
        normalized_description="cemento loma negra 50 kg",
        price_cash_ars=Decimal("10000.00"),
        price_list_ars=Decimal("10000.00"),
        weight_kg=Decimal("50.00"),
        material_type="Cemento",
        row_sha256="ha",
    )
    prod_c = VendorProduct(
        id=uuid.uuid4(),
        price_list_id=pl_c.id,
        vendor_id=vendor_c.id,
        sku="P-C",
        raw_description="Cemento Loma Negra 50 kg",
        normalized_description="cemento loma negra 50 kg",
        price_cash_ars=Decimal("10000.00"),
        price_list_ars=Decimal("10000.00"),
        weight_kg=Decimal("50.00"),
        material_type="Cemento",
        row_sha256="hc",
    )
    db_session.add_all([prod_a, prod_c])
    db_session.flush()

    req = Requisition(id=uuid.uuid4(), workspace_id=ws.id, title="Obra Acopio", status="READY_TO_COMPARE")
    db_session.add(req)
    db_session.flush()

    item = RequisitionItem(
        id=uuid.uuid4(),
        requisition_id=req.id,
        line_order=1,
        raw_line="10 bolsas de cemento",
        requested_term="Cemento Portland 50 kg",
        quantity=Decimal("10.0"),
        weight_kg=Decimal("50.00"),
        material_type="Cemento",
        completeness="complete",
        is_confirmed=True,
    )
    db_session.add(item)
    db_session.commit()

    # Ejecutar compulsa en ACOPIO
    result = ComparisonOptimizerService.run_multi_vendor_comparison(
        db=db_session,
        requisition_id=req.id,
        vendor_ids=[vendor_a.id, vendor_c.id],
        payment_modality="ACOPIO",
        include_delivery_fees=True,
    )

    # Verificar token público firmado y resumen de acopio de cada negocio
    assert result.public_share_token is not None
    assert "." in result.public_share_token

    v_a_sum = next(v for v in result.vendors if v.vendor_id == vendor_a.id)
    v_c_sum = next(v for v in result.vendors if v.vendor_id == vendor_c.id)

    # Total A: 10 * 10000 + 10000 = 110.000. Anticipo 100% = 110.000
    assert v_a_sum.acopio_summary["down_payment_ars"] == 110000.00
    assert v_a_sum.acopio_summary["freeze_days"] == 30

    # Total C: 10 * 10000 + 12000 = 112.000. Anticipo 70% = 78.400
    assert v_c_sum.acopio_summary["down_payment_ars"] == 78400.00
    assert v_c_sum.acopio_summary["freeze_days"] == 90
    assert v_c_sum.acopio_summary["min_notice_hours"] == 48
