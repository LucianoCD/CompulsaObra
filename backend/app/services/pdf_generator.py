"""Generador de documentos PDF nativos con fpdf2 (sin dependencias C/GTK externas)."""

from datetime import datetime
from typing import Any, Dict, Optional
from fpdf import FPDF

from app.services.comparison_optimizer import ComparisonOptimizerService


def clean_pdf_text(text: str) -> str:
    """Sanitiza caracteres unicode para compatibilidad total con fuentes estándar FPDF."""
    if not text:
        return ""
    replacements = {
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "Ø": "Diam.",
        "ø": "diam.",
        "¡": "",
        "¿": "",
        "×": "x",
        "•": "*",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def format_ars(val: Optional[float]) -> str:
    """Formatea valores numéricos al estándar argentino: $ 10.500,50."""
    if val is None:
        return "-"
    formatted = f"{val:,.2f}"
    return "$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


class CompulsaPDF(FPDF):
    """Clase personalizada FPDF con encabezados y pies de página estilizados."""

    def __init__(self, title_text: str = "CompulsaObra"):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.title_text = clean_pdf_text(title_text)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(30, 41, 59)
        self.cell(0, 10, self.title_text, border=False, new_x="LMARGIN", new_y="NEXT", align="L")
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 116, 139)
        self.cell(
            0,
            5,
            "Sistema Inteligente de Elaboracion de Presupuestos y Comparacion Multi-Negocio | NOA",
            border=False,
            new_x="LMARGIN",
            new_y="NEXT",
            align="L",
        )
        self.ln(3)
        self.set_draw_color(226, 232, 240)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(148, 163, 184)
        page_str = f"Pagina {self.page_no()}/{{nb}}"
        self.cell(0, 10, f"CompulsaObra - Documento emitido con snapshot inmutable - {page_str}", align="C")


