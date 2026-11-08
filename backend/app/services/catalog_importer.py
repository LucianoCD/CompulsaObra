"""Servicio de importación de catálogos Excel/CSV con deduplicación incremental SHA-256."""

import io
import csv
import hashlib
import uuid
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
import openpyxl
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.vendor import Vendor, PriceList, VendorProduct
from app.schemas.vendor import ColumnMappingSchema, CatalogImportSummary
from app.services.unit_normalizer import UnitNormalizerService, strip_accents
from app.core.exceptions import CatalogImportValidationError


def parse_argentina_currency(val: Any) -> Decimal:
    """Limpia y convierte texto o número a Decimal ARS positivo.
    
    Soporta: '$ 10.500,50', '10.500,50', '$10500', '10.500', 10500.5, '10500'
    """
    if val is None:
        raise CatalogImportValidationError("Precio no puede ser nulo")
    
    if isinstance(val, (int, float, Decimal)):
        d = Decimal(str(val))
        if d <= 0:
            raise CatalogImportValidationError(f"El precio debe ser mayor a 0: {d}")
        return d.quantize(Decimal("0.01"))
    
    s = str(val).strip()
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
            raise CatalogImportValidationError(
                "El formato binario tradicional .xls no está soportado. Guarde el archivo como .xlsx o .csv."
            )

        if lower_name.endswith(".xlsx"):
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
            raise CatalogImportValidationError(f"Formato no soportado: '{filename}'. Use .xlsx o .csv")

        return rows


    @classmethod
    def import_vendor_catalog(
        cls,
        db: Session,
        vendor_id: uuid.UUID,
        file_bytes: bytes,
        filename: str,
        mapping: ColumnMappingSchema,
    ) -> CatalogImportSummary:
        """Importa el catálogo, aplica versionado incremental y deduplicación por row_sha256."""
        vendor = db.scalar(select(Vendor).where(Vendor.id == vendor_id))
        if not vendor:
            raise CatalogImportValidationError(f"Comercio con ID {vendor_id} no encontrado")

        raw_rows = cls.read_tabular_data(file_bytes, filename)
        if not raw_rows:
            raise CatalogImportValidationError("El archivo no contiene filas de datos válidas")

        # Buscar versión activa previa del mismo comercio
        prev_price_list = db.scalar(
            select(PriceList)
            .where(PriceList.vendor_id == vendor_id, PriceList.is_active == True)
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

        new_price_list = PriceList(
            id=uuid.uuid4(),
            vendor_id=vendor_id,
            version_number=new_version_number,
            source_filename=filename,
            valid_from=datetime.now(timezone.utc),
            row_count=0,
            is_active=True,
        )
        db.add(new_price_list)
        db.flush()

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
        seen_hashes_in_batch: Set[str] = set()

        for idx, row in enumerate(raw_rows, start=1):
            raw_sku = str(row.get(sku_col, f"SKU-{idx}") or f"SKU-{idx}").strip()
            raw_desc = str(row.get(desc_col, "") or "").strip()
            if not raw_desc:
                continue

            sku_val = sanitize_cell_value(raw_sku)
            clean_desc = sanitize_cell_value(raw_desc)

            # Validar precio con tolerancia: si trae "Consultar" o formato inválido, omitir fila
            try:
                price_cash = parse_argentina_currency(row.get(cash_col))
                if list_col and row.get(list_col) is not None:
                    price_list = parse_argentina_currency(row.get(list_col))
                else:
                    price_list = price_cash
            except CatalogImportValidationError:
                skipped_invalid_count += 1
                continue

            sale_unit = str(row.get(unit_col, "UN") or "UN").strip().upper()
            brand_val = str(row.get(brand_col, "") or "").strip() or None
            category_val = str(row.get(cat_col, "") or "").strip() or None

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
                # Fila nueva o con descripción modificada: ejecutar normalizador físico
                parsed = UnitNormalizerService.parse_single_line(clean_desc, line_order=idx)
                diameter_mm = Decimal(str(parsed.diameter_mm)) if parsed.diameter_mm is not None else None
                length_m = Decimal(str(parsed.length_m)) if parsed.length_m is not None else None
                weight_kg = Decimal(str(parsed.weight_kg)) if parsed.weight_kg is not None else None
                material_type = parsed.material_type
                new_or_updated_count += 1

            new_prod = VendorProduct(
                id=uuid.uuid4(),
                price_list_id=new_price_list.id,
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
            )
            new_products.append(new_prod)

        if not new_products:
            raise CatalogImportValidationError("No se pudo extraer ningún producto válido con precio numérico de la planilla.")

        # Desactivar lista anterior
        if prev_price_list:
            prev_price_list.is_active = False

        new_price_list.row_count = len(new_products)
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
            source_filename=filename,
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
