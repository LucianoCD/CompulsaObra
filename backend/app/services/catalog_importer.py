"""Servicio de importación de catálogos Excel/CSV con deduplicación incremental SHA-256."""

import io
import csv
import hashlib
import uuid
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
import openpyxl
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.vendor import Vendor, PriceList, VendorProduct
from app.schemas.vendor import ColumnMappingSchema, CatalogImportSummary
from app.services.unit_normalizer import UnitNormalizerService, strip_accents
from app.core.exceptions import CatalogImportValidationError, WorkspaceIsolationError


def parse_argentina_currency(val: Any) -> Decimal:
    """Limpia y convierte texto o número a Decimal ARS positivo.
    
    Soporta: '$ 10.500,50', '10.500,50', '$10500', '10.500', 10500.5, '10500'
    """
    if val is None or isinstance(val, bool):
        raise CatalogImportValidationError("Precio no puede ser nulo")
    
    if isinstance(val, (int, float, Decimal)):
        d = Decimal(str(val))
        if d <= 0:
            raise CatalogImportValidationError(f"El precio debe ser mayor a 0: {d}")
        return d.quantize(Decimal("0.01"))
    
    s = str(val).strip()
    if "-" in s:
        raise CatalogImportValidationError(f"El precio no puede ser negativo o inválido: {val}")
    # Eliminar signo peso, espacios y caracteres no numéricos excepto puntos y comas
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        raise CatalogImportValidationError(f"Precio inválido: {val}")
    
    # Manejo de formato argentino:
    # 1. '10.500,50' -> punto miles, coma decimal
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.match(r"^\d{1,3}(\.\d{3})+$", s):
        # Entero con separador de miles argentino sin decimales (ej. '10.500' -> '10500')
        s = s.replace(".", "")
    
    try:
        d = Decimal(s)
        if d <= 0:
            raise CatalogImportValidationError(f"El precio debe ser mayor a 0: {d}")
        return d.quantize(Decimal("0.01"))
    except Exception as e:
        raise CatalogImportValidationError(f"Error al convertir precio '{val}': {str(e)}")


