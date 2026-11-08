"""Pruebas para el motor de matching y Cero Sustitución Ciega (TASK-05, E2E-01 y E2E-02)."""

import uuid
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.workspace import Workspace
from app.models.vendor import Vendor, PriceList, VendorProduct, ProductAlias
from app.models.requisition import Requisition, RequisitionItem
from app.core.exceptions import AmbiguousItemCannotBeMatchedError
from app.services.matching_engine import MatchingEngineService


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


def test_rule_1_blocks_ambiguous_item_e2e_01(db_session):
    """E2E-01: Si un ítem está en missing_critical_attribute, matching_engine bloquea el emparejamiento."""
    ws = Workspace(id=uuid.uuid4(), name="Test WS")
    vendor = Vendor(id=uuid.uuid4(), workspace_id=ws.id, name="Corralón A", locality="Jujuy")
    req = Requisition(id=uuid.uuid4(), workspace_id=ws.id, title="Pedido Obra", status="NEEDS_CLARIFICATION")
    
    item = RequisitionItem(
        id=uuid.uuid4(),
        requisition_id=req.id,
        line_order=1,
        raw_line="4 caño de 3/4",
        requested_term="Caño Ø 3/4\" (19.05 mm)",
        quantity=Decimal("4.0"),
        diameter_mm=Decimal("19.05"),
        completeness="missing_critical_attribute",
        clarification_prompt="Especificar material...",
        is_confirmed=False,
    )
    db_session.add_all([ws, vendor, req, item])
    db_session.commit()

    with pytest.raises(AmbiguousItemCannotBeMatchedError) as exc_info:
        MatchingEngineService.match_item_against_vendor(
            db=db_session,
            workspace_id=ws.id,
            item=item,
            vendor_id=vendor.id,
        )
    assert "Especificar material" in str(exc_info.value.message)


def test_rule_3_and_4_zero_blind_substitution_e2e_02(db_session):
    """E2E-02: No-sustitución ciega entre medidas físicas.
    Negocio A tiene sólo Caño PVC 110 mm.
    Negocio B tiene Caño PVC 40 mm.
    El usuario pide Caño PVC 40 mm.
    Negocio A DEBE retornar NOT_CARRIED (jamás el de 110 mm).
    Negocio B DEBE retornar EXACT_MATCH.
    """
    ws = Workspace(id=uuid.uuid4(), name="Test WS")
    vendor_a = Vendor(id=uuid.uuid4(), workspace_id=ws.id, name="Negocio A", locality="Jujuy")
    vendor_b = Vendor(id=uuid.uuid4(), workspace_id=ws.id, name="Negocio B", locality="Palpalá")
    db_session.add_all([ws, vendor_a, vendor_b])
    db_session.flush()

    # Listas de precios activas
    pl_a = PriceList(id=uuid.uuid4(), vendor_id=vendor_a.id, version_number=1, source_filename="a.csv", is_active=True)
    pl_b = PriceList(id=uuid.uuid4(), vendor_id=vendor_b.id, version_number=1, source_filename="b.csv", is_active=True)
    db_session.add_all([pl_a, pl_b])
    db_session.flush()

    # Negocio A sólo tiene PVC 110 mm
    prod_a_110 = VendorProduct(
        id=uuid.uuid4(),
        price_list_id=pl_a.id,
        vendor_id=vendor_a.id,
        sku="PVC-110",
        raw_description="Caño PVC cloacal 110 mm x 4 m",
        normalized_description="cano pvc cloacal 110 mm x 4 m",
        price_cash_ars=Decimal("18500.00"),
        price_list_ars=Decimal("20000.00"),
        diameter_mm=Decimal("110.00"),
        length_m=Decimal("4.00"),
        material_type="PVC",
        row_sha256="hash110",
    )
    # Negocio B tiene PVC 40 mm
    prod_b_40 = VendorProduct(
        id=uuid.uuid4(),
        price_list_id=pl_b.id,
        vendor_id=vendor_b.id,
        sku="PVC-40",
        raw_description="Caño PVC sanitario blanco 40 mm x 4 m",
        normalized_description="cano pvc sanitario blanco 40 mm x 4 m",
        price_cash_ars=Decimal("6200.00"),
        price_list_ars=Decimal("6800.00"),
        diameter_mm=Decimal("40.00"),
        length_m=Decimal("4.00"),
        material_type="PVC",
        row_sha256="hash40",
    )
    db_session.add_all([prod_a_110, prod_b_40])
    db_session.commit()

    # Pedido: 5 caño PVC 40 mm
    item_40 = RequisitionItem(
        id=uuid.uuid4(),
        requisition_id=uuid.uuid4(),
        line_order=1,
        raw_line="5 caño PVC 40 mm",
        requested_term="Caño PVC Ø 40 mm",
        quantity=Decimal("5.0"),
        diameter_mm=Decimal("40.00"),
        length_m=Decimal("4.00"),
        material_type="PVC",
        completeness="complete",
        is_confirmed=True,
    )

    # Coincidencia contra Negocio A: debe ser NOT_CARRIED
    match_a = MatchingEngineService.match_item_against_vendor(
        db=db_session,
        workspace_id=ws.id,
        item=item_40,
        vendor_id=vendor_a.id,
    )
    assert match_a.match_status == "NOT_CARRIED"
    assert match_a.vendor_product_id is None
    assert match_a.unit_price_applied_ars is None

    # Coincidencia contra Negocio B: debe ser EXACT_MATCH
    match_b = MatchingEngineService.match_item_against_vendor(
        db=db_session,
        workspace_id=ws.id,
        item=item_40,
        vendor_id=vendor_b.id,
    )
    assert match_b.match_status == "EXACT_MATCH"
    assert match_b.vendor_product_id == prod_b_40.id
    assert match_b.unit_price_applied_ars == Decimal("6200.00")
    assert match_b.line_subtotal_ars == Decimal("31000.00")