class PDFGeneratorService:
    """Genera pliegos comparativos y presupuestos finales vectoriales en formato PDF."""

    @classmethod
    def generate_pdf(
        cls,
        matrix_data: Dict[str, Any],
        mode: str = "comparison",  # 'comparison' | 'client_budget'
        title: str = "Presupuesto de Materiales",
        client_name: Optional[str] = None,
        strategy: Optional[str] = None,
        single_vendor_id: Optional[str] = None,
    ) -> bytes:
        header_title = (
            "CompulsaObra - Comparativa Multi-Negocio"
            if mode == "comparison"
            else "CompulsaObra - Presupuesto al Cliente"
        )
        pdf = CompulsaPDF(title_text=header_title)
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 7, clean_pdf_text(f"Titulo: {title}"), new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(51, 65, 85)
        if client_name:
            pdf.cell(0, 6, clean_pdf_text(f"Cliente / Comitente: {client_name}"), new_x="LMARGIN", new_y="NEXT")

        created_at_str = str(matrix_data.get("created_at", datetime.now().isoformat()))[:10]
        payment_mod = matrix_data.get("payment_modality", "CASH")
        pdf.cell(
            0,
            6,
            clean_pdf_text(f"Fecha de Emision: {created_at_str} | Modalidad: {payment_mod}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        if mode == "comparison":
            token = matrix_data.get("public_share_token", "N/A")
            pdf.cell(0, 6, clean_pdf_text(f"Token de Verificacion: {token}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        if mode == "comparison":
            cls._render_comparison_mode(pdf, matrix_data)
        else:
            cls._render_client_budget_mode(
                pdf,
                matrix_data,
                strategy=strategy,
                single_vendor_id=single_vendor_id,
            )

        return bytes(pdf.output())

    @classmethod
    def _render_comparison_mode(cls, pdf: CompulsaPDF, data: Dict[str, Any]):
        # 1. Resumen por comercio
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_fill_color(241, 245, 249)
        pdf.cell(0, 7, "1. Resumen de Comercios Comparados", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(60, 6, "Comercio", border=1)
        pdf.cell(30, 6, "Cobertura", border=1, align="C")
        pdf.cell(35, 6, "Materiales", border=1, align="R")
        pdf.cell(30, 6, "Flete", border=1, align="R")
        pdf.cell(35, 6, "Total c/Flete", border=1, align="R")
        pdf.ln()

        pdf.set_font("Helvetica", "", 9)
        for v in data.get("vendors", []):
            v_name = clean_pdf_text(v.get("vendor_name", "")[:28])
            cov = f"{v.get('coverage_pct', 0)}%"
            mat = format_ars(v.get("materials_subtotal_ars", 0))
            fee = format_ars(v.get("delivery_fee_ars", 0))
            tot = format_ars(v.get("total_with_delivery_ars", 0))

            pdf.cell(60, 6, v_name, border=1)
            pdf.cell(30, 6, cov, border=1, align="C")
            pdf.cell(35, 6, mat, border=1, align="R")
            pdf.cell(30, 6, fee, border=1, align="R")
            pdf.cell(35, 6, tot, border=1, align="R")
            pdf.ln()

        pdf.ln(4)

        # 2. Tarjeta Split Cart vs Mejor Único
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "2. Analisis de Optimizacion de Compra (Split Cart)", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        best_v = clean_pdf_text(data.get("best_single_vendor_name") or "N/A")
        best_t_str = format_ars(data.get("best_single_total_ars", 0))
        split_c = data.get("split_cart", {})
        split_t_str = format_ars(split_c.get("total_cart_ars", 0))
        savings = float(split_c.get("savings_vs_single_vendor_ars", 0))

        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, clean_pdf_text(f"* Mejor Proveedor Unico: {best_v} - Total: {best_t_str}"), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 5, clean_pdf_text(f"* Compra Dividida Optima: Total con fletes sumados: {split_t_str}"), new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "B", 10)
        if savings > 0:
            pdf.set_text_color(16, 185, 129)
            pdf.cell(0, 6, clean_pdf_text(f"Ahorro Neto Real de Bolsillo comprando dividido: {format_ars(savings)}!"), new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_text_color(71, 85, 105)
            pdf.cell(0, 6, "Se recomienda compra en un solo comercio (ahorro en fletes unificados).", new_x="LMARGIN", new_y="NEXT")

        pdf.set_text_color(15, 23, 42)
        pdf.ln(4)

        # 3. Detalle ítem por ítem (separando Mejor Precio Unitario vs Subtotal Línea H-01)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "3. Comparativa Renglon por Renglon", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(8, 6, "#", border=1, align="C")
        pdf.cell(62, 6, "Material Solicitado", border=1)
        pdf.cell(20, 6, "Cantidad", border=1, align="C")
        pdf.cell(32, 6, "Mejor Unit.", border=1, align="R")
        pdf.cell(34, 6, "Mejor Subtotal", border=1, align="R")
        pdf.cell(34, 6, "Ganador", border=1)
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        for row in data.get("matrix_rows", []):
            order = str(row.get("line_order", 1))
            term = clean_pdf_text(row.get("requested_term", "")[:34])
            qty = float(row.get("quantity", 1.0))
            qty_str = f"{qty:g} {row.get('requested_unit', 'UN')}"

            low_sub = row.get("lowest_line_subtotal_ars")
            if low_sub is None:
                low_sub = row.get("lowest_price_ars")
            low_unit = row.get("lowest_unit_price_ars")
            if low_unit is None and low_sub is not None and qty > 0:
                low_unit = round(float(low_sub) / qty, 2)

            unit_str = format_ars(low_unit) if low_unit is not None else "-"
            sub_str = format_ars(low_sub) if low_sub is not None else "Sin Cotiz."

            winning_id = row.get("winning_vendor_id")
            w_name = "N/A"
            for c in row.get("vendor_cells", []):
                if c.get("vendor_id") == winning_id:
                    w_name = clean_pdf_text(c.get("vendor_name", "")[:17])
                    break

            pdf.cell(8, 5, order, border=1, align="C")
            pdf.cell(62, 5, term, border=1)
            pdf.cell(20, 5, qty_str, border=1, align="C")
            pdf.cell(32, 5, unit_str, border=1, align="R")
            pdf.cell(34, 5, sub_str, border=1, align="R")
            pdf.cell(34, 5, w_name, border=1)
            pdf.ln()

    @classmethod
    def _render_client_budget_mode(
        cls,
        pdf: CompulsaPDF,
        data: Dict[str, Any],
        strategy: Optional[str] = None,
        single_vendor_id: Optional[str] = None,
    ):
        resolved = ComparisonOptimizerService.resolve_budget_lines_for_strategy(
            matrix_data=data,
            strategy=strategy,
            single_vendor_id=single_vendor_id,
        )
        strategy_label = (
            "Compra Unificada (Proveedor Unico)"
            if resolved["strategy"] == "SINGLE_VENDOR"
            else "Compra Dividida Optima (Multi-Proveedor)"
        )

        pdf.set_font("Helvetica", "B", 11)
        pdf.set_fill_color(241, 245, 249)
        pdf.cell(
            0,
            7,
            clean_pdf_text(f"Presupuesto Consolidado de Materiales - {strategy_label}"),
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(10, 6, "#", border=1, align="C")
        pdf.cell(85, 6, "Descripcion del Material", border=1)
        pdf.cell(30, 6, "Cant. Comercial", border=1, align="C")
        pdf.cell(32, 6, "Precio Unit. Final", border=1, align="R")
        pdf.cell(33, 6, "Subtotal", border=1, align="R")
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        for line in resolved["lines"]:
            order = str(line["line_order"])
            term = clean_pdf_text(line["canonical_name"][:46])
            if line["covered"] and line["commercial_qty"] is not None:
                qty_str = f"{line['commercial_qty']:g} {line['sale_unit'] or line['requested_unit']}"
                unit_str = format_ars(line["client_unit_price_ars"])
                sub_str = format_ars(line["client_subtotal_ars"])
            else:
                qty_str = f"{line['requested_qty']:g} {line['requested_unit']}"
                unit_str = "A convenir"
                sub_str = "A convenir"

            pdf.cell(10, 5, order, border=1, align="C")
            pdf.cell(85, 5, term, border=1)
            pdf.cell(30, 5, clean_pdf_text(qty_str[:16]), border=1, align="C")
            pdf.cell(32, 5, unit_str, border=1, align="R")
            pdf.cell(33, 5, sub_str, border=1, align="R")
            pdf.ln()

        pdf.ln(4)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(130, 6, "Subtotal Materiales:", border=0, align="R")
        pdf.cell(60, 6, format_ars(resolved["materials_subtotal_ars"]), border=1, align="R")
        pdf.ln()

        if resolved["include_delivery_fees"] and resolved["logistics_ars"] > 0:
            pdf.cell(130, 6, "Costo Logistico / Fletes:", border=0, align="R")
            pdf.cell(60, 6, format_ars(resolved["logistics_ars"]), border=1, align="R")
            pdf.ln()

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(130, 7, "TOTAL PRESUPUESTO:", border=0, align="R")
        pdf.cell(60, 7, format_ars(resolved["grand_total_ars"]), border=1, align="R")
        pdf.ln(8)

        if resolved["has_unquoted_items"]:
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(185, 28, 28)
            pdf.cell(
                0,
                5,
                clean_pdf_text(
                    "ATENCION: Este presupuesto es PARCIAL y contiene items 'A convenir' no incluidos en el total final."
                ),
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.ln(2)

        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(100, 116, 139)
        pdf.multi_cell(
            0,
            4,
            clean_pdf_text(
                "Nota: Los precios expresados en el presente presupuesto quedan sujetos a las condiciones de acopio y vigencia comercial pactadas al momento de su aceptacion."
            ),
        )