def sanitize_cell_value(val: str) -> str:
    """Evita ataques de CSV Formula Injection (CWE-1236 / SEC-05)."""
    if val and val[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + val
    return val


class CatalogImporterService:
    """Importador de listas de precios con deduplicación SHA-256 incremental."""

    @classmethod
    def read_tabular_data(cls, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        """Lee archivo .xlsx o .csv y retorna lista de diccionarios con claves en minúsculas."""
        lower_name = filename.lower()
        rows: List[Dict[str, Any]] = []

        if lower_name.endswith(".xls") and not lower_name.endswith(".xlsx"):
            try:
                import xlrd
                book = xlrd.open_workbook(file_contents=file_bytes)
                sheet = book.sheet_by_index(0)
                if sheet.nrows == 0:
                    raise CatalogImportValidationError("La planilla Excel .xls está vacía")
                
                header_row = [sheet.cell_value(0, col) for col in range(sheet.ncols)]
                headers = [
                    strip_accents(str(h).strip().lower()) if h is not None and str(h).strip() != "" else f"col_{i}"
                    for i, h in enumerate(header_row)
                ]

                for row_idx in range(1, sheet.nrows):
                    row_vals = [sheet.cell_value(row_idx, col) for col in range(sheet.ncols)]
                    if not any(c is not None and str(c).strip() != "" for c in row_vals):
                        continue
                    row_dict = {}
                    for h, cell in zip(headers, row_vals):
                        row_dict[h] = cell
                    rows.append(row_dict)
            except CatalogImportValidationError:
                raise
            except Exception as e:
                raise CatalogImportValidationError(f"No se pudo procesar la planilla Excel .xls: {str(e)}")

        elif lower_name.endswith(".xlsx"):
            try:
                wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            except Exception as e:
                raise CatalogImportValidationError(f"No se pudo procesar la planilla Excel .xlsx: {str(e)}")

            sheet = wb.active
            iter_rows = sheet.iter_rows(values_only=True)
            try:
                header_row = next(iter_rows)
            except StopIteration:
                raise CatalogImportValidationError("La planilla Excel está vacía")
            
            headers = [strip_accents(str(h).strip().lower()) if h is not None else f"col_{i}" for i, h in enumerate(header_row)]

            for row in iter_rows:
                if not any(cell is not None for cell in row):
                    continue
                row_dict = {}
                for h, cell in zip(headers, row):
                    row_dict[h] = cell
                rows.append(row_dict)

        elif lower_name.endswith(".csv"):
            # Intentar decodificar con utf-8, fallback a latin-1
            text = ""
            for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
                try:
                    text = file_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if not text:
                raise CatalogImportValidationError("No se pudo decodificar el archivo CSV")
            
            # Detectar delimitador: coma, punto y coma o tab
            sample = text[:2048]
            delimiter = ","
            if sample.count(";") > sample.count(","):
                delimiter = ";"
            elif sample.count("\t") > sample.count(","):
                delimiter = "\t"

            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            try:
                header_row = next(reader)
            except StopIteration:
                raise CatalogImportValidationError("El archivo CSV está vacío")
            
            headers = [strip_accents(str(h).strip().lower()) for h in header_row]

            for row in reader:
                if not any(field.strip() for field in row):
                    continue
                row_dict = {}
                for h, val in zip(headers, row):
                    row_dict[h] = val.strip()
                rows.append(row_dict)
        else:
            raise CatalogImportValidationError(f"Formato no soportado: '{filename}'. Use .xlsx, .xls o .csv")

        return rows


    @classmethod
    def import_vendor_catalog(
        cls,
        db: Session,
        vendor_id: uuid.UUID,
        file_bytes: bytes,
        filename: str,
        mapping: ColumnMappingSchema,
        workspace_id: Optional[uuid.UUID] = None,
    ) -> CatalogImportSummary:
        """Importa el catálogo, aplica versionado incremental y deduplicación por row_sha256."""
        vendor = db.scalar(select(Vendor).where(Vendor.id == vendor_id).with_for_update())
        if not vendor:
            raise CatalogImportValidationError(f"Comercio con ID {vendor_id} no encontrado")

        # Cierre definitivo CO-03: Autorización estricta en capa de servicio
        if vendor.is_public_directory or (workspace_id is not None and vendor.workspace_id != workspace_id):
            raise WorkspaceIsolationError(
                "Acceso denegado: no se permite importar catálogos sobre comercios del directorio público ni de otros espacios de trabajo."
            )

        raw_rows = cls.read_tabular_data(file_bytes, filename)
        if not raw_rows:
            raise CatalogImportValidationError("El archivo no contiene filas de datos válidas")

        # Buscar versión activa previa del mismo comercio
        prev_price_list = db.scalar(
            select(PriceList)
            .where(PriceList.vendor_id == vendor_id, PriceList.is_active.is_(True))
            .order_by(PriceList.version_number.desc())
        )

        prev_products_by_hash: Dict[str, VendorProduct] = {}
        if prev_price_list:
            prev_products = db.scalars(
                select(VendorProduct).where(VendorProduct.price_list_id == prev_price_list.id)
            ).all()
            for prod in prev_products:
                prev_products_by_hash[prod.row_sha256] = prod

        new_version_number = (prev_price_list.version_number + 1) if prev_price_list else 1
        new_price_list_id = uuid.uuid4()
        safe_filename = (filename or "catalogo.csv").strip()[:255]
        bind = db.get_bind()
        is_postgres = bind is not None and bind.dialect.name == "postgresql"

        sku_col = strip_accents(mapping.sku_col.lower())
        desc_col = strip_accents(mapping.desc_col.lower())
        cash_col = strip_accents(mapping.price_cash_col.lower())
        list_col = strip_accents(mapping.price_list_col.lower()) if mapping.price_list_col else None
        unit_col = strip_accents(mapping.unit_col.lower()) if mapping.unit_col else None
        brand_col = strip_accents(mapping.brand_col.lower()) if mapping.brand_col else None
        cat_col = strip_accents(mapping.category_col.lower()) if mapping.category_col else None

        new_products: List[VendorProduct] = []
        unchanged_count = 0
        new_or_updated_count = 0
        skipped_invalid_count = 0
        seen_hashes_in_batch: set[str] = set()

        for idx, row in enumerate(raw_rows, start=1):
            raw_sku_cell = row.get(sku_col)
            if raw_sku_cell is None or isinstance(raw_sku_cell, bool) or str(raw_sku_cell).strip() == "":
                raw_sku = f"SKU-{idx}"
            elif isinstance(raw_sku_cell, float) and raw_sku_cell.is_integer():
                raw_sku = str(int(raw_sku_cell))
            else:
                raw_sku = str(raw_sku_cell).strip()

            raw_desc_cell = row.get(desc_col)
            raw_desc = str(raw_desc_cell).strip() if raw_desc_cell is not None else ""
            if not raw_desc:
                continue

            sku_val = sanitize_cell_value(raw_sku)[:80]
            clean_desc = sanitize_cell_value(raw_desc)

            # Validar precio con tolerancia: si trae "Consultar" o formato inválido, omitir fila
            try:
                raw_cash = row.get(cash_col)
                raw_list = row.get(list_col) if list_col else None
                has_cash_val = raw_cash is not None and not (isinstance(raw_cash, str) and raw_cash.strip() == "")
                has_list_val = raw_list is not None and not (isinstance(raw_list, str) and raw_list.strip() == "")
                if not has_cash_val and not has_list_val:
                    raise CatalogImportValidationError("Fila sin precio válido")

                parsed_cash = parse_argentina_currency(raw_cash) if has_cash_val else None
                parsed_list = parse_argentina_currency(raw_list) if has_list_val else None

                if parsed_cash is None and parsed_list is not None:
                    price_list = parsed_list
                    if vendor.cash_discount_pct and float(vendor.cash_discount_pct) > 0:
                        discount_factor = (Decimal("100") - Decimal(str(vendor.cash_discount_pct))) / Decimal("100")
                        price_cash = (price_list * discount_factor).quantize(Decimal("0.01"))
                    else:
                        price_cash = price_list
                elif parsed_list is None and parsed_cash is not None:
                    price_cash = parsed_cash
                    price_list = parsed_cash
                else:
                    assert parsed_cash is not None and parsed_list is not None
                    price_cash = parsed_cash
                    price_list = parsed_list
            except CatalogImportValidationError:
                skipped_invalid_count += 1
                continue

            raw_unit_cell = row.get(unit_col) if unit_col else None
            sale_unit = (
                str(raw_unit_cell).strip().upper()[:30]
                if raw_unit_cell is not None and str(raw_unit_cell).strip()
                else "UN"
            )
            raw_brand_cell = row.get(brand_col) if brand_col else None
            brand_val = (
                str(raw_brand_cell).strip()[:80]
                if raw_brand_cell is not None and str(raw_brand_cell).strip()
                else None
            )
            raw_cat_cell = row.get(cat_col) if cat_col else None
            category_val = (
                str(raw_cat_cell).strip()[:80]
                if raw_cat_cell is not None and str(raw_cat_cell).strip()
                else None
            )

            normalized_desc = strip_accents(clean_desc).lower()
            row_sha256 = hashlib.sha256(f"{sku_val.strip().upper()}||{normalized_desc}".encode("utf-8")).hexdigest()

            # Evitar filas duplicadas idénticas en el mismo archivo (CO-12)
            if row_sha256 in seen_hashes_in_batch:
                continue
            seen_hashes_in_batch.add(row_sha256)

            # Deduplicación incremental: si el hash ya existía en la lista activa previa, clonar dimensiones
            if row_sha256 in prev_products_by_hash:
                prev_p = prev_products_by_hash[row_sha256]
                diameter_mm = prev_p.diameter_mm
                length_m = prev_p.length_m
                weight_kg = prev_p.weight_kg
                material_type = prev_p.material_type
                unchanged_count += 1
            else:
                # Fila nueva o con descripción modificada: ejecutar normalizador físico en modo catálogo
                parsed = UnitNormalizerService.parse_single_line(
                    clean_desc,
                    line_order=idx,
                    is_catalog_description=True,
                )
                diameter_mm = Decimal(str(parsed.diameter_mm)) if parsed.diameter_mm is not None else None
                length_m = Decimal(str(parsed.length_m)) if parsed.length_m is not None else None
                weight_kg = Decimal(str(parsed.weight_kg)) if parsed.weight_kg is not None else None
                material_type = parsed.material_type[:60] if parsed.material_type else None
                new_or_updated_count += 1

            new_prod = VendorProduct(
                id=uuid.uuid4(),
                price_list_id=new_price_list_id,
                vendor_id=vendor_id,
                sku=sku_val,
                raw_description=clean_desc,
                normalized_description=normalized_desc,
                brand=brand_val,
                brand_tier="PREMIUM" if brand_val and "acindar" in brand_val.lower() else "STANDARD",
                category=category_val,
                sale_unit=sale_unit,
                price_cash_ars=price_cash,
                price_list_ars=price_list,
                stock_available=True,
                diameter_mm=diameter_mm,
                length_m=length_m,
                weight_kg=weight_kg,
                material_type=material_type,
                row_sha256=row_sha256,
                search_vector=(
                    func.to_tsvector("spanish", func.unaccent(normalized_desc))
                    if is_postgres
                    else None
                ),
            )
            new_products.append(new_prod)

        if not new_products:
            db.rollback()
            raise CatalogImportValidationError("No se pudo extraer ningún producto válido con precio numérico de la planilla.")

        new_price_list = PriceList(
            id=new_price_list_id,
            vendor_id=vendor_id,
            version_number=new_version_number,
            source_filename=safe_filename,
            valid_from=datetime.now(timezone.utc),
            row_count=len(new_products),
            is_active=True,
        )

        # Desactivar lista anterior y persistir la nueva lista junto con sus productos
        if prev_price_list:
            prev_price_list.is_active = False

        db.add(new_price_list)
        db.add_all(new_products)
        db.commit()

        return CatalogImportSummary(
            price_list_id=new_price_list.id,
            vendor_id=vendor_id,
            version_number=new_version_number,
            total_rows=len(new_products),
            new_or_updated_rows=new_or_updated_count,
            unchanged_skipped_rows=unchanged_count,
            skipped_invalid_rows=skipped_invalid_count,
            source_filename=safe_filename,
        )

    @classmethod
    def generate_sample_csv(cls) -> str:
        """Genera un archivo CSV de ejemplo con precios y jerga del NOA para prueba en un clic."""
        rows = [
            ["sku", "descripcion", "precio_contado", "precio_lista", "unidad", "marca", "categoria"],
            ["CEM-01", "Cemento Portland Loma Negra 50 kg", "9500.50", "10500.00", "BOLSA", "Loma Negra", "Cosas de Obra"],
            ["HIE-08", "Hierro aletado conformada Ø 8 mm x 12 m", "11000.00", "12200.00", "BARRA", "Acindar", "Hierros"],
            ["HIE-10", "Hierro aletado conformada Ø 10 mm x 12 m", "17500.00", "19000.00", "BARRA", "Acindar", "Hierros"],
            ["PVC-40", "Caño PVC sanitario blanco 40 mm x 4 m", "6200.00", "7000.00", "UN", "Tigre", "Sanitarios"],
            ["PVC-110", "Caño PVC sanitario cloacal 110 mm x 4 m", "18500.00", "20500.00", "UN", "Tigre", "Sanitarios"],
            ["TER-34", "Caño termofusión agua 3/4 pulgada x 6 m", "9800.00", "10900.00", "UN", "Polimex", "Plomería"],
        ]
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerows(rows)
        return output.getvalue()
