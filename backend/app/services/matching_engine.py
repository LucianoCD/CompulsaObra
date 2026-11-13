"""Motor de emparejamiento físico-léxico multi-catálogo con Cero Sustitución Ciega."""

import math
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import AmbiguousItemCannotBeMatchedError
from app.models.requisition import RequisitionItem
from app.models.vendor import PriceList, ProductAlias, Vendor, VendorProduct
from app.services.unit_normalizer import UnitNormalizerService, strip_accents

MIN_SIMILARITY_THRESHOLD = 0.20
MIN_AUTO_CONFIDENCE = 0.30
MIN_TOP_CANDIDATE_GAP = 0.08

_DISCRETE_PACK_UNITS = {"UN", "U", "BOLSA", "BARRA", "CAÑO", "CANO", "TIRA", "ROLLO", "PIEZA"}
_LINEAR_PACK_UNITS = {"ROLLO", "BARRA", "CAÑO", "CANO", "TIRA", "UN", "U"}


def _normalize_commercial_unit(unit: Optional[str]) -> str:
    if not unit:
        return "UN"
    u = strip_accents(unit).strip().upper()
    if u in {"U", "UN", "UNIDAD", "UNIDADES", "PIEZA", "PIEZAS"}:
        return "UN"
    if u in {"M", "MT", "MTS", "METRO", "METROS"}:
        return "M"
    if u in {"M2", "MT2", "M²"}:
        return "M2"
    if u in {"M3", "MT3", "M³"}:
        return "M3"
    if u in {"KG", "KILO", "KILOS", "KGS"}:
        return "KG"
    if "BOLSA" in u:
        return "BOLSA"
    if "BARRA" in u:
        return "BARRA"
    if "ROLLO" in u:
        return "ROLLO"
    if "CANO" in u or "CAÑO" in u or "TIRA" in u:
        return "CAÑO"
    if u in {"LT", "LTS", "LITRO", "LITROS", "L"}:
        return "LT"
    return u


@dataclass
class VendorItemMatchResult:
    match_status: str  # 'EXACT_MATCH' | 'AMBIGUOUS_CANDIDATES' | 'OUT_OF_STOCK' | 'NOT_CARRIED'
    vendor_product_id: Optional[uuid.UUID]
    vendor_product: Optional[VendorProduct]
    unit_price_applied_ars: Optional[Decimal]
    line_subtotal_ars: Optional[Decimal]
    similarity_score: Optional[float]
    match_origin: str = "EXACT_DIMENSIONAL"
    commercial_qty: Optional[float] = None
    conversion_note: Optional[str] = None
    candidate_options: List[Dict[str, object]] = field(default_factory=list)


def compute_string_similarity(s1: str, s2: str) -> float:
    """Calcula similitud de Jaccard y trigramas determinista entre dos cadenas."""
    w1 = set(strip_accents(s1).lower().split())
    w2 = set(strip_accents(s2).lower().split())
    if not w1 or not w2:
        return 0.0
    intersection = w1.intersection(w2)
    union = w1.union(w2)
    word_jaccard = len(intersection) / len(union)

    t1 = {s1[i : i + 3] for i in range(len(s1) - 2)} if len(s1) >= 3 else {s1}
    t2 = {s2[i : i + 3] for i in range(len(s2) - 2)} if len(s2) >= 3 else {s2}
    trigram_sim = len(t1.intersection(t2)) / len(t1.union(t2)) if t1 and t2 else 0.0

    return round(0.6 * word_jaccard + 0.4 * trigram_sim, 4)


