"""Motor de emparejamiento físico-léxico multi-catálogo con Cero Sustitución Ciega."""

import uuid
from decimal import Decimal
from typing import Optional, List, Tuple
from dataclasses import dataclass
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session

from app.models.vendor import Vendor, PriceList, VendorProduct, ProductAlias
from app.models.requisition import RequisitionItem
from app.core.exceptions import AmbiguousItemCannotBeMatchedError
from app.services.unit_normalizer import strip_accents


@dataclass
class VendorItemMatchResult:
    match_status: str  # 'EXACT_MATCH' | 'AMBIGUOUS_CANDIDATES' | 'OUT_OF_STOCK' | 'NOT_CARRIED'
    vendor_product_id: Optional[uuid.UUID]
    vendor_product: Optional[VendorProduct]
    unit_price_applied_ars: Optional[Decimal]
    line_subtotal_ars: Optional[Decimal]
    similarity_score: Optional[float]
    match_origin: str = "EXACT_DIMENSIONAL"


def compute_string_similarity(s1: str, s2: str) -> float:
    """Calcula similitud de Jaccard y trigramas determinista entre dos cadenas."""
    w1 = set(strip_accents(s1).lower().split())
    w2 = set(strip_accents(s2).lower().split())
    if not w1 or not w2:
        return 0.0
    intersection = w1.intersection(w2)
    union = w1.union(w2)
    word_jaccard = len(intersection) / len(union)

    # Trigramas
    t1 = set(s1[i : i + 3] for i in range(len(s1) - 2)) if len(s1) >= 3 else {s1}
    t2 = set(s2[i : i + 3] for i in range(len(s2) - 2)) if len(s2) >= 3 else {s2}
    trigram_sim = len(t1.intersection(t2)) / len(t1.union(t2)) if t1 and t2 else 0.0

    return round(0.6 * word_jaccard + 0.4 * trigram_sim, 4)


