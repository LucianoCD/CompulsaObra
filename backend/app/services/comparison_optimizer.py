"""Algoritmo de compulsa multi-negocio, Compra Dividida Óptima y Simulador de Acopio."""

import uuid
import itertools
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Set, Tuple
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session

from app.models.vendor import Vendor
from app.models.requisition import Requisition, RequisitionItem
from app.models.comparison import ComparisonRun, ComparisonItemMatch
from app.schemas.comparison import (
    ComparisonMatrixResponse,
    ComparisonVendorSummary,
    ComparisonItemRow,
    ComparisonItemCell,
    SplitCartSummary,
)
from app.services.matching_engine import MatchingEngineService
from app.core.exceptions import (
    AmbiguousItemCannotBeMatchedError,
    CompulsaDomainException,
    LockedBudgetModificationError,
    WorkspaceIsolationError,
)
from app.core.security import generate_hmac_share_token


class ComparisonOptimizerService:
    """Motor de cálculo comparativo, optimización logística y acopio de materiales."""

    @classmethod
    def run_multi_vendor_comparison(
        cls,
        db: Session,
        requisition_id: uuid.UUID,
        vendor_ids: List[uuid.UUID],
        payment_modality: str = "CASH",
        markup_pct: float = 0.0,
        include_delivery_fees: bool = True,
    ) -> ComparisonMatrixResponse:
        """Ejecuta la compulsa completa entre los comercios seleccionados con optimización global."""
        req = db.scalar(select(Requisition).where(Requisition.id == requisition_id))
        if not req:
            raise CompulsaDomainException("Requisición no encontrada", code="REQUISITION_NOT_FOUND")

        # Invariante CO-05 / BUG-04: Bloquear compulsa si la requisición ya fue congelada
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

        # Verificar completitud previa
        for it in items:
            if it.completeness == "missing_critical_attribute" or not it.is_confirmed:
                raise AmbiguousItemCannotBeMatchedError(
                    item_id=str(it.id),
                    message=f"El ítem '{it.requested_term}' requiere confirmación técnica previa a la compulsa."
                )

        # Control estricto de aislamiento CO-04 / SEC-02: solo comercios propios o del directorio público
        vendors = db.scalars(
            select(Vendor).where(
                Vendor.id.in_(vendor_ids),
                or_(Vendor.workspace_id == req.workspace_id, Vendor.is_public_directory == True),
            )
        ).all()

        if len(vendors) < len(vendor_ids):
            raise WorkspaceIsolationError(
                "Uno o más comercios solicitados no pertenecen a su espacio de trabajo ni al directorio público."
            )

        if not vendors:
            raise CompulsaDomainException("No se encontraron comercios válidos para comparar", code="NO_VENDORS")

        # 1. Emparejar cada ítem contra cada comercio
        matrix_rows: List[ComparisonItemRow] = []
        vendor_matches_by_id: Dict[uuid.UUID, List[Dict[str, Any]]] = {v.id: [] for v in vendors}
        item_matches_to_save: List[ComparisonItemMatch] = []
        run_id = uuid.uuid4()

        for it in items:
            row_cells: List[ComparisonItemCell] = []
            best_cell_price = float("inf")
            cheapest_v_id: Optional[uuid.UUID] = None

            for v in vendors:
                match_res = MatchingEngineService.match_item_against_vendor(
                    db=db,
                    workspace_id=req.workspace_id,
                    item=it,
                    vendor_id=v.id,
                    payment_modality=payment_modality,
                )

                unit_p = float(match_res.unit_price_applied_ars) if match_res.unit_price_applied_ars is not None else None
                line_sub = float(match_res.line_subtotal_ars) if match_res.line_subtotal_ars is not None else None
                cell_match_id = uuid.uuid4()

                cell = ComparisonItemCell(
                    match_id=cell_match_id,
                    vendor_id=v.id,
                    vendor_name=v.name,
                    match_status=match_res.match_status,
                    vendor_product_id=match_res.vendor_product_id,
                    product_sku=match_res.vendor_product.sku if match_res.vendor_product else None,
                    product_description=match_res.vendor_product.raw_description if match_res.vendor_product else None,
                    unit_price_ars=unit_p,
                    line_subtotal_ars=line_sub,
                    similarity_score=match_res.similarity_score,
                    is_best_price=False,
                    is_selected_split=False,
                )
                row_cells.append(cell)

                vendor_matches_by_id[v.id].append({
                    "item_id": it.id,
                    "match_res": match_res,
                    "cell": cell,
                })

                if line_sub is not None and line_sub < best_cell_price:
                    best_cell_price = line_sub
                    cheapest_v_id = v.id

                # Preparar registro ORM
                match_rec = ComparisonItemMatch(
                    id=cell_match_id,
                    comparison_run_id=run_id,
                    requisition_item_id=it.id,
                    vendor_id=v.id,
                    vendor_product_id=match_res.vendor_product_id,
                    match_status=match_res.match_status,
                    unit_price_applied_ars=Decimal(str(unit_p)) if unit_p is not None else None,
                    line_subtotal_ars=Decimal(str(line_sub)) if line_sub is not None else None,
                    similarity_score=Decimal(str(match_res.similarity_score)) if match_res.similarity_score is not None else None,
                    is_selected_for_split_cart=False,
                )
                item_matches_to_save.append(match_rec)

            lowest_p = best_cell_price if cheapest_v_id is not None and best_cell_price < float("inf") else None
            if lowest_p is not None:
                for c in row_cells:
                    if c.vendor_id == cheapest_v_id:
                        c.is_best_price = True

            matrix_rows.append(
                ComparisonItemRow(
                    requisition_item_id=it.id,
                    line_order=it.line_order,
                    requested_term=it.requested_term,
                    quantity=float(it.quantity),
                    requested_unit=it.requested_unit,
                    diameter_mm=float(it.diameter_mm) if it.diameter_mm is not None else None,
                    material_type=it.material_type,
                    vendor_cells=row_cells,
                    lowest_price_ars=lowest_p,
                    winning_vendor_id=cheapest_v_id,
                )
            )

        # 2. Resúmenes por comercio y Simulación de Acopio
        vendor_summaries: List[ComparisonVendorSummary] = []
        now = datetime.now(timezone.utc)

        for v in vendors:
            v_matches = vendor_matches_by_id[v.id]
            matched_count = sum(1 for m in v_matches if m["match_res"].match_status == "EXACT_MATCH")
            missing_count = len(items) - matched_count
            coverage_pct = round((matched_count / len(items)) * 100.0, 2)

            materials_subtotal = sum(
                float(m["match_res"].line_subtotal_ars)
                for m in v_matches
                if m["match_res"].line_subtotal_ars is not None
            )

            delivery_fee = float(v.estimate_delivery_fee_ars) if include_delivery_fees else 0.0
            total_with_delivery = materials_subtotal + delivery_fee

            acopio_cfg = v.acopio_config_json or {}
            acopio_summary = None
            if acopio_cfg.get("enabled", False):
                down_pct = float(acopio_cfg.get("min_down_payment_pct", 100.0))
                freeze_days = int(acopio_cfg.get("freeze_days", 30))
                max_days = int(acopio_cfg.get("max_withdrawal_days", 60))
                notice_hrs = int(acopio_cfg.get("min_notice_hours", 24))

                down_payment = round(total_with_delivery * (down_pct / 100.0), 2)
                balance = round(total_with_delivery - down_payment, 2)
                freeze_date = now + timedelta(days=freeze_days)
                max_date = now + timedelta(days=max_days)

                acopio_summary = {
                    "enabled": True,
                    "min_down_payment_pct": down_pct,
                    "down_payment_ars": down_payment,
                    "remaining_balance_ars": balance,
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
                    materials_subtotal_ars=materials_subtotal,
                    delivery_fee_ars=delivery_fee,
                    total_with_delivery_ars=total_with_delivery,
                    acopio_summary=acopio_summary,
                )
            )

        # 3. Determinar Mejor Proveedor Único (mayor cobertura y luego menor costo total)
        sorted_vendors = sorted(
            vendor_summaries,
            key=lambda x: (-x.coverage_pct, x.total_with_delivery_ars),
        )
        best_single = sorted_vendors[0] if sorted_vendors else None
        best_single_id = best_single.vendor_id if best_single else None
        best_single_name = best_single.vendor_name if best_single else None
        best_single_total = best_single.total_with_delivery_ars if best_single else None

        # 4. Optimización Global de Split Cart por Subconjuntos (Cierre definitivo de CO-07)
        split_summary, split_winners_map = cls._optimize_split_cart(
            matrix_rows=matrix_rows,
            vendors=vendors,
            include_delivery_fees=include_delivery_fees,
            best_single=best_single,
        )

        # Asignar is_selected_split a las celdas ganadoras del subconjunto óptimo
        for row in matrix_rows:
            split_vid = split_winners_map.get(row.requisition_item_id)
            if split_vid:
                for c in row.vendor_cells:
                    if c.vendor_id == split_vid:
                        c.is_selected_split = True

        # Actualizar flag is_selected_for_split_cart en los registros ORM
        for match_rec in item_matches_to_save:
            split_vid = split_winners_map.get(match_rec.requisition_item_id)
            if split_vid and match_rec.vendor_id == split_vid:
                match_rec.is_selected_for_split_cart = True

        # 5. Persistir ComparisonRun y ComparisonItemMatch
        public_token = generate_hmac_share_token(str(run_id), str(req.id))

        matrix_response = ComparisonMatrixResponse(
            run_id=run_id,
            requisition_id=req.id,
            payment_modality=payment_modality,
            markup_pct=markup_pct,
            include_delivery_fees=include_delivery_fees,
            best_single_vendor_id=best_single_id,
            best_single_vendor_name=best_single_name,
            best_single_total_ars=best_single_total,
            split_cart=split_summary,
            vendors=vendor_summaries,
            matrix_rows=matrix_rows,
            public_share_token=public_token,
            created_at=now,
        )

        comparison_run = ComparisonRun(
            id=run_id,
            requisition_id=req.id,
            workspace_id=req.workspace_id,
            payment_modality=payment_modality,
            markup_pct=Decimal(str(markup_pct)),
            best_single_vendor_id=best_single_id,
            best_single_total_ars=Decimal(str(best_single_total)) if best_single_total is not None else None,
            split_cart_total_ars=Decimal(str(split_summary.total_cart_ars)),
            split_cart_savings_ars=Decimal(str(split_summary.savings_vs_single_vendor_ars)),
            comparison_matrix_json=matrix_response.model_dump(mode="json"),
            public_share_token=public_token,
            created_at=now,
        )
        db.add(comparison_run)
        db.add_all(item_matches_to_save)

        req.status = "COMPARED"
        db.commit()

        return matrix_response

    @classmethod
    def _optimize_split_cart(
        cls,
        matrix_rows: List[ComparisonItemRow],
        vendors: List[Vendor],
        include_delivery_fees: bool,
        best_single: Optional[ComparisonVendorSummary],
    ) -> Tuple[SplitCartSummary, Dict[uuid.UUID, uuid.UUID]]:
        """Calcula el óptimo global del Carrito Dividido evaluando todos los subconjuntos de proveedores.
        
        Minimiza C_total = sum(Materiales) + sum(Fletes únicos utilizados) a máxima cobertura alcanzable.
        """
        vendor_fees = {
            v.id: (float(v.estimate_delivery_fee_ars) if include_delivery_fees else 0.0)
            for v in vendors
        }
        vendor_names = {v.id: v.name for v in vendors}
        total_items = len(matrix_rows)

        # Mapa de precios por ítem y vendor: {item_id: {vendor_id: line_subtotal}}
        item_prices: Dict[uuid.UUID, Dict[uuid.UUID, float]] = {}
        for r in matrix_rows:
            item_prices[r.requisition_item_id] = {
                c.vendor_id: c.line_subtotal_ars
                for c in r.vendor_cells
                if c.match_status == "EXACT_MATCH" and c.line_subtotal_ars is not None
            }

        vendor_id_list = [v.id for v in vendors]
        best_plan: Optional[Dict[str, Any]] = None

        # Evaluar todos los subconjuntos no vacíos de comercios
        for r_size in range(1, len(vendor_id_list) + 1):
            for subset in itertools.combinations(vendor_id_list, r_size):
                subset_set = set(subset)
                covered_items_count = 0
                materials_subtotal = 0.0
                used_vendors: Set[uuid.UUID] = set()
                item_assigned_vendor: Dict[uuid.UUID, uuid.UUID] = {}

                for row in matrix_rows:
                    prices = item_prices[row.requisition_item_id]
                    # Elegir el proveedor más barato dentro del subconjunto actual
                    available_in_subset = [vid for vid in subset_set if vid in prices]
                    if available_in_subset:
                        covered_items_count += 1
                        cheapest_vid = min(available_in_subset, key=lambda vid: prices[vid])
                        materials_subtotal += prices[cheapest_vid]
                        used_vendors.add(cheapest_vid)
                        item_assigned_vendor[row.requisition_item_id] = cheapest_vid

                delivery_total = sum(vendor_fees[vid] for vid in used_vendors)
                total_cost = materials_subtotal + delivery_total

                # Criterio de comparación:
                # 1. Mayor cantidad de ítems cubiertos
                # 2. Menor costo total (materiales + fletes)
                # 3. Menor cantidad de proveedores utilizados
                is_better = False
                if best_plan is None:
                    is_better = True
                elif covered_items_count > best_plan["covered_count"]:
                    is_better = True
                elif covered_items_count == best_plan["covered_count"]:
                    if total_cost < best_plan["total_cost"] - 1e-4:
                        is_better = True
                    elif abs(total_cost - best_plan["total_cost"]) <= 1e-4 and len(used_vendors) < len(best_plan["used_vendors"]):
                        is_better = True

                if is_better:
                    best_plan = {
                        "covered_count": covered_items_count,
                        "materials_subtotal": materials_subtotal,
                        "delivery_total": delivery_total,
                        "total_cost": total_cost,
                        "used_vendors": used_vendors,
                        "item_assigned_vendor": item_assigned_vendor,
                    }

        if not best_plan:
            return SplitCartSummary(
                total_materials_ars=0.0,
                total_delivery_fees_ars=0.0,
                total_cart_ars=0.0,
                participating_vendors_count=0,
                participating_vendor_names=[],
                savings_vs_single_vendor_ars=0.0,
                is_split_recommended=False,
            ), {}

        used_vendor_ids = best_plan["used_vendors"]
        participating_names = [vendor_names[vid] for vid in used_vendor_ids if vid in vendor_names]

        # Cálculo de Ahorro: Solo se considera ahorro si tanto el mejor único como el split cart cubren el 100% de los ítems
        best_single_total = best_single.total_with_delivery_ars if best_single else None
        best_single_full_cov = best_single is not None and best_single.coverage_pct >= 100.0
        split_full_cov = best_plan["covered_count"] == total_items

        if best_single_full_cov and split_full_cov and best_single_total is not None:
            savings = round(best_single_total - best_plan["total_cost"], 2)
        else:
            savings = 0.0

        is_recommended = (
            savings > 0.0
            and len(used_vendor_ids) > 1
            and best_single_full_cov
            and split_full_cov
        )

        summary = SplitCartSummary(
            total_materials_ars=round(best_plan["materials_subtotal"], 2),
            total_delivery_fees_ars=round(best_plan["delivery_total"], 2),
            total_cart_ars=round(best_plan["total_cost"], 2),
            participating_vendors_count=len(used_vendor_ids),
            participating_vendor_names=participating_names,
            savings_vs_single_vendor_ars=savings,
            is_split_recommended=is_recommended,
        )

        return summary, best_plan["item_assigned_vendor"]

    @classmethod
    def recalculate_matrix_totals(
        cls,
        matrix_dict: Dict[str, Any],
        vendors: List[Vendor],
        include_delivery_fees: bool,
    ) -> Dict[str, Any]:
        """Recalcula subtotales, mejor proveedor único y split cart tras un override manual."""
        now = datetime.now(timezone.utc)
        vendor_fees = {
            str(v.id): (float(v.estimate_delivery_fee_ars) if include_delivery_fees else 0.0)
            for v in vendors
        }
        vendor_names = {str(v.id): v.name for v in vendors}
        acopio_cfgs = {str(v.id): (v.acopio_config_json or {}) for v in vendors}
        localities = {str(v.id): v.locality for v in vendors}

        total_rows = len(matrix_dict.get("matrix_rows", []))
        vendor_materials: Dict[str, float] = {str(v.id): 0.0 for v in vendors}
        vendor_matched: Dict[str, int] = {str(v.id): 0 for v in vendors}

        # 1. Recalcular menor precio unitario y ganador por fila
        for row in matrix_dict.get("matrix_rows", []):
            best_unit_price = None
            winning_vid = None
            for cell in row.get("vendor_cells", []):
                vid_str = str(cell.get("vendor_id"))
                m_status = cell.get("match_status")
                sub = cell.get("line_subtotal_ars")
                u_p = cell.get("unit_price_ars")

                if m_status == "EXACT_MATCH" and sub is not None:
                    vendor_materials[vid_str] = vendor_materials.get(vid_str, 0.0) + sub
                    vendor_matched[vid_str] = vendor_matched.get(vid_str, 0) + 1

                    if u_p is not None and (best_unit_price is None or u_p < best_unit_price):
                        best_unit_price = u_p
                        winning_vid = vid_str

            row["lowest_price_ars"] = best_unit_price
            row["winning_vendor_id"] = winning_vid
            for cell in row.get("vendor_cells", []):
                cell["is_best_price"] = (
                    str(cell.get("vendor_id")) == winning_vid
                    and cell.get("match_status") == "EXACT_MATCH"
                )

        # 2. Recalcular resúmenes por comercio
        vendor_summaries_list = []
        for v in vendors:
            vid_str = str(v.id)
            matched = vendor_matched.get(vid_str, 0)
            cov_pct = round((matched / total_rows) * 100.0, 2) if total_rows > 0 else 0.0
            mat_sub = vendor_materials.get(vid_str, 0.0)
            d_fee = vendor_fees.get(vid_str, 0.0)
            tot_deliv = mat_sub + d_fee

            acopio_cfg = acopio_cfgs.get(vid_str, {})
            acopio_sum = None
            if acopio_cfg.get("enabled", False):
                down_pct = float(acopio_cfg.get("min_down_payment_pct", 100.0))
                freeze_days = int(acopio_cfg.get("freeze_days", 30))
                max_days = int(acopio_cfg.get("max_withdrawal_days", 60))
                notice_hrs = int(acopio_cfg.get("min_notice_hours", 24))

                down_payment = round(tot_deliv * (down_pct / 100.0), 2)
                balance = round(tot_deliv - down_payment, 2)

                acopio_sum = {
                    "enabled": True,
                    "min_down_payment_pct": down_pct,
                    "down_payment_ars": down_payment,
                    "remaining_balance_ars": balance,
                    "freeze_days": freeze_days,
                    "freeze_until_date": (now + timedelta(days=freeze_days)).isoformat(),
                    "max_withdrawal_days": max_days,
                    "max_withdrawal_date": (now + timedelta(days=max_days)).isoformat(),
                    "min_notice_hours": notice_hrs,
                }

            vendor_summaries_list.append({
                "vendor_id": v.id,
                "vendor_name": v.name,
                "locality": localities.get(vid_str, ""),
                "coverage_pct": cov_pct,
                "matched_items_count": matched,
                "missing_items_count": total_rows - matched,
                "materials_subtotal_ars": round(mat_sub, 2),
                "delivery_fee_ars": round(d_fee, 2),
                "total_with_delivery_ars": round(tot_deliv, 2),
                "acopio_summary": acopio_sum,
            })

        sorted_v = sorted(vendor_summaries_list, key=lambda x: (-x["coverage_pct"], x["total_with_delivery_ars"]))
        best_single = sorted_v[0] if sorted_v else None
        best_single_id = best_single["vendor_id"] if best_single else None
        best_single_name = best_single["vendor_name"] if best_single else None
        best_single_total = best_single["total_with_delivery_ars"] if best_single else None

        # 3. Recalcular Split Cart óptimo por subconjuntos
        vendor_id_strs = [str(v.id) for v in vendors]
        best_plan: Optional[Dict[str, Any]] = None

        for r_size in range(1, len(vendor_id_strs) + 1):
            for subset in itertools.combinations(vendor_id_strs, r_size):
                subset_set = set(subset)
                covered_count = 0
                materials_sub = 0.0
                used_v: Set[str] = set()
                assigned_v: Dict[str, str] = {}

                for row in matrix_dict.get("matrix_rows", []):
                    item_id_str = str(row.get("requisition_item_id"))
                    cell_prices = {
                        str(c["vendor_id"]): c["line_subtotal_ars"]
                        for c in row.get("vendor_cells", [])
                        if c.get("match_status") == "EXACT_MATCH" and c.get("line_subtotal_ars") is not None
                    }
                    avail = [vid for vid in subset_set if vid in cell_prices]
                    if avail:
                        covered_count += 1
                        cheapest_vid = min(avail, key=lambda vid: cell_prices[vid])
                        materials_sub += cell_prices[cheapest_vid]
                        used_v.add(cheapest_vid)
                        assigned_v[item_id_str] = cheapest_vid

                deliv_total = sum(vendor_fees[vid] for vid in used_v)
                tot_c = materials_sub + deliv_total

                is_better = False
                if best_plan is None:
                    is_better = True
                elif covered_count > best_plan["covered_count"]:
                    is_better = True
                elif covered_count == best_plan["covered_count"]:
                    if tot_c < best_plan["total_cost"] - 1e-4:
                        is_better = True
                    elif abs(tot_c - best_plan["total_cost"]) <= 1e-4 and len(used_v) < len(best_plan["used_vendors"]):
                        is_better = True

                if is_better:
                    best_plan = {
                        "covered_count": covered_count,
                        "materials_subtotal": materials_sub,
                        "delivery_total": deliv_total,
                        "total_cost": tot_c,
                        "used_vendors": used_v,
                        "assigned_vendors": assigned_v,
                    }

        if best_plan:
            assigned_map = best_plan["assigned_vendors"]
            for row in matrix_dict.get("matrix_rows", []):
                item_id_str = str(row.get("requisition_item_id"))
                split_winner = assigned_map.get(item_id_str)
                for cell in row.get("vendor_cells", []):
                    cell["is_selected_split"] = (str(cell.get("vendor_id")) == split_winner)

            best_single_full = best_single is not None and best_single["coverage_pct"] >= 100.0
            split_full = best_plan["covered_count"] == total_rows
            savings = round(best_single_total - best_plan["total_cost"], 2) if best_single_full and split_full and best_single_total is not None else 0.0

            split_summary_dict = {
                "total_materials_ars": round(best_plan["materials_subtotal"], 2),
                "total_delivery_fees_ars": round(best_plan["delivery_total"], 2),
                "total_cart_ars": round(best_plan["total_cost"], 2),
                "participating_vendors_count": len(best_plan["used_vendors"]),
                "participating_vendor_names": [vendor_names[vid] for vid in best_plan["used_vendors"] if vid in vendor_names],
                "savings_vs_single_vendor_ars": savings,
                "is_split_recommended": savings > 0.0 and len(best_plan["used_vendors"]) > 1 and best_single_full and split_full,
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

        matrix_dict["vendors"] = vendor_summaries_list
        matrix_dict["best_single_vendor_id"] = best_single_id
        matrix_dict["best_single_vendor_name"] = best_single_name
        matrix_dict["best_single_total_ars"] = best_single_total
        matrix_dict["split_cart"] = split_summary_dict

        return matrix_dict