def test_rule_2_supervised_alias_priority(db_session):
    """Verifica que un alias supervisado tenga prioridad de coincidencia."""
    ws = Workspace(id=uuid.uuid4(), name="Test WS")
    vendor = Vendor(id=uuid.uuid4(), workspace_id=ws.id, name="Corralón C", locality="Perico")
    pl = PriceList(id=uuid.uuid4(), vendor_id=vendor.id, version_number=1, source_filename="c.csv", is_active=True)
    db_session.add_all([ws, vendor, pl])
    db_session.flush()

    prod_especial = VendorProduct(
        id=uuid.uuid4(),
        price_list_id=pl.id,
        vendor_id=vendor.id,
        sku="CEM-ESP",
        raw_description="Cemento Holcim Fuerte 50 kg Especial",
        normalized_description="cemento holcim fuerte 50 kg especial",
        price_cash_ars=Decimal("9900.00"),
        price_list_ars=Decimal("11000.00"),
        weight_kg=Decimal("50.00"),
        material_type="Cemento",
        row_sha256="hashesp",
    )
    db_session.add(prod_especial)
    db_session.flush()

    # Guardar alias supervisado
    alias = ProductAlias(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        vendor_id=vendor.id,
        alias_term="cemento preferido de la obra",
        canonical_term="Cemento Portland 50 kg",
        target_vendor_product_id=prod_especial.id,
        is_active=True,
    )
    db_session.add(alias)
    db_session.commit()

    item_alias = RequisitionItem(
        id=uuid.uuid4(),
        requisition_id=uuid.uuid4(),
        line_order=1,
        raw_line="10 bolsas cemento preferido de la obra",
        requested_term="cemento preferido de la obra",
        quantity=Decimal("10.0"),
        weight_kg=Decimal("50.00"),
        material_type="Cemento",
        completeness="complete",
        is_confirmed=True,
    )

    match_alias = MatchingEngineService.match_item_against_vendor(
        db=db_session,
        workspace_id=ws.id,
        item=item_alias,
        vendor_id=vendor.id,
    )

    assert match_alias.match_status == "EXACT_MATCH"
    assert match_alias.match_origin == "SUPERVISED_ALIAS"
    assert match_alias.vendor_product_id == prod_especial.id
    assert match_alias.unit_price_applied_ars == Decimal("9900.00")
    assert match_alias.line_subtotal_ars == Decimal("99000.00")
