"""Algoritmo de compulsa multi-negocio, Compra Dividida Óptima (Branch-and-Bound) y Simulador de Acopio."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AmbiguousItemCannotBeMatchedError,
    CompulsaDomainException,
    LockedBudgetModificationError,
    WorkspaceIsolationError,
)
from app.core.security import compute_matrix_snapshot_hash, generate_hmac_share_token
from app.models.comparison import ComparisonItemMatch, ComparisonRun
from app.models.requisition import Requisition, RequisitionItem
from app.models.vendor import Vendor, VendorProduct
from app.schemas.comparison import (
    ComparisonItemCell,
    ComparisonItemRow,
    ComparisonMatrixResponse,
    ComparisonVendorSummary,
    SplitCartSummary,
)
from app.services.matching_engine import MatchingEngineService
from app.services.unit_normalizer import UnitNormalizerService, strip_accents

_TWO_PLACES = Decimal("0.01")


def _d(val: Any) -> Decimal:
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def _q2(val: Decimal) -> Decimal:
    return val.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _money(val: Any) -> float:
    return float(_q2(_d(val)))


class ComparisonOptimizerService:
    """Motor de cálculo comparativo, optimización logística Branch-and-Bound y acopio."""

    @classmethod
    def detect_technical_discrepancies(
        cls,
        req_item: RequisitionItem,
        prod: VendorProduct,
    ) -> List[str]:
        """Valida las 4 dimensiones críticas entre ítem pedido y producto alternativo (H-10)."""
        discrepancies: List[str] = []

        if req_item.material_type is not None:
            if not prod.material_type:
                discrepancies.append(
                    f"Material sin especificar en producto: solicitado '{req_item.material_type}'."
                )
            else:
                p_mat = strip_accents(prod.material_type).lower()
                i_mat = strip_accents(req_item.material_type).lower()
                both_steel = ("hierro" in p_mat or "acero" in p_mat) and (
                    "hierro" in i_mat or "acero" in i_mat
                )
                if not both_steel and p_mat != i_mat and not (p_mat in i_mat or i_mat in p_mat):
                    discrepancies.append(
                        f"Material incompatible: solicitado '{req_item.material_type}' vs producto '{prod.material_type}'."
                    )

        if req_item.diameter_mm is not None:
            if prod.diameter_mm is None:
                discrepancies.append(
                    f"Diámetro incompatible: solicitado Ø {float(req_item.diameter_mm):g} mm vs producto sin diámetro."
                )
            else:
                allowed_diameters = UnitNormalizerService.get_equivalent_diameters_mm(
                    diameter_mm=float(req_item.diameter_mm),
                    material_type=req_item.material_type,
                    diameter_inch=req_item.diameter_inch,
                )
                if not any(abs(float(prod.diameter_mm) - eq_d) <= 0.5 for eq_d in allowed_diameters):
                    discrepancies.append(
                        f"Diámetro incompatible: solicitado Ø {float(req_item.diameter_mm):g} mm vs producto Ø {float(prod.diameter_mm):g} mm."
                    )

        req_unit = (req_item.requested_unit or "UN").strip().upper()
        if req_item.length_m is not None and req_unit not in {"M", "MT", "MTS", "METRO", "METROS"}:
            if prod.length_m is None or abs(float(prod.length_m) - float(req_item.length_m)) > 0.05:
                discrepancies.append(
                    f"Longitud incompatible: solicitado {float(req_item.length_m):g} m vs producto {prod.length_m} m."
                )

        if req_item.weight_kg is not None and req_unit not in {"KG", "KILO", "KILOS"}:
            if prod.weight_kg is None or abs(float(prod.weight_kg) - float(req_item.weight_kg)) > 0.5:
                discrepancies.append(
                    f"Peso incompatible: solicitado {float(req_item.weight_kg):g} kg vs producto {prod.weight_kg} kg."
                )

        return discrepancies

    @classmethod
    def compute_fulfillment_status(
        cls,
        matrix_rows: List[Dict[str, Any]],
    ) -> Tuple[str, int, int]:
        """Calcula estado de completitud: complete | partial | pending (H-08)."""
        if not matrix_rows:
            return "pending", 0, 0

        unresolved_count = 0
        ambiguous_count = 0
        covered_count = 0

        for row in matrix_rows:
            cells = row.get("vendor_cells", [])
            has_exact = any(c.get("match_status") == "EXACT_MATCH" for c in cells)
            has_ambiguous = any(c.get("match_status") == "AMBIGUOUS_CANDIDATES" for c in cells)
            if has_exact:
                covered_count += 1
            else:
                unresolved_count += 1
                if has_ambiguous:
                    ambiguous_count += 1

        if ambiguous_count > 0 or covered_count == 0:
            return "pending", unresolved_count, ambiguous_count
        if unresolved_count > 0:
            return "partial", unresolved_count, 0
        return "complete", 0, 0

    @classmethod
    def run_multi_vendor_comparison(
        cls,
        db: Session,
        requisition_id: uuid.UUID,
        vendor_ids: List[uuid.UUID],
        payment_modality: str = "CASH",
        markup_pct: float = 0.0,
        include_delivery_fees: bool = True,
        budget_strategy: str = "SPLIT_CART",
        selected_single_vendor_id: Optional[uuid.UUID] = None,
        existing_run_id: Optional[uuid.UUID] = None,
        persist: bool = True,
    ) -> ComparisonMatrixResponse:
        """Ejecuta la compulsa completa entre comercios seleccionados con optimización Branch-and-Bound."""
        req = db.scalar(select(Requisition).where(Requisition.id == requisition_id))
        if not req:
            raise CompulsaDomainException("Requisición no encontrada", code="REQUISITION_NOT_FOUND")

        if req.status == "LOCKED_BUDGET":
            raise LockedBudgetModificationError(
                "La requisición está congelada como presupuesto definitivo (LOCKED_BUDGET) y no admite modificaciones ni nuevas compulsas."
            )

        items = db.scalars(
            select(RequisitionItem)
            .where(RequisitionItem.requisition_id == requisition_id)
            .order_by(RequisitionItem.line_order)
        ).all()

        if not items:
            raise CompulsaDomainException("La requisición no contiene ítems", code="EMPTY_REQUISITION")

        for it in items:
            if it.completeness == "missing_critical_attribute" or not it.is_confirmed:
                raise AmbiguousItemCannotBeMatchedError(
                    item_id=str(it.id),
                    message=f"El ítem '{it.requested_term}' requiere confirmación técnica previa a la compulsa.",
                )

        vendors = db.scalars(
            select(Vendor).where(
                Vendor.id.in_(vendor_ids),
                or_(Vendor.workspace_id == req.workspace_id, Vendor.is_public_directory.is_(True)),
            )
        ).all()

        if len(vendors) < len(set(vendor_ids)):
            raise WorkspaceIsolationError(
                "Uno o más comercios solicitados no pertenecen a su espacio de trabajo ni al directorio público."
            )

        if not vendors:
            raise CompulsaDomainException("No se encontraron comercios válidos para comparar", code="NO_VENDORS")

        existing_run: Optional[ComparisonRun] = None
        if persist and existing_run_id is not None:
            existing_run = db.scalar(
                select(ComparisonRun).where(
                    ComparisonRun.id == existing_run_id,
                    ComparisonRun.requisition_id == req.id,
                    ComparisonRun.workspace_id == req.workspace_id,
                )
            )
            if existing_run:
                prev_status = (
                    existing_run.comparison_matrix_json.get("status")
                    if isinstance(existing_run.comparison_matrix_json, dict)
                    else None
                )
                if prev_status == "LOCKED_BUDGET":
                    raise LockedBudgetModificationError(
                        "La compulsa referenciada está congelada (LOCKED_BUDGET)."
                    )

        run_id = existing_run.id if existing_run else uuid.uuid4()
        matrix_rows: List[ComparisonItemRow] = []
        vendor_matches_by_id: Dict[uuid.UUID, List[Dict[str, Any]]] = {v.id: [] for v in vendors}
        item_matches_to_save: List[ComparisonItemMatch] = []

        for it in items:
            row_cells: List[ComparisonItemCell] = []
            best_cell_sub: Optional[Decimal] = None
            best_cell_unit: Optional[Decimal] = None
            cheapest_v_id: Optional[uuid.UUID] = None

            for v in vendors:
                match_res = MatchingEngineService.match_item_against_vendor(
                    db=db,
                    workspace_id=req.workspace_id,
                    item=it,
                    vendor_id=v.id,
                    payment_modality=payment_modality,
                )

                unit_dec = (
                    _q2(match_res.unit_price_applied_ars)
                    if match_res.unit_price_applied_ars is not None
                    else None
                )
                sub_dec = (
                    _q2(match_res.line_subtotal_ars)
                    if match_res.line_subtotal_ars is not None
                    else None
                )
                unit_p = float(unit_dec) if unit_dec is not None else None
                line_sub = float(sub_dec) if sub_dec is not None else None
                cell_match_id = uuid.uuid4()

                cell = ComparisonItemCell(
                    match_id=cell_match_id,
                    vendor_id=v.id,
                    vendor_name=v.name,
                    match_status=match_res.match_status,
                    vendor_product_id=match_res.vendor_product_id,
                    product_sku=match_res.vendor_product.sku if match_res.vendor_product else None,
                    product_description=match_res.vendor_product.raw_description if match_res.vendor_product else None,
                    sale_unit=match_res.vendor_product.sale_unit if match_res.vendor_product else None,
                    commercial_qty=match_res.commercial_qty,
                    conversion_note=match_res.conversion_note,
                    unit_price_ars=unit_p,
                    line_subtotal_ars=line_sub,
                    similarity_score=match_res.similarity_score,
                    is_best_price=False,
                    is_selected_split=False,
                    candidate_options=match_res.candidate_options,
                )
                row_cells.append(cell)

                vendor_matches_by_id[v.id].append({
                    "item_id": it.id,
                    "match_res": match_res,
                    "cell": cell,
                })

                if sub_dec is not None and (best_cell_sub is None or sub_dec < best_cell_sub):
                    best_cell_sub = sub_dec
                    best_cell_unit = unit_dec
                    cheapest_v_id = v.id

                match_rec = ComparisonItemMatch(
                    id=cell_match_id,
                    comparison_run_id=run_id,
                    requisition_item_id=it.id,
                    vendor_id=v.id,
                    vendor_product_id=match_res.vendor_product_id,
                    match_status=match_res.match_status,
                    unit_price_applied_ars=unit_dec,
                    line_subtotal_ars=sub_dec,
                    similarity_score=(
                        Decimal(str(match_res.similarity_score))
                        if match_res.similarity_score is not None
                        else None
                    ),
                    is_selected_for_split_cart=False,
                )
                item_matches_to_save.append(match_rec)

            lowest_sub_f = float(best_cell_sub) if best_cell_sub is not None else None
            lowest_unit_f = float(best_cell_unit) if best_cell_unit is not None else None
            if cheapest_v_id is not None:
                for c in row_cells:
                    if c.vendor_id == cheapest_v_id and c.match_status == "EXACT_MATCH":
                        c.is_best_price = True

            matrix_rows.append(
                ComparisonItemRow(
                    requisition_item_id=it.id,
                    line_order=it.line_order,
                    requested_term=it.requested_term,
                    quantity=float(it.quantity),
                    requested_unit=it.requested_unit,
                    diameter_mm=float(it.diameter_mm) if it.diameter_mm is not None else None,
                    length_m=float(it.length_m) if it.length_m is not None else None,
                    weight_kg=float(it.weight_kg) if it.weight_kg is not None else None,
                    material_type=it.material_type,
                    vendor_cells=row_cells,
                    lowest_unit_price_ars=lowest_unit_f,
                    lowest_line_subtotal_ars=lowest_sub_f,
                    lowest_price_ars=lowest_sub_f,
                    winning_vendor_id=cheapest_v_id,
                )
            )

        # 2. Resúmenes por comercio y Simulación de Acopio (precisión Decimal H-13)
        vendor_summaries: List[ComparisonVendorSummary] = []
        now = datetime.now(timezone.utc)

        for v in vendors:
            v_matches = vendor_matches_by_id[v.id]
            matched_count = sum(1 for m in v_matches if m["match_res"].match_status == "EXACT_MATCH")
            missing_count = len(items) - matched_count
            coverage_pct = round((matched_count / len(items)) * 100.0, 2)

            materials_subtotal_dec = sum(
                (
                    _d(m["match_res"].line_subtotal_ars)
                    for m in v_matches
                    if m["match_res"].line_subtotal_ars is not None
                ),
                Decimal("0.00"),
            )
            delivery_fee_dec = (
                _q2(_d(v.estimate_delivery_fee_ars)) if include_delivery_fees else Decimal("0.00")
            )
            total_with_delivery_dec = _q2(materials_subtotal_dec + delivery_fee_dec)

            acopio_cfg = v.acopio_config_json or {}
            acopio_summary = None
            if acopio_cfg.get("enabled", False):
                down_pct_dec = _d(acopio_cfg.get("min_down_payment_pct", 100.0))
                freeze_days = int(acopio_cfg.get("freeze_days", 30))
                max_days = int(acopio_cfg.get("max_withdrawal_days", 60))
                notice_hrs = int(acopio_cfg.get("min_notice_hours", 24))

                down_payment_dec = _q2(total_with_delivery_dec * down_pct_dec / Decimal("100"))
                balance_dec = _q2(total_with_delivery_dec - down_payment_dec)
                freeze_date = now + timedelta(days=freeze_days)
                max_date = now + timedelta(days=max_days)

                acopio_summary = {
                    "enabled": True,
                    "min_down_payment_pct": float(down_pct_dec),
                    "down_payment_ars": float(down_payment_dec),
                    "remaining_balance_ars": float(balance_dec),
                    "freeze_days": freeze_days,
                    "freeze_until_date": freeze_date.isoformat(),
                    "max_withdrawal_days": max_days,
                    "max_withdrawal_date": max_date.isoformat(),
                    "min_notice_hours": notice_hrs,
                }

            vendor_summaries.append(
                ComparisonVendorSummary(
                    vendor_id=v.id,
                    vendor_name=v.name,
                    locality=v.locality,
                    coverage_pct=coverage_pct,
                    matched_items_count=matched_count,
                    missing_items_count=missing_count,
                    materials_subtotal_ars=float(_q2(materials_subtotal_dec)),
                    delivery_fee_ars=float(delivery_fee_dec),
                    total_with_delivery_ars=float(total_with_delivery_dec),
                    acopio_summary=acopio_summary,
                )
            )

        sorted_vendors = sorted(
            vendor_summaries,
            key=lambda x: (-x.coverage_pct, x.total_with_delivery_ars),
        )
        best_single = sorted_vendors[0] if sorted_vendors else None
        best_single_id = best_single.vendor_id if best_single else None
        best_single_name = best_single.vendor_name if best_single else None
        best_single_total = best_single.total_with_delivery_ars if best_single else None

        split_summary, split_winners_map = cls._optimize_split_cart(
            matrix_rows=matrix_rows,
            vendors=vendors,
            include_delivery_fees=include_delivery_fees,
            best_single=best_single,
        )

        for row in matrix_rows:
            split_vid = split_winners_map.get(row.requisition_item_id)
            if split_vid:
                for c in row.vendor_cells:
                    if c.vendor_id == split_vid:
                        c.is_selected_split = True

        for match_rec in item_matches_to_save:
            split_vid = split_winners_map.get(match_rec.requisition_item_id)
            if split_vid and match_rec.vendor_id == split_vid:
                match_rec.is_selected_for_split_cart = True

        serialized_rows = [r.model_dump(mode="json") for r in matrix_rows]
        fulfillment_status, unresolved_count, ambiguous_count = cls.compute_fulfillment_status(
            serialized_rows
        )

        effective_single_vendor_id = selected_single_vendor_id or best_single_id
        matrix_response = ComparisonMatrixResponse(
            run_id=run_id,
            requisition_id=req.id,
            status="COMPARED",
            fulfillment_status=fulfillment_status,  # type: ignore[arg-type]
            unresolved_items_count=unresolved_count,
            ambiguous_items_count=ambiguous_count,
            payment_modality=payment_modality,  # type: ignore[arg-type]
            markup_pct=markup_pct,
            include_delivery_fees=include_delivery_fees,
            budget_strategy=budget_strategy,  # type: ignore[arg-type]
            selected_single_vendor_id=effective_single_vendor_id,
            best_single_vendor_id=best_single_id,
            best_single_vendor_name=best_single_name,
            best_single_total_ars=best_single_total,
            split_cart=split_summary,
            vendors=vendor_summaries,
            matrix_rows=matrix_rows,
            public_share_token="",
            created_at=now,
        )

        matrix_dump = matrix_response.model_dump(mode="json")
        snapshot_hash = compute_matrix_snapshot_hash(matrix_dump)
        public_token = generate_hmac_share_token(str(run_id), str(req.id), matrix_dump)
        matrix_dump["snapshot_content_hash"] = snapshot_hash
        matrix_dump["public_share_token"] = public_token
        matrix_response.snapshot_content_hash = snapshot_hash
        matrix_response.public_share_token = public_token

        if persist:
            if existing_run:
                db.execute(
                    delete(ComparisonItemMatch).where(
                        ComparisonItemMatch.comparison_run_id == existing_run.id
                    )
                )
                existing_run.payment_modality = payment_modality
                existing_run.markup_pct = _d(markup_pct)
                existing_run.best_single_vendor_id = best_single_id
                existing_run.best_single_total_ars = (
                    _d(best_single_total) if best_single_total is not None else None
                )
                existing_run.split_cart_total_ars = _d(split_summary.total_cart_ars)
                existing_run.split_cart_savings_ars = _d(split_summary.savings_vs_single_vendor_ars)
                existing_run.comparison_matrix_json = matrix_dump
                existing_run.public_share_token = public_token
                db.add_all(item_matches_to_save)
            else:
                comparison_run = ComparisonRun(
                    id=run_id,
                    requisition_id=req.id,
                    workspace_id=req.workspace_id,
                    payment_modality=payment_modality,
                    markup_pct=_d(markup_pct),
                    best_single_vendor_id=best_single_id,
                    best_single_total_ars=(
                        _d(best_single_total) if best_single_total is not None else None
                    ),
                    split_cart_total_ars=_d(split_summary.total_cart_ars),
                    split_cart_savings_ars=_d(split_summary.savings_vs_single_vendor_ars),
                    comparison_matrix_json=matrix_dump,
                    public_share_token=public_token,
                    created_at=now,
                )
                db.add(comparison_run)
                db.add_all(item_matches_to_save)

            req.status = "COMPARED"
            db.commit()

        return matrix_response

    @classmethod
    def _solve_split_cart_bnb(
        cls,
        item_prices: Dict[str, Dict[str, Decimal]],
        vendor_fees: Dict[str, Decimal],
    ) -> Tuple[int, Decimal, Decimal, Decimal, Set[str], Dict[str, str]]:
        """Resuelve el problema exacto de Facility Location / Split Cart mediante Branch-and-Bound (H-12)."""
        coverable = [(iid, prices) for iid, prices in item_prices.items() if prices]
        if not coverable:
            return 0, Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), set(), {}

        # Poda de proveedores estrictamente dominados (mayor/igual flete y mayor/igual precio en todos los ítems)
        all_vendors = sorted({vid for _, prices in coverable for vid in prices})
        active_vendors_pool: List[str] = []
        for va in all_vendors:
            dominated = False
            for vb in active_vendors_pool:
                if vendor_fees.get(vb, Decimal("0")) <= vendor_fees.get(va, Decimal("0")):
                    if all(
                        (vb in prices and prices[vb] <= prices[va])
                        for _, prices in coverable
                        if va in prices
                    ):
                        dominated = True
                        break
            if not dominated:
                # Revalidar contra previos en caso de orden distinto
                active_vendors_pool = [
                    vb
                    for vb in active_vendors_pool
                    if not (
                        vendor_fees.get(va, Decimal("0")) <= vendor_fees.get(vb, Decimal("0"))
                        and all(
                            (va in prices and prices[va] <= prices[vb])
                            for _, prices in coverable
                            if vb in prices
                        )
                    )
                ]
                active_vendors_pool.append(va)

        pool_set = set(active_vendors_pool)
        filtered_coverable: List[Tuple[str, Dict[str, Decimal]]] = []
        for iid, prices in coverable:
            p_sub = {v: p for v, p in prices.items() if v in pool_set}
            filtered_coverable.append((iid, p_sub if p_sub else prices))

        # Identificar proveedores obligatorios (únicos que cubren algún ítem)
        mandatory_vendors: Set[str] = set()
        for _, prices in filtered_coverable:
            if len(prices) == 1:
                only_v = next(iter(prices))
                mandatory_vendors.add(only_v)

        initial_assign: Dict[str, str] = {}
        remaining_items: List[Tuple[str, Dict[str, Decimal]]] = []
        fixed_mat = Decimal("0.00")

        for iid, prices in filtered_coverable:
            global_min = min(prices.values())
            open_best = [v for v in mandatory_vendors if v in prices and prices[v] == global_min]
            if open_best:
                chosen_v = open_best[0]
                initial_assign[iid] = chosen_v
                fixed_mat += prices[chosen_v]
            else:
                remaining_items.append((iid, prices))

        fixed_fees = sum((vendor_fees.get(v, Decimal("0")) for v in mandatory_vendors), Decimal("0.00"))

        if not remaining_items:
            tot = _q2(fixed_mat + fixed_fees)
            return len(filtered_coverable), _q2(fixed_mat), _q2(fixed_fees), tot, set(mandatory_vendors), initial_assign

        # Ordenar ítems restantes por menor cantidad de candidatos y mayor dispersión de precio
        remaining_items.sort(key=lambda pair: (len(pair[1]), -max(pair[1].values()) + min(pair[1].values())))

        n_rem = len(remaining_items)
        suffix_min_mat: List[Decimal] = [Decimal("0.00")] * (n_rem + 1)
        for i in range(n_rem - 1, -1, -1):
            suffix_min_mat[i] = suffix_min_mat[i + 1] + min(remaining_items[i][1].values())

        # Cota superior inicial voraz + mejor proveedor único
        best_state: Dict[str, Any] = {"cost": None, "mat": Decimal("0"), "fee": Decimal("0"), "open": set(), "assign": {}}

        def _evaluate_candidate(cand_open: Set[str], cand_assign: Dict[str, str], mat_s: Decimal) -> None:
            used_only = set(cand_assign.values())
            fee_s = sum((vendor_fees.get(v, Decimal("0")) for v in used_only), Decimal("0.00"))
            tot_s = mat_s + fee_s
            b_cost = best_state["cost"]
            if b_cost is None or tot_s < b_cost or (tot_s == b_cost and len(used_only) < len(best_state["open"])):
                best_state["cost"] = tot_s
                best_state["mat"] = mat_s
                best_state["fee"] = fee_s
                best_state["open"] = used_only
                best_state["assign"] = dict(cand_assign)

        # Semilla 1: mejor proveedor único con cobertura total sobre filtered_coverable
        for v in active_vendors_pool:
            if all(v in prices for _, prices in filtered_coverable):
                a_map = {iid: v for iid, _ in filtered_coverable}
                m_sum = sum((prices[v] for _, prices in filtered_coverable), Decimal("0.00"))
                _evaluate_candidate({v}, a_map, m_sum)

        # Semilla 2: heurística voraz secuencial sobre remaining_items
        g_open = set(mandatory_vendors)
        g_assign = dict(initial_assign)
        g_mat = fixed_mat
        for iid, prices in remaining_items:
            best_v = min(
                prices.keys(),
                key=lambda vid: (
                    prices[vid] + (Decimal("0") if vid in g_open else vendor_fees.get(vid, Decimal("0"))),
                    prices[vid],
                ),
            )
            g_open.add(best_v)
            g_assign[iid] = best_v
            g_mat += prices[best_v]
        _evaluate_candidate(g_open, g_assign, g_mat)

        # Búsqueda exacta Branch-and-Bound
        nodes_visited = 0
        MAX_NODES = 250000

        def _dfs(
            idx: int,
            open_vs: Set[str],
            cur_mat: Decimal,
            cur_fee: Decimal,
            cur_assign: Dict[str, str],
        ) -> None:
            nonlocal nodes_visited
            nodes_visited += 1
            if nodes_visited > MAX_NODES:
                return

            b_cost = best_state["cost"]
            lb = cur_mat + cur_fee + suffix_min_mat[idx]
            if b_cost is not None:
                if lb > b_cost:
                    return
                if lb == b_cost and len(open_vs) >= len(best_state["open"]):
                    return

            if idx == n_rem:
                _evaluate_candidate(open_vs, cur_assign, cur_mat)
                return

            iid, prices = remaining_items[idx]
            open_candidates = [v for v in prices if v in open_vs]
            best_open_price = min((prices[v] for v in open_candidates), default=None)

            ordered_cands: List[str] = []
            if open_candidates:
                cheapest_open = min(open_candidates, key=lambda v: prices[v])
                ordered_cands.append(cheapest_open)

            new_cands = [
                v
                for v in prices
                if v not in open_vs and (best_open_price is None or prices[v] < best_open_price)
            ]
            new_cands.sort(key=lambda v: vendor_fees.get(v, Decimal("0")) + prices[v])
            ordered_cands.extend(new_cands)

            for cand_v in ordered_cands:
                is_new = cand_v not in open_vs
                added_fee = vendor_fees.get(cand_v, Decimal("0")) if is_new else Decimal("0")
                next_fee = cur_fee + added_fee
                next_mat = cur_mat + prices[cand_v]
                if b_cost is not None and (next_mat + next_fee + suffix_min_mat[idx + 1]) > b_cost:
                    continue
                if is_new:
                    open_vs.add(cand_v)
                cur_assign[iid] = cand_v
                _dfs(idx + 1, open_vs, next_mat, next_fee, cur_assign)
                cur_assign.pop(iid, None)
                if is_new:
                    open_vs.remove(cand_v)

        _dfs(0, set(mandatory_vendors), fixed_mat, fixed_fees, dict(initial_assign))

        return (
            len(filtered_coverable),
            _q2(best_state["mat"]),
            _q2(best_state["fee"]),
            _q2(best_state["cost"]),
            set(best_state["open"]),
            best_state["assign"],
        )

    @classmethod
    def _optimize_split_cart(
        cls,
        matrix_rows: List[ComparisonItemRow],
        vendors: List[Vendor],
        include_delivery_fees: bool,
        best_single: Optional[ComparisonVendorSummary],
    ) -> Tuple[SplitCartSummary, Dict[uuid.UUID, uuid.UUID]]:
        """Calcula el óptimo global del Carrito Dividido mediante Branch-and-Bound."""
        vendor_fees = {
            str(v.id): (_q2(_d(v.estimate_delivery_fee_ars)) if include_delivery_fees else Decimal("0.00"))
            for v in vendors
        }
        vendor_names = {str(v.id): v.name for v in vendors}
        total_items = len(matrix_rows)

        item_prices: Dict[str, Dict[str, Decimal]] = {}
        for r in matrix_rows:
            item_prices[str(r.requisition_item_id)] = {
                str(c.vendor_id): _q2(_d(c.line_subtotal_ars))
                for c in r.vendor_cells
                if c.match_status == "EXACT_MATCH" and c.line_subtotal_ars is not None
            }

        covered_count, mat_dec, fee_dec, tot_dec, used_vs, assigned_str = cls._solve_split_cart_bnb(
            item_prices=item_prices,
            vendor_fees=vendor_fees,
        )

        if covered_count == 0:
            return SplitCartSummary(
                total_materials_ars=0.0,
                total_delivery_fees_ars=0.0,
                total_cart_ars=0.0,
                participating_vendors_count=0,
                participating_vendor_names=[],
                savings_vs_single_vendor_ars=0.0,
                is_split_recommended=False,
            ), {}

        participating_names = [vendor_names[vid] for vid in used_vs if vid in vendor_names]
        best_single_total_dec = _d(best_single.total_with_delivery_ars) if (best_single and best_single.total_with_delivery_ars is not None) else None
        best_single_full_cov = best_single is not None and best_single.coverage_pct >= 100.0
        split_full_cov = covered_count == total_items

        if best_single_full_cov and split_full_cov and best_single_total_dec is not None:
            savings_dec = _q2(best_single_total_dec - tot_dec)
        else:
            savings_dec = Decimal("0.00")

        is_recommended = (
            savings_dec > Decimal("0.00")
            and len(used_vs) > 1
            and best_single_full_cov
            and split_full_cov
        )

        summary = SplitCartSummary(
            total_materials_ars=float(mat_dec),
            total_delivery_fees_ars=float(fee_dec),
            total_cart_ars=float(tot_dec),
            participating_vendors_count=len(used_vs),
            participating_vendor_names=participating_names,
            savings_vs_single_vendor_ars=float(savings_dec),
            is_split_recommended=is_recommended,
        )

        assigned_uuids = {uuid.UUID(k): uuid.UUID(v) for k, v in assigned_str.items()}
        return summary, assigned_uuids

    @classmethod
    def recalculate_matrix_totals(
        cls,
        matrix_dict: Dict[str, Any],
        vendors: List[Vendor],
        include_delivery_fees: bool,
    ) -> Dict[str, Any]:
        """Recalcula subtotales de línea, mejor proveedor único y Split Cart tras un override manual (H-01 / H-12 / H-13)."""
        now = datetime.now(timezone.utc)
        vendor_fees_dec = {
            str(v.id): (_q2(_d(v.estimate_delivery_fee_ars)) if include_delivery_fees else Decimal("0.00"))
            for v in vendors
        }
        vendor_names = {str(v.id): v.name for v in vendors}
        acopio_cfgs = {str(v.id): (v.acopio_config_json or {}) for v in vendors}
        localities = {str(v.id): v.locality for v in vendors}

        rows = matrix_dict.get("matrix_rows", [])
        total_rows = len(rows)
        vendor_materials: Dict[str, Decimal] = {str(v.id): Decimal("0.00") for v in vendors}
        vendor_matched: Dict[str, int] = {str(v.id): 0 for v in vendors}

        # 1. Recalcular menor subtotal de línea y menor unitario asociado SIN sobrescribir subtotal con unitario (H-01)
        for row in rows:
            best_sub: Optional[Decimal] = None
            best_unit: Optional[Decimal] = None
            winning_vid: Optional[str] = None
            for cell in row.get("vendor_cells", []):
                vid_str = str(cell.get("vendor_id"))
                m_status = cell.get("match_status")
                sub = cell.get("line_subtotal_ars")
                u_p = cell.get("unit_price_ars")

                if m_status == "EXACT_MATCH" and sub is not None:
                    sub_dec = _q2(_d(sub))
                    unit_dec = _q2(_d(u_p)) if u_p is not None else None
                    vendor_materials[vid_str] = vendor_materials.get(vid_str, Decimal("0.00")) + sub_dec
                    vendor_matched[vid_str] = vendor_matched.get(vid_str, 0) + 1

                    if best_sub is None or sub_dec < best_sub:
                        best_sub = sub_dec
                        best_unit = unit_dec
                        winning_vid = vid_str

            row["lowest_line_subtotal_ars"] = float(best_sub) if best_sub is not None else None
            row["lowest_unit_price_ars"] = float(best_unit) if best_unit is not None else None
            row["lowest_price_ars"] = float(best_sub) if best_sub is not None else None
            row["winning_vendor_id"] = winning_vid
            for cell in row.get("vendor_cells", []):
                cell["is_best_price"] = (
                    str(cell.get("vendor_id")) == winning_vid
                    and cell.get("match_status") == "EXACT_MATCH"
                )

        # 2. Resúmenes por comercio
        vendor_summaries_list: List[Dict[str, Any]] = []
        for v in vendors:
            vid_str = str(v.id)
            matched = vendor_matched.get(vid_str, 0)
            cov_pct = round((matched / total_rows) * 100.0, 2) if total_rows > 0 else 0.0
            mat_sub_dec = _q2(vendor_materials.get(vid_str, Decimal("0.00")))
            d_fee_dec = vendor_fees_dec.get(vid_str, Decimal("0.00"))
            tot_deliv_dec = _q2(mat_sub_dec + d_fee_dec)

            acopio_cfg = acopio_cfgs.get(vid_str, {})
            acopio_sum = None
            if acopio_cfg.get("enabled", False):
                down_pct_dec = _d(acopio_cfg.get("min_down_payment_pct", 100.0))
                freeze_days = int(acopio_cfg.get("freeze_days", 30))
                max_days = int(acopio_cfg.get("max_withdrawal_days", 60))
                notice_hrs = int(acopio_cfg.get("min_notice_hours", 24))

                down_payment_dec = _q2(tot_deliv_dec * down_pct_dec / Decimal("100"))
                balance_dec = _q2(tot_deliv_dec - down_payment_dec)

                acopio_sum = {
                    "enabled": True,
                    "min_down_payment_pct": float(down_pct_dec),
                    "down_payment_ars": float(down_payment_dec),
                    "remaining_balance_ars": float(balance_dec),
                    "freeze_days": freeze_days,
                    "freeze_until_date": (now + timedelta(days=freeze_days)).isoformat(),
                    "max_withdrawal_days": max_days,
                    "max_withdrawal_date": (now + timedelta(days=max_days)).isoformat(),
                    "min_notice_hours": notice_hrs,
                }

            vendor_summaries_list.append({
                "vendor_id": str(v.id),
                "vendor_name": v.name,
                "locality": localities.get(vid_str, ""),
                "coverage_pct": cov_pct,
                "matched_items_count": matched,
                "missing_items_count": total_rows - matched,
                "materials_subtotal_ars": float(mat_sub_dec),
                "delivery_fee_ars": float(d_fee_dec),
                "total_with_delivery_ars": float(tot_deliv_dec),
                "acopio_summary": acopio_sum,
            })

        sorted_v = sorted(
            vendor_summaries_list,
            key=lambda x: (-x["coverage_pct"], x["total_with_delivery_ars"]),
        )
        best_single = sorted_v[0] if sorted_v else None
        best_single_id = str(best_single["vendor_id"]) if best_single else None
        best_single_name = best_single["vendor_name"] if best_single else None
        best_single_total = best_single["total_with_delivery_ars"] if best_single else None

        # 3. Recalcular Split Cart con Branch-and-Bound
        item_prices: Dict[str, Dict[str, Decimal]] = {}
        for row in rows:
            item_id_str = str(row.get("requisition_item_id"))
            item_prices[item_id_str] = {
                str(c["vendor_id"]): _q2(_d(c["line_subtotal_ars"]))
                for c in row.get("vendor_cells", [])
                if c.get("match_status") == "EXACT_MATCH" and c.get("line_subtotal_ars") is not None
            }

        covered_count, mat_dec, fee_dec, tot_dec, used_v, assigned_map = cls._solve_split_cart_bnb(
            item_prices=item_prices,
            vendor_fees=vendor_fees_dec,
        )

        if covered_count > 0:
            for row in rows:
                item_id_str = str(row.get("requisition_item_id"))
                split_winner = assigned_map.get(item_id_str)
                for cell in row.get("vendor_cells", []):
                    cell["is_selected_split"] = str(cell.get("vendor_id")) == split_winner

            best_single_full = best_single is not None and best_single["coverage_pct"] >= 100.0
            split_full = covered_count == total_rows
            if best_single_full and split_full and best_single_total is not None:
                savings_dec = _q2(_d(best_single_total) - tot_dec)
            else:
                savings_dec = Decimal("0.00")

            split_summary_dict = {
                "total_materials_ars": float(mat_dec),
                "total_delivery_fees_ars": float(fee_dec),
                "total_cart_ars": float(tot_dec),
                "participating_vendors_count": len(used_v),
                "participating_vendor_names": [
                    vendor_names[vid] for vid in used_v if vid in vendor_names
                ],
                "savings_vs_single_vendor_ars": float(savings_dec),
                "is_split_recommended": (
                    savings_dec > Decimal("0.00")
                    and len(used_v) > 1
                    and best_single_full
                    and split_full
                ),
            }
        else:
            split_summary_dict = {
                "total_materials_ars": 0.0,
                "total_delivery_fees_ars": 0.0,
                "total_cart_ars": 0.0,
                "participating_vendors_count": 0,
                "participating_vendor_names": [],
                "savings_vs_single_vendor_ars": 0.0,
                "is_split_recommended": False,
            }

        fulfillment_status, unresolved_count, ambiguous_count = cls.compute_fulfillment_status(rows)

        matrix_dict["vendors"] = vendor_summaries_list
        matrix_dict["best_single_vendor_id"] = best_single_id
        matrix_dict["best_single_vendor_name"] = best_single_name
        matrix_dict["best_single_total_ars"] = best_single_total
        matrix_dict["split_cart"] = split_summary_dict
        matrix_dict["fulfillment_status"] = fulfillment_status
        matrix_dict["unresolved_items_count"] = unresolved_count
        matrix_dict["ambiguous_items_count"] = ambiguous_count
        matrix_dict["snapshot_content_hash"] = compute_matrix_snapshot_hash(matrix_dict)

        return matrix_dict

    @classmethod
    def resolve_budget_lines_for_strategy(
        cls,
        matrix_data: Dict[str, Any],
        strategy: Optional[str] = None,
        single_vendor_id: Optional[str] = None,
        markup_pct: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Calcula líneas, fletes y totales del presupuesto cliente según estrategia explícita (H-02 / H-03)."""
        effective_strategy = (
            strategy or matrix_data.get("budget_strategy") or "SPLIT_CART"
        ).upper()
        if effective_strategy not in {"SPLIT_CART", "SINGLE_VENDOR"}:
            effective_strategy = "SPLIT_CART"

        effective_markup = _d(
            matrix_data.get("markup_pct", 0.0) if markup_pct is None else markup_pct
        )
        markup_mult = Decimal("1") + (effective_markup / Decimal("100"))
        include_fees = bool(matrix_data.get("include_delivery_fees", True))

        target_single_vid = (
            str(single_vendor_id)
            if single_vendor_id
            else (
                str(matrix_data.get("selected_single_vendor_id"))
                if matrix_data.get("selected_single_vendor_id")
                else (
                    str(matrix_data.get("best_single_vendor_id"))
                    if matrix_data.get("best_single_vendor_id")
                    else None
                )
            )
        )

        vendors_by_id = {
            str(v.get("vendor_id")): v for v in matrix_data.get("vendors", [])
        }
        rows = matrix_data.get("matrix_rows", [])

        lines: List[Dict[str, Any]] = []
        materials_total_dec = Decimal("0.00")
        participating_vendor_ids: Set[str] = set()
        has_unquoted_items = False

        for row in rows:
            cells = row.get("vendor_cells", [])
            chosen_cell: Optional[Dict[str, Any]] = None

            if effective_strategy == "SINGLE_VENDOR":
                if target_single_vid:
                    for c in cells:
                        if str(c.get("vendor_id")) == target_single_vid:
                            chosen_cell = c
                            break
            else:
                for c in cells:
                    if c.get("is_selected_split"):
                        chosen_cell = c
                        break

            req_qty = float(row.get("quantity", 1.0))
            req_unit = row.get("requested_unit", "UN")
            is_covered = (
                chosen_cell is not None
                and chosen_cell.get("match_status") == "EXACT_MATCH"
                and chosen_cell.get("line_subtotal_ars") is not None
            )

            if is_covered and chosen_cell is not None:
                participating_vendor_ids.add(str(chosen_cell.get("vendor_id")))
                comm_qty = chosen_cell.get("commercial_qty") or req_qty
                sale_unit = chosen_cell.get("sale_unit") or req_unit
                conv_note = chosen_cell.get("conversion_note")
                base_unit = _d(chosen_cell.get("unit_price_ars", 0.0))
                base_sub = _d(chosen_cell.get("line_subtotal_ars", 0.0))
                client_unit_dec = _q2(base_unit * markup_mult)
                client_sub_dec = _q2(base_sub * markup_mult)
                materials_total_dec += client_sub_dec

                lines.append({
                    "requisition_item_id": row.get("requisition_item_id"),
                    "line_order": int(row.get("line_order", 1)),
                    "canonical_name": row.get("requested_term", ""),
                    "requested_qty": req_qty,
                    "requested_unit": req_unit,
                    "commercial_qty": float(comm_qty),
                    "sale_unit": sale_unit,
                    "conversion_note": conv_note,
                    "client_unit_price_ars": float(client_unit_dec),
                    "client_subtotal_ars": float(client_sub_dec),
                    "covered": True,
                })
            else:
                has_unquoted_items = True
                lines.append({
                    "requisition_item_id": row.get("requisition_item_id"),
                    "line_order": int(row.get("line_order", 1)),
                    "canonical_name": row.get("requested_term", ""),
                    "requested_qty": req_qty,
                    "requested_unit": req_unit,
                    "commercial_qty": None,
                    "sale_unit": None,
                    "conversion_note": None,
                    "client_unit_price_ars": None,
                    "client_subtotal_ars": None,
                    "covered": False,
                })

        logistics_dec = Decimal("0.00")
        if include_fees:
            if effective_strategy == "SINGLE_VENDOR":
                if target_single_vid and target_single_vid in vendors_by_id:
                    logistics_dec = _q2(_d(vendors_by_id[target_single_vid].get("delivery_fee_ars", 0.0)))
            else:
                for vid in participating_vendor_ids:
                    if vid in vendors_by_id:
                        logistics_dec += _q2(_d(vendors_by_id[vid].get("delivery_fee_ars", 0.0)))

        materials_total_dec = _q2(materials_total_dec)
        logistics_dec = _q2(logistics_dec)
        grand_total_dec = _q2(materials_total_dec + logistics_dec)

        return {
            "strategy": effective_strategy,
            "selected_single_vendor_id": target_single_vid if effective_strategy == "SINGLE_VENDOR" else None,
            "lines": lines,
            "materials_subtotal_ars": float(materials_total_dec),
            "logistics_ars": float(logistics_dec),
            "grand_total_ars": float(grand_total_dec),
            "has_unquoted_items": has_unquoted_items,
            "include_delivery_fees": include_fees,
        }
