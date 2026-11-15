"""Inicialización de datos semilla idempotente para CompulsaObra (Jujuy Demo)."""

import uuid
import hashlib
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.workspace import Workspace, User
from app.models.vendor import Vendor, PriceList, VendorProduct
from app.core.security import get_password_hash


def seed_demo_data_if_needed(db: Session) -> Workspace:
    """Crea el Workspace Demo y los 3 comercios semilla de Jujuy de manera idempotente."""
    demo_ws = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
    if demo_ws:
        return demo_ws

    bind = db.get_bind()
    is_postgres = bind is not None and bind.dialect.name == "postgresql"

    demo_ws_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    demo_ws = Workspace(
        id=demo_ws_id,
        name="Workspace Demo Jujuy",
        owner_role="ESTIMATOR",
        is_demo=True,
    )
    db.add(demo_ws)

    # Usuario demo inicial
    demo_user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        workspace_id=demo_ws_id,
        email="demo@compulsaobra.com.ar",
        full_name="Presupuestador Demo Jujuy",
        password_hash=get_password_hash("demo123"),
        role="ESTIMATOR",
        email_verified=True,
    )
    db.add(demo_user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
        if existing:
            return existing
        raise

    # 1. Corralón El Pórtico - Demo
    vendor_1_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    v1 = Vendor(
        id=vendor_1_id,
        workspace_id=demo_ws_id,
        name="Corralón El Pórtico - Demo",
        locality="San Salvador de Jujuy",
        whatsapp_phone="+543884112233",
        is_public_directory=True,
        cash_discount_pct=Decimal("5.00"),
        estimate_delivery_fee_ars=Decimal("15000.00"),
        acopio_config_json={
            "enabled": True,
            "price_basis": "LIST",
            "min_down_payment_pct": 100.0,
            "freeze_days": 30,
            "max_withdrawal_days": 60,
            "min_notice_hours": 24,
        },
    )
    db.add(v1)
    db.flush()

    pl1 = PriceList(
        id=uuid.uuid4(),
        vendor_id=v1.id,
        version_number=1,
        source_filename="catalogo_el_portico_demo.xlsx",
        is_active=True,
        row_count=5,
    )
    db.add(pl1)
    db.flush()

    prods_v1 = [
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl1.id,
            vendor_id=v1.id,
            sku="PORT-CEM-50",
            raw_description="Cemento Portland Loma Negra 50 kg",
            normalized_description="cemento portland loma negra 50 kg",
            brand="Loma Negra",
            brand_tier="PREMIUM",
            category="Cemento",
            sale_unit="BOLSA",
            price_cash_ars=Decimal("9500.00"),
            price_list_ars=Decimal("10500.00"),
            weight_kg=Decimal("50.00"),
            material_type="Cemento",
            row_sha256=hashlib.sha256(b"PORT-CEM-50||cemento portland loma negra 50 kg").hexdigest(),
        ),
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl1.id,
            vendor_id=v1.id,
            sku="PORT-HIE-08",
            raw_description="Barra acero aletado conformada Ø 8 mm x 12 m",
            normalized_description="barra acero aletado conformada 8 mm x 12 m",
            brand="Acindar",
            brand_tier="PREMIUM",
            category="Hierros",
            sale_unit="BARRA",
            price_cash_ars=Decimal("11000.00"),
            price_list_ars=Decimal("12200.00"),
            diameter_mm=Decimal("8.00"),
            length_m=Decimal("12.00"),
            material_type="Acero",
            row_sha256=hashlib.sha256(b"PORT-HIE-08||barra acero aletado conformada 8 mm x 12 m").hexdigest(),
        ),
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl1.id,
            vendor_id=v1.id,
            sku="PORT-HIE-10",
            raw_description="Barra acero aletado conformada Ø 10 mm x 12 m",
            normalized_description="barra acero aletado conformada 10 mm x 12 m",
            brand="Acindar",
            brand_tier="PREMIUM",
            category="Hierros",
            sale_unit="BARRA",
            price_cash_ars=Decimal("17500.00"),
            price_list_ars=Decimal("19000.00"),
            diameter_mm=Decimal("10.00"),
            length_m=Decimal("12.00"),
            material_type="Acero",
            row_sha256=hashlib.sha256(b"PORT-HIE-10||barra acero aletado conformada 10 mm x 12 m").hexdigest(),
        ),
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl1.id,
            vendor_id=v1.id,
            sku="PORT-PVC-40",
            raw_description="Caño PVC sanitario blanco 40 mm x 4 m",
            normalized_description="cano pvc sanitario blanco 40 mm x 4 m",
            brand="Tigre",
            brand_tier="STANDARD",
            category="Sanitarios",
            sale_unit="UN",
            price_cash_ars=Decimal("6200.00"),
            price_list_ars=Decimal("7000.00"),
            diameter_mm=Decimal("40.00"),
            length_m=Decimal("4.00"),
            material_type="PVC",
            row_sha256=hashlib.sha256(b"PORT-PVC-40||cano pvc sanitario blanco 40 mm x 4 m").hexdigest(),
        ),
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl1.id,
            vendor_id=v1.id,
            sku="PORT-TER-34",
            raw_description="Caño termofusión agua 3/4 pulgada x 6 m",
            normalized_description="cano termofusion agua 3/4 pulgada x 6 m",
            brand="Polimex",
            brand_tier="STANDARD",
            category="Plomería",
            sale_unit="UN",
            price_cash_ars=Decimal("9800.00"),
            price_list_ars=Decimal("10900.00"),
            diameter_mm=Decimal("19.05"),
            length_m=Decimal("6.00"),
            material_type="Termofusión",
            row_sha256=hashlib.sha256(b"PORT-TER-34||cano termofusion agua 3/4 pulgada x 6 m").hexdigest(),
        ),
    ]
    if is_postgres:
        for p in prods_v1:
            p.search_vector = func.to_tsvector("spanish", func.unaccent(p.normalized_description))
    db.add_all(prods_v1)

    # 2. Ferretería Industrial Cuyaya - Demo
    vendor_2_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    v2 = Vendor(
        id=vendor_2_id,
        workspace_id=demo_ws_id,
        name="Ferretería Industrial Cuyaya - Demo",
        locality="San Salvador de Jujuy",
        whatsapp_phone="+543884445566",
        is_public_directory=True,
        cash_discount_pct=Decimal("7.00"),
        estimate_delivery_fee_ars=Decimal("15000.00"),
        acopio_config_json={
            "enabled": True,
            "price_basis": "LIST",
            "min_down_payment_pct": 80.0,
            "freeze_days": 45,
            "max_withdrawal_days": 90,
            "min_notice_hours": 24,
        },
    )
    db.add(v2)
    db.flush()

    pl2 = PriceList(
        id=uuid.uuid4(),
        vendor_id=v2.id,
        version_number=1,
        source_filename="catalogo_cuyaya_demo.xlsx",
        is_active=True,
        row_count=5,
    )
    db.add(pl2)
    db.flush()

    prods_v2 = [
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl2.id,
            vendor_id=v2.id,
            sku="CUY-CEM-50",
            raw_description="Cemento Avellaneda 50 kg",
            normalized_description="cemento avellaneda 50 kg",
            brand="Avellaneda",
            brand_tier="STANDARD",
            category="Cemento",
            sale_unit="BOLSA",
            price_cash_ars=Decimal("10500.00"),
            price_list_ars=Decimal("11500.00"),
            weight_kg=Decimal("50.00"),
            material_type="Cemento",
            row_sha256=hashlib.sha256(b"CUY-CEM-50||cemento avellaneda 50 kg").hexdigest(),
        ),
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl2.id,
            vendor_id=v2.id,
            sku="CUY-HIE-08",
            raw_description="Barra acero aletado Ø 8 mm x 12 m Acindar",
            normalized_description="barra acero aletado 8 mm x 12 m acindar",
            brand="Acindar",
            brand_tier="PREMIUM",
            category="Hierros",
            sale_unit="BARRA",
            price_cash_ars=Decimal("8800.00"),
            price_list_ars=Decimal("9800.00"),
            diameter_mm=Decimal("8.00"),
            length_m=Decimal("12.00"),
            material_type="Acero",
            row_sha256=hashlib.sha256(b"CUY-HIE-08||barra acero aletado 8 mm x 12 m acindar").hexdigest(),
        ),
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl2.id,
            vendor_id=v2.id,
            sku="CUY-HIE-10",
            raw_description="Barra acero aletado Ø 10 mm x 12 m",
            normalized_description="barra acero aletado 10 mm x 12 m",
            brand="Acindar",
            brand_tier="PREMIUM",
            category="Hierros",
            sale_unit="BARRA",
            price_cash_ars=Decimal("16800.00"),
            price_list_ars=Decimal("18500.00"),
            diameter_mm=Decimal("10.00"),
            length_m=Decimal("12.00"),
            material_type="Acero",
            row_sha256=hashlib.sha256(b"CUY-HIE-10||barra acero aletado 10 mm x 12 m").hexdigest(),
        ),
        # Cuyaya sólo tiene Caño PVC 110 mm, NO tiene 40 mm (vital para E2E-02)
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl2.id,
            vendor_id=v2.id,
            sku="CUY-PVC-110",
            raw_description="Caño PVC cloacal 110 mm x 4 m",
            normalized_description="cano pvc cloacal 110 mm x 4 m",
            brand="Tigre",
            brand_tier="STANDARD",
            category="Sanitarios",
            sale_unit="UN",
            price_cash_ars=Decimal("18500.00"),
            price_list_ars=Decimal("20500.00"),
            diameter_mm=Decimal("110.00"),
            length_m=Decimal("4.00"),
            material_type="PVC",
            row_sha256=hashlib.sha256(b"CUY-PVC-110||cano pvc cloacal 110 mm x 4 m").hexdigest(),
        ),
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl2.id,
            vendor_id=v2.id,
            sku="CUY-PPR-34",
            raw_description="Caño polipropileno roscado 3/4 pulgada x 6 m",
            normalized_description="cano polipropileno roscado 3/4 pulgada x 6 m",
            brand="IPS",
            brand_tier="STANDARD",
            category="Plomería",
            sale_unit="UN",
            price_cash_ars=Decimal("8500.00"),
            price_list_ars=Decimal("9500.00"),
            diameter_mm=Decimal("19.05"),
            length_m=Decimal("6.00"),
            material_type="Polipropileno",
            row_sha256=hashlib.sha256(b"CUY-PPR-34||cano polipropileno roscado 3/4 pulgada x 6 m").hexdigest(),
        ),
    ]
    if is_postgres:
        for p in prods_v2:
            p.search_vector = func.to_tsvector("spanish", func.unaccent(p.normalized_description))
    db.add_all(prods_v2)

    # 3. Sanitarios y Materiales Palpalá - Demo
    vendor_3_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    v3 = Vendor(
        id=vendor_3_id,
        workspace_id=demo_ws_id,
        name="Sanitarios y Materiales Palpalá - Demo",
        locality="Palpalá",
        whatsapp_phone="+543884778899",
        is_public_directory=True,
        cash_discount_pct=Decimal("10.00"),
        estimate_delivery_fee_ars=Decimal("12000.00"),
        acopio_config_json={
            "enabled": True,
            "price_basis": "LIST",
            "min_down_payment_pct": 70.0,
            "freeze_days": 90,
            "max_withdrawal_days": 180,
            "min_notice_hours": 48,
        },
    )
    db.add(v3)
    db.flush()

    pl3 = PriceList(
        id=uuid.uuid4(),
        vendor_id=v3.id,
        version_number=1,
        source_filename="catalogo_palpala_demo.xlsx",
        is_active=True,
        row_count=5,
    )
    db.add(pl3)
    db.flush()

    prods_v3 = [
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl3.id,
            vendor_id=v3.id,
            sku="PAL-CEM-50",
            raw_description="Cemento Holcim 50 kg",
            normalized_description="cemento holcim 50 kg",
            brand="Holcim",
            brand_tier="STANDARD",
            category="Cemento",
            sale_unit="BOLSA",
            price_cash_ars=Decimal("10200.00"),
            price_list_ars=Decimal("11200.00"),
            weight_kg=Decimal("50.00"),
            material_type="Cemento",
            row_sha256=hashlib.sha256(b"PAL-CEM-50||cemento holcim 50 kg").hexdigest(),
        ),
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl3.id,
            vendor_id=v3.id,
            sku="PAL-HIE-08",
            raw_description="Barra hierro aletado Ø 8 mm x 12 m",
            normalized_description="barra hierro aletado 8 mm x 12 m",
            brand="Gerdau",
            brand_tier="STANDARD",
            category="Hierros",
            sale_unit="BARRA",
            price_cash_ars=Decimal("10800.00"),
            price_list_ars=Decimal("12000.00"),
            diameter_mm=Decimal("8.00"),
            length_m=Decimal("12.00"),
            material_type="Acero",
            row_sha256=hashlib.sha256(b"PAL-HIE-08||barra hierro aletado 8 mm x 12 m").hexdigest(),
        ),
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl3.id,
            vendor_id=v3.id,
            sku="PAL-PVC-40",
            raw_description="Caño PVC sanitario blanco 40 mm x 4 m",
            normalized_description="cano pvc sanitario blanco 40 mm x 4 m",
            brand="Tigre",
            brand_tier="STANDARD",
            category="Sanitarios",
            sale_unit="UN",
            price_cash_ars=Decimal("5900.00"),
            price_list_ars=Decimal("6600.00"),
            diameter_mm=Decimal("40.00"),
            length_m=Decimal("4.00"),
            material_type="PVC",
            row_sha256=hashlib.sha256(b"PAL-PVC-40||cano pvc sanitario blanco 40 mm x 4 m").hexdigest(),
        ),
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl3.id,
            vendor_id=v3.id,
            sku="PAL-PVC-110",
            raw_description="Caño PVC cloacal 110 mm x 4 m",
            normalized_description="cano pvc cloacal 110 mm x 4 m",
            brand="Tigre",
            brand_tier="STANDARD",
            category="Sanitarios",
            sale_unit="UN",
            price_cash_ars=Decimal("17800.00"),
            price_list_ars=Decimal("19800.00"),
            diameter_mm=Decimal("110.00"),
            length_m=Decimal("4.00"),
            material_type="PVC",
            row_sha256=hashlib.sha256(b"PAL-PVC-110||cano pvc cloacal 110 mm x 4 m").hexdigest(),
        ),
        VendorProduct(
            id=uuid.uuid4(),
            price_list_id=pl3.id,
            vendor_id=v3.id,
            sku="PAL-COR-34",
            raw_description="Caño corrugado eléctrico blanco 3/4 pulgada x 25 m",
            normalized_description="cano corrugado electrico blanco 3/4 pulgada x 25 m",
            brand="Genrod",
            brand_tier="STANDARD",
            category="Electricidad",
            sale_unit="ROLLO",
            price_cash_ars=Decimal("5200.00"),
            price_list_ars=Decimal("6000.00"),
            diameter_mm=Decimal("19.05"),
            length_m=Decimal("25.00"),
            material_type="Corrugado",
            row_sha256=hashlib.sha256(b"PAL-COR-34||cano corrugado electrico blanco 3/4 pulgada x 25 m").hexdigest(),
        ),
    ]
    if is_postgres:
        for p in prods_v3:
            p.search_vector = func.to_tsvector("spanish", func.unaccent(p.normalized_description))
    db.add_all(prods_v3)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Workspace).where(Workspace.is_demo.is_(True)))
        if existing:
            return existing
        raise
    return demo_ws