class MatchingEngineService:
    """Servicio de búsqueda y validación dimensional estricta por comercio."""

    @classmethod
    def match_item_against_vendor(
        cls,
        db: Session,
        workspace_id: uuid.UUID,
        item: RequisitionItem,
        vendor_id: uuid.UUID,
        payment_modality: str = "CASH",
    ) -> VendorItemMatchResult:
        """Empareja un ítem del pedido contra el catálogo activo de un comercio.
        
        Sigue el orden estricto de reglas:
        1. Guarda de completitud (bloqueo ante missing_critical_attribute).
        2. Memoria de alias supervisados.
        3. Filtro Dimensional Duro SQL.
        4. Cero sustitución ciega (NOT_CARRIED si no existe la medida).
        5. Ranking léxico.
        """
        # 1. Regla de Oro: Bloqueo ante atributos críticos faltantes
        if item.completeness == "missing_critical_attribute":
            raise AmbiguousItemCannotBeMatchedError(
                item_id=str(item.id),
                message=item.clarification_prompt or "El ítem requiere aclaración técnica previa al emparejamiento."
            )

        # 2. Prioridad de Alias Supervisado en el Workspace
        alias = db.scalar(
            select(ProductAlias)
            .where(
                ProductAlias.workspace_id == workspace_id,
                or_(ProductAlias.vendor_id == vendor_id, ProductAlias.vendor_id.is_(None)),
                or_(
                    ProductAlias.alias_term == item.requested_term,
                    ProductAlias.alias_term == item.raw_line.strip(),
                ),
                ProductAlias.is_active == True,
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
                    PriceList.is_active == True,
                )
            )
            if target_prod and cls._satisfies_physical_constraints(item, target_prod):
                price = (
                    target_prod.price_cash_ars
                    if payment_modality == "CASH"
                    else target_prod.price_list_ars
                )
                subtotal = price * item.quantity
                return VendorItemMatchResult(
                    match_status="EXACT_MATCH",
                    vendor_product_id=target_prod.id,
                    vendor_product=target_prod,
                    unit_price_applied_ars=price,
                    line_subtotal_ars=subtotal,
                    similarity_score=1.0,
                    match_origin="SUPERVISED_ALIAS",
                )

        # 3. Consulta con Filtro Dimensional Duro SQL sobre la lista activa
        active_price_list = db.scalar(
            select(PriceList)
            .where(PriceList.vendor_id == vendor_id, PriceList.is_active == True)
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

        # Construir predicados SQL de tolerancia estricta
        conditions = [
            VendorProduct.price_list_id == active_price_list.id,
            VendorProduct.vendor_id == vendor_id,
        ]

        if item.diameter_mm is not None:
            # Tolerancia máxima: +- 0.5 mm y NO puede ser nulo
            conditions.append(VendorProduct.diameter_mm.is_not(None))
            conditions.append(func.abs(VendorProduct.diameter_mm - item.diameter_mm) <= 0.5)

        if item.length_m is not None:
            # Tolerancia máxima: +- 0.05 m
            conditions.append(VendorProduct.length_m.is_not(None))
            conditions.append(func.abs(VendorProduct.length_m - item.length_m) <= 0.05)

        if item.weight_kg is not None:
            # Tolerancia máxima: +- 0.5 kg
            conditions.append(VendorProduct.weight_kg.is_not(None))
            conditions.append(func.abs(VendorProduct.weight_kg - item.weight_kg) <= 0.5)

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

        stmt = select(VendorProduct).where(and_(*conditions))
        candidates = db.scalars(stmt).all()

        # 4. Invariante: Cero Sustitución Ciega
        # Si ningún producto cumple la medida física exacta, el comercio NO lo trabaja
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

        # 5. Ranking léxico entre los candidatos físicamente válidos
        MIN_SIMILARITY_THRESHOLD = 0.20
        scored_candidates: List[Tuple[float, VendorProduct]] = []
        term_clean = strip_accents(item.requested_term).lower()
        
        for cand in candidates:
            score = compute_string_similarity(term_clean, cand.normalized_description)
            # Bonificación si la marca solicitada coincide con la marca o descripción del producto
            if cand.brand and strip_accents(cand.brand).lower() in term_clean:
                score += 0.25
            scored_candidates.append((score, cand))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # Filtrar candidatos que cumplan el umbral mínimo de similitud
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

        # Buscar el mejor candidato que tenga stock disponible
        in_stock_candidates = [c for c in valid_candidates if c[1].stock_available]
        if in_stock_candidates:
            best_score, best_product = in_stock_candidates[0]
            price = (
                best_product.price_cash_ars
                if payment_modality == "CASH"
                else best_product.price_list_ars
            )
            subtotal = price * item.quantity

            return VendorItemMatchResult(
                match_status="EXACT_MATCH",
                vendor_product_id=best_product.id,
                vendor_product=best_product,
                unit_price_applied_ars=price,
                line_subtotal_ars=subtotal,
                similarity_score=best_score,
                match_origin="EXACT_DIMENSIONAL",
            )
        else:
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

    @classmethod
    def _satisfies_physical_constraints(cls, item: RequisitionItem, prod: VendorProduct) -> bool:
        """Verifica que un producto de alias no viole las dimensiones físicas del ítem."""
        if item.diameter_mm is not None:
            if prod.diameter_mm is None or abs(prod.diameter_mm - item.diameter_mm) > 0.5:
                return False
        if item.length_m is not None:
            if prod.length_m is None or abs(prod.length_m - item.length_m) > 0.05:
                return False
        if item.weight_kg is not None:
            if prod.weight_kg is None or abs(prod.weight_kg - item.weight_kg) > 0.5:
                return False
        if item.material_type is not None:
            if prod.material_type:
                p_mat = strip_accents(prod.material_type).lower()
                i_mat = strip_accents(item.material_type).lower()
                if ("hierro" in p_mat or "acero" in p_mat) and ("hierro" in i_mat or "acero" in i_mat):
                    pass
                elif p_mat != i_mat and not (p_mat in i_mat or i_mat in p_mat):
                    return False
        return True