class MatchingEngineService:
    """Servicio de búsqueda, conversión de unidades comerciales y validación dimensional estricta."""

    @classmethod
    def resolve_effective_unit_price(
        cls,
        prod: VendorProduct,
        vendor: Optional[Vendor],
        payment_modality: str,
    ) -> Decimal:
        """Determina el precio unitario exacto según modalidad comercial y políticas de acopio (CO-09 / H-13)."""
        modality = (payment_modality or "CASH").upper()
        if modality == "ACOPIO" and vendor and vendor.acopio_config_json:
            basis = str(vendor.acopio_config_json.get("price_basis", "LIST")).upper()
            modality = "CASH" if basis == "CASH" else "LIST"

        if modality == "CASH":
            p_cash = Decimal(str(prod.price_cash_ars))
            p_list = Decimal(str(prod.price_list_ars))
            if (
                p_cash == p_list
                and vendor
                and vendor.cash_discount_pct
                and Decimal(str(vendor.cash_discount_pct)) > Decimal("0")
            ):
                factor = (Decimal("100") - Decimal(str(vendor.cash_discount_pct))) / Decimal("100")
                return (p_list * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return p_cash.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return Decimal(str(prod.price_list_ars)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_commercial_quantity(
        cls,
        item: RequisitionItem,
        prod: VendorProduct,
    ) -> Tuple[Decimal, str, Optional[str], bool]:
        """Convierte cantidad solicitada a unidad comercial de venta del comercio con redondeo hacia arriba (H-07)."""
        req_qty = Decimal(str(item.quantity))
        req_unit = _normalize_commercial_unit(item.requested_unit)
        sale_unit_raw = (prod.sale_unit or "UN").strip()
        sale_unit = _normalize_commercial_unit(sale_unit_raw)

        # 1. Igual unidad física (ej. M -> M, KG -> KG, ROLLO -> ROLLO, UN -> UN)
        if req_unit == sale_unit:
            return req_qty, sale_unit_raw, None, True

        # 2. Unidades discretas compatibles (ej. BOLSA <-> UN, BARRA <-> UN, CAÑO <-> UN)
        if req_unit in _DISCRETE_PACK_UNITS and sale_unit in _DISCRETE_PACK_UNITS:
            # Si ambos son paquetes discretos compatibles (ej. pide 5 caño UN y vende en UN o CAÑO)
            if req_unit in {"UN", "BOLSA", "BARRA", "CAÑO"} and sale_unit in {"UN", "BOLSA", "BARRA", "CAÑO"}:
                return req_qty, sale_unit_raw, None, True
            if req_unit == "ROLLO" and sale_unit in {"ROLLO", "UN"}:
                return req_qty, sale_unit_raw, None, True

        # 3. Solicitud lineal en Metros ('M') frente a presentaciones por rollo/barra/tira/caño
        if req_unit == "M" and sale_unit in _LINEAR_PACK_UNITS:
            if prod.length_m is not None and Decimal(str(prod.length_m)) > Decimal("0"):
                pack_len = Decimal(str(prod.length_m))
                packs = math.ceil((float(req_qty) - 1e-9) / float(pack_len))
                comm_qty = Decimal(max(1, packs))
                total_meters = comm_qty * pack_len
                note = (
                    f"Solicitado: {float(req_qty):g} M -> Cotizado: {int(comm_qty)} "
                    f"{sale_unit_raw} de {float(pack_len):g}m ({float(total_meters):g}m totales)"
                )
                return comm_qty, sale_unit_raw, note, True
            return (
                req_qty,
                sale_unit_raw,
                f"No hay longitud de presentación para convertir {float(req_qty):g} M a {sale_unit_raw}; requiere confirmación.",
                False,
            )

        # 4. Solicitud en ROLLO/BARRA/CAÑO cuando el proveedor vende por Metro ('M')
        if req_unit in {"ROLLO", "BARRA", "CAÑO"} and sale_unit == "M":
            ref_len = prod.length_m or item.length_m
            if ref_len is not None and Decimal(str(ref_len)) > Decimal("0"):
                meters_qty = (req_qty * Decimal(str(ref_len))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                note = (
                    f"Solicitado: {float(req_qty):g} {req_unit} de {float(ref_len):g}m -> "
                    f"Cotizado: {float(meters_qty):g} M"
                )
                return meters_qty, sale_unit_raw, note, True
            return (
                req_qty,
                sale_unit_raw,
                f"No hay longitud de referencia para convertir {req_unit} a metros; requiere confirmación.",
                False,
            )

        # 5. Solicitud ponderal en KG frente a bolsas o unidades con peso declarado
        if req_unit == "KG" and sale_unit in {"BOLSA", "UN"}:
            if prod.weight_kg is not None and Decimal(str(prod.weight_kg)) > Decimal("0"):
                pack_w = Decimal(str(prod.weight_kg))
                packs = math.ceil((float(req_qty) - 1e-9) / float(pack_w))
                comm_qty = Decimal(max(1, packs))
                note = (
                    f"Solicitado: {float(req_qty):g} KG -> Cotizado: {int(comm_qty)} "
                    f"{sale_unit_raw} de {float(pack_w):g}kg"
                )
                return comm_qty, sale_unit_raw, note, True
            return (
                req_qty,
                sale_unit_raw,
                f"No hay peso de presentación para convertir {float(req_qty):g} KG a {sale_unit_raw}; requiere confirmación.",
                False,
            )

        # 6. Unidades sin equivalencia determinista segura -> exigir confirmación humana
        return (
            req_qty,
            sale_unit_raw,
            f"Unidad solicitada ({item.requested_unit}) distinta de unidad comercial ({sale_unit_raw}); requiere confirmación.",
            False,
        )

    @classmethod
    def match_item_against_vendor(
        cls,
        db: Session,
        workspace_id: uuid.UUID,
        item: RequisitionItem,
        vendor_id: uuid.UUID,
        payment_modality: str = "CASH",
    ) -> VendorItemMatchResult:
        """Empareja un ítem del pedido contra el catálogo activo de un comercio."""
        vendor = db.scalar(select(Vendor).where(Vendor.id == vendor_id))
        if item.completeness == "missing_critical_attribute":
            raise AmbiguousItemCannotBeMatchedError(
                item_id=str(item.id),
                message=item.clarification_prompt or "El ítem requiere aclaración técnica previa al emparejamiento.",
            )

        # 2. Memoria de Alias Supervisado en el Workspace (H-11: exacto por ID o por término canónico aprendido)
        alias = db.scalar(
            select(ProductAlias)
            .where(
                ProductAlias.workspace_id == workspace_id,
                or_(ProductAlias.vendor_id == vendor_id, ProductAlias.vendor_id.is_(None)),
                or_(
                    ProductAlias.alias_term == item.requested_term,
                    ProductAlias.alias_term == item.raw_line.strip(),
                    func.lower(ProductAlias.alias_term) == item.requested_term.strip().lower(),
                    func.lower(ProductAlias.alias_term) == item.raw_line.strip().lower(),
                ),
                ProductAlias.is_active.is_(True),
            )
            .order_by(ProductAlias.vendor_id.desc().nullslast())
        )

        if alias and alias.target_vendor_product_id:
            target_prod = db.scalar(
                select(VendorProduct)
                .join(PriceList, VendorProduct.price_list_id == PriceList.id)
                .where(
                    VendorProduct.id == alias.target_vendor_product_id,
                    VendorProduct.vendor_id == vendor_id,
                    PriceList.is_active.is_(True),
                )
            )
            if target_prod and cls._satisfies_physical_constraints(item, target_prod):
                comm_qty, _, conv_note, is_safe = cls.calculate_commercial_quantity(item, target_prod)
                if not is_safe:
                    return VendorItemMatchResult(
                        match_status="AMBIGUOUS_CANDIDATES",
                        vendor_product_id=target_prod.id,
                        vendor_product=target_prod,
                        unit_price_applied_ars=None,
                        line_subtotal_ars=None,
                        similarity_score=1.0,
                        match_origin="UNIT_CONVERSION_CONFIRMATION_REQUIRED",
                        commercial_qty=float(comm_qty),
                        conversion_note=conv_note,
                        candidate_options=[{
                            "vendor_product_id": str(target_prod.id),
                            "sku": target_prod.sku,
                            "description": target_prod.raw_description,
                            "sale_unit": target_prod.sale_unit,
                        }],
                    )
                price = cls.resolve_effective_unit_price(target_prod, vendor, payment_modality)
                subtotal = (price * comm_qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                return VendorItemMatchResult(
                    match_status="EXACT_MATCH",
                    vendor_product_id=target_prod.id,
                    vendor_product=target_prod,
                    unit_price_applied_ars=price,
                    line_subtotal_ars=subtotal,
                    similarity_score=1.0,
                    match_origin="SUPERVISED_ALIAS",
                    commercial_qty=float(comm_qty),
                    conversion_note=conv_note,
                )

        # 3. Consulta con Filtro Dimensional Duro SQL sobre la lista activa
        active_price_list = db.scalar(
            select(PriceList)
            .where(PriceList.vendor_id == vendor_id, PriceList.is_active.is_(True))
            .order_by(PriceList.version_number.desc())
        )

        if not active_price_list:
            return VendorItemMatchResult(
                match_status="NOT_CARRIED",
                vendor_product_id=None,
                vendor_product=None,
                unit_price_applied_ars=None,
                line_subtotal_ars=None,
                similarity_score=None,
                match_origin="NO_ACTIVE_CATALOG",
            )

        conditions = [
            VendorProduct.price_list_id == active_price_list.id,
            VendorProduct.vendor_id == vendor_id,
        ]

        if item.diameter_mm is not None:
            allowed_diameters = UnitNormalizerService.get_equivalent_diameters_mm(
                diameter_mm=float(item.diameter_mm),
                material_type=item.material_type,
                diameter_inch=item.diameter_inch,
            )
            conditions.append(VendorProduct.diameter_mm.is_not(None))
            conditions.append(
                or_(*[
                    func.abs(VendorProduct.diameter_mm - Decimal(str(d))) <= Decimal("0.5")
                    for d in allowed_diameters
                ])
            )

        # Cuando el usuario pide en metros lineales ('M'), permitir presentaciones en rollo/barra/caño
        req_unit_norm = _normalize_commercial_unit(item.requested_unit)
        if item.length_m is not None and req_unit_norm != "M":
            conditions.append(VendorProduct.length_m.is_not(None))
            conditions.append(func.abs(VendorProduct.length_m - item.length_m) <= Decimal("0.05"))

        if item.weight_kg is not None and req_unit_norm != "KG":
            conditions.append(VendorProduct.weight_kg.is_not(None))
            conditions.append(func.abs(VendorProduct.weight_kg - item.weight_kg) <= Decimal("0.5"))

        if item.material_type is not None:
            mat_raw = item.material_type.strip()
            mat_clean = strip_accents(mat_raw).lower()
            mat_variants = [mat_raw.lower(), mat_clean]
            if "termofus" in mat_clean or "termo fus" in mat_clean:
                mat_variants.extend(["termofusion", "termofusión", "termo fusion", "termo fusión"])
            elif "acero" in mat_clean or "hierro" in mat_clean:
                mat_variants.extend(["acero", "hierro"])
            elif "pvc" in mat_clean:
                mat_variants.append("pvc")

            mat_predicates = [
                func.lower(func.coalesce(VendorProduct.material_type, VendorProduct.normalized_description)).contains(v)
                for v in set(mat_variants)
            ]
            conditions.append(or_(*mat_predicates))

        candidates = db.scalars(select(VendorProduct).where(and_(*conditions))).all()

        # 4. Invariante: Cero Sustitución Ciega
        if not candidates:
            return VendorItemMatchResult(
                match_status="NOT_CARRIED",
                vendor_product_id=None,
                vendor_product=None,
                unit_price_applied_ars=None,
                line_subtotal_ars=None,
                similarity_score=None,
                match_origin="HARD_DIMENSION_FILTER",
            )

        # 5. Ranking léxico entre candidatos físicamente válidos (con soporte para alias canónico H-11)
        search_terms = [strip_accents(item.requested_term).lower()]
        raw_clean = strip_accents(item.raw_line).lower().strip()
        mat_clean_term = strip_accents(item.material_type or "").lower().strip()
        raw_with_material = f"{raw_clean} {mat_clean_term}".strip()
        for extra_term in (raw_with_material, raw_clean):
            if extra_term and extra_term not in search_terms:
                search_terms.append(extra_term)
        has_canonical_alias = False
        if alias and alias.canonical_term:
            canonical_clean = strip_accents(alias.canonical_term).lower()
            if canonical_clean and canonical_clean not in search_terms:
                search_terms.append(canonical_clean)
            has_canonical_alias = True

        scored_candidates: List[Tuple[float, VendorProduct]] = []
        for cand in candidates:
            best_term_score = max(
                compute_string_similarity(t, cand.normalized_description)
                for t in search_terms
            )
            if cand.brand and any(strip_accents(cand.brand).lower() in t for t in search_terms):
                best_term_score += 0.25
            if has_canonical_alias and best_term_score >= MIN_SIMILARITY_THRESHOLD:
                best_term_score = min(1.0, best_term_score + 0.15)
            scored_candidates.append((round(best_term_score, 4), cand))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        valid_candidates = [c for c in scored_candidates if c[0] >= MIN_SIMILARITY_THRESHOLD]
        if not valid_candidates:
            return VendorItemMatchResult(
                match_status="NOT_CARRIED",
                vendor_product_id=None,
                vendor_product=None,
                unit_price_applied_ars=None,
                line_subtotal_ars=None,
                similarity_score=scored_candidates[0][0] if scored_candidates else None,
                match_origin="BELOW_SIMILARITY_THRESHOLD",
            )

        in_stock_candidates = [c for c in valid_candidates if c[1].stock_available]
        if not in_stock_candidates:
            best_score, best_product = valid_candidates[0]
            return VendorItemMatchResult(
                match_status="OUT_OF_STOCK",
                vendor_product_id=best_product.id,
                vendor_product=best_product,
                unit_price_applied_ars=None,
                line_subtotal_ars=None,
                similarity_score=best_score,
                match_origin="STOCK_EXHAUSTED",
            )

        best_score, best_product = in_stock_candidates[0]

        # H-09: Detección efectiva de ambigüedad entre candidatos muy cercanos o confianza insuficiente
        is_close_tie = False
        if len(in_stock_candidates) >= 2:
            second_score, second_product = in_stock_candidates[1]
            if best_score < 0.95 and (best_score - second_score) < MIN_TOP_CANDIDATE_GAP:
                is_close_tie = True

        if best_score < MIN_AUTO_CONFIDENCE or is_close_tie:
            return VendorItemMatchResult(
                match_status="AMBIGUOUS_CANDIDATES",
                vendor_product_id=best_product.id,
                vendor_product=best_product,
                unit_price_applied_ars=None,
                line_subtotal_ars=None,
                similarity_score=best_score,
                match_origin="AMBIGUOUS_TOP_CANDIDATES" if is_close_tie else "LOW_CONFIDENCE_CANDIDATE",
                candidate_options=[
                    {
                        "vendor_product_id": str(prod.id),
                        "sku": prod.sku,
                        "description": prod.raw_description,
                        "sale_unit": prod.sale_unit,
                        "score": score,
                    }
                    for score, prod in in_stock_candidates[:5]
                ],
            )

        # H-07: Conversión de unidad comercial y validación de equivalencia segura
        comm_qty, _, conv_note, is_safe = cls.calculate_commercial_quantity(item, best_product)
        if not is_safe:
            return VendorItemMatchResult(
                match_status="AMBIGUOUS_CANDIDATES",
                vendor_product_id=best_product.id,
                vendor_product=best_product,
                unit_price_applied_ars=None,
                line_subtotal_ars=None,
                similarity_score=best_score,
                match_origin="UNIT_CONVERSION_CONFIRMATION_REQUIRED",
                commercial_qty=float(comm_qty),
                conversion_note=conv_note,
                candidate_options=[
                    {
                        "vendor_product_id": str(best_product.id),
                        "sku": best_product.sku,
                        "description": best_product.raw_description,
                        "sale_unit": best_product.sale_unit,
                        "score": best_score,
                    }
                ],
            )

        price = cls.resolve_effective_unit_price(best_product, vendor, payment_modality)
        subtotal = (price * comm_qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return VendorItemMatchResult(
            match_status="EXACT_MATCH",
            vendor_product_id=best_product.id,
            vendor_product=best_product,
            unit_price_applied_ars=price,
            line_subtotal_ars=subtotal,
            similarity_score=best_score,
            match_origin="SUPERVISED_ALIAS" if has_canonical_alias else "EXACT_DIMENSIONAL",
            commercial_qty=float(comm_qty),
            conversion_note=conv_note,
        )

    @classmethod
    def _satisfies_physical_constraints(cls, item: RequisitionItem, prod: VendorProduct) -> bool:
        """Verifica que un producto (incluyendo alias) no viole las dimensiones físicas del ítem."""
        if item.diameter_mm is not None:
            if prod.diameter_mm is None:
                return False
            allowed = UnitNormalizerService.get_equivalent_diameters_mm(
                diameter_mm=float(item.diameter_mm),
                material_type=item.material_type,
                diameter_inch=item.diameter_inch,
            )
            if not any(abs(float(prod.diameter_mm) - d) <= 0.5 for d in allowed):
                return False

        req_unit_norm = _normalize_commercial_unit(item.requested_unit)
        if item.length_m is not None and req_unit_norm != "M":
            if prod.length_m is None or abs(float(prod.length_m) - float(item.length_m)) > 0.05:
                return False
        if item.weight_kg is not None and req_unit_norm != "KG":
            if prod.weight_kg is None or abs(float(prod.weight_kg) - float(item.weight_kg)) > 0.5:
                return False
        if item.material_type is not None and prod.material_type:
            p_mat = strip_accents(prod.material_type).lower()
            i_mat = strip_accents(item.material_type).lower()
            if ("hierro" in p_mat or "acero" in p_mat) and ("hierro" in i_mat or "acero" in i_mat):
                pass
            elif p_mat != i_mat and not (p_mat in i_mat or i_mat in p_mat):
                return False
        return True
