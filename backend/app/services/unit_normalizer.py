"""Normalizador físico determinista de unidades, pulgadas a mm y jerga del NOA."""

import re
import unicodedata
from typing import List, Optional, Tuple, Dict
from app.schemas.dimensions import NormalizedItemDraft

INCH_TO_MM_MAP: Dict[str, float] = {
    "1/2": 12.70,
    "3/4": 19.05,
    "1": 25.40,
    "1 1/4": 31.75,
    "1 1/2": 38.10,
    "2": 50.80,
    "2 1/2": 63.50,
    "3": 75.00,
    "4": 110.00,  # Equivalencia sanitaria PVC cloacal estándar
}

MATERIAL_FAMILIES = ["caño", "cano", "tubo", "codo", "tee", "cupla", "union"]

KNOWN_MATERIALS = {
    "pvc": "PVC",
    "termofusion": "Termofusión",
    "termo fusión": "Termofusión",
    "polipropileno": "Polipropileno",
    "corrugado": "Corrugado",
    "hierro": "Acero",  # Unificado con Acero para coherencia entre catálogo y pedido
    "acero": "Acero",
    "chapa": "Chapa",
    "cemento": "Cemento",
    "cal": "Cal",
    "yeso": "Yeso",
}


def strip_accents(text: str) -> str:
    """Elimina tildes y diacríticos preservando caracteres base."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def normalize_material_label(mat: Optional[str]) -> Optional[str]:
    """Unifica variaciones de nombres de materiales a su forma canónica estándar."""
    if not mat:
        return None
    s = strip_accents(mat).strip().lower()
    if "pvc" in s:
        return "PVC"
    if "termofus" in s or "termo fus" in s:
        return "Termofusión"
    if "poliprop" in s:
        return "Polipropileno"
    if "corrugad" in s:
        return "Corrugado"
    if "hierro" in s or "acero" in s:
        return "Acero"
    if "chapa" in s:
        return "Chapa"
    if "cemento" in s:
        return "Cemento"
    if "cal" in s:
        return "Cal"
    if "yeso" in s:
        return "Yeso"
    return mat.strip()



class UnitNormalizerService:
    """Servicio de normalización física y lingüística de materiales de construcción."""

    @classmethod
    def split_conjunctions(cls, raw_text: str) -> List[str]:
        """Divide líneas compuestas por ' y ', ' + ', saltos de línea o ';'.
        
        Ejemplo: '20 barra del 8 y 4 caño de 3/4' -> ['20 barra del 8', '4 caño de 3/4']
        """
        lines = []
        for segment in raw_text.splitlines():
            segment = segment.strip()
            if not segment:
                continue
            
            # Separar por ';'
            parts = [p.strip() for p in re.split(r";", segment) if p.strip()]
            
            for part in parts:
                # Separar por ' + '
                subparts = [sp.strip() for sp in re.split(r"\s+\+\s+", part) if sp.strip()]
                for sp in subparts:
                    # Separar por ' y ' cuando va seguido de un número o cantidad
                    # ej: '20 barra del 8 y 4 caño de 3/4'
                    y_split = re.split(r"\s+y\s+(?=\d)", sp, flags=re.IGNORECASE)
                    for item in y_split:
                        item_clean = item.strip()
                        if item_clean:
                            lines.append(item_clean)
        return lines

    @classmethod
    def extract_quantity_and_unit(cls, text: str) -> Tuple[float, str, str]:
        """Extrae la cantidad inicial, unidad y el texto remanente."""
        clean_text = text.strip()

        # 1. Detectar formato con punto de miles argentino (ej. '1.500 ladrillos' o '1.500,50 kg')
        m_thousand = re.match(
            r"^(\d{1,3}(?:\.\d{3})+)(?:,(\d+))?\s*(barras?|bolsas?|caños?|canos?|unidades?|unids?|un|mts?|metros?|kg|kilos?|litros?|lts?|rollos?|ladrillos?)?\s*(.*)$",
            clean_text,
            re.IGNORECASE,
        )
        if m_thousand:
            int_part = m_thousand.group(1).replace(".", "")
            dec_part = m_thousand.group(2)
            qty = float(f"{int_part}.{dec_part}" if dec_part else int_part)
            unit_raw = m_thousand.group(3) or "UN"
            rest = m_thousand.group(4) or ""
            unit_normalized = cls._normalize_unit_name(unit_raw)
            return qty, unit_normalized, rest.strip()

        # 2. Formato estándar '20 barras', '4 caños', '1.5 kg', '50 bolsas'
        match = re.match(
            r"^(\d+(?:[.,]\d+)?)\s*(barras?|bolsas?|caños?|canos?|unidades?|unids?|un|mts?|metros?|kg|kilos?|litros?|lts?|rollos?|ladrillos?)?\s*(.*)$",
            clean_text,
            re.IGNORECASE,
        )
        if match:
            qty_str = match.group(1).replace(",", ".")
            qty = float(qty_str)
            unit_raw = match.group(2) or "UN"
            rest = match.group(3) or ""
            unit_normalized = cls._normalize_unit_name(unit_raw)
            return qty, unit_normalized, rest.strip()

        return 1.0, "UN", clean_text

    @classmethod
    def _normalize_unit_name(cls, unit_str: str) -> str:
        u = strip_accents(unit_str)
        if "barra" in u:
            return "BARRA"
        if "bolsa" in u:
            return "BOLSA"
        if "caño" in u or "cano" in u:
            return "UN"
        if "m" in u:
            return "M"
        if "kg" in u or "kilo" in u:
            return "KG"
        if "litro" in u or "lt" in u:
            return "LT"
        if "rollo" in u:
            return "ROLLO"
        return "UN"

    @classmethod
    def detect_fractional_inch(cls, text: str) -> Optional[Tuple[str, float]]:
        """Detecta fracciones de pulgada y devuelve (inch_str, mm_val)."""
        # Buscar ej: '1 1/2"', '3/4"', '3/4', '1/2'
        # Primero buscar fracciones compuestas '1 1/2' o '2 1/2'
        compound_match = re.search(r"\b([1-3]\s+[1-3]/[2-8])\s*(?:\"|pulg|pulgadas?)?", text, re.IGNORECASE)
        if compound_match:
            fraction = compound_match.group(1).strip()
            if fraction in INCH_TO_MM_MAP:
                return fraction, INCH_TO_MM_MAP[fraction]
        
        # Fracciones simples '1/2', '3/4', '1/4'
        simple_match = re.search(r"\b([1-3]/[2-8])\s*(?:\"|pulg|pulgadas?)?", text, re.IGNORECASE)
        if simple_match:
            fraction = simple_match.group(1).strip()
            if fraction in INCH_TO_MM_MAP:
                return fraction, INCH_TO_MM_MAP[fraction]

        # Pulgadas enteras ej: '4"', '4 pulg', '1"', '2"'
        inch_int_match = re.search(r"\b([1-4])\s*(?:\"|pulg|pulgadas?)(?:\s|$)", text, re.IGNORECASE)
        if inch_int_match:
            val_str = inch_int_match.group(1).strip()
            if val_str in INCH_TO_MM_MAP:
                return val_str, INCH_TO_MM_MAP[val_str]

        return None

    @classmethod
    def parse_single_line(cls, line: str, line_order: int = 1) -> NormalizedItemDraft:
        """Parsea y normaliza una línea individual hacia un NormalizedItemDraft."""
        raw_line = line.strip()
        qty, unit, remaining = cls.extract_quantity_and_unit(raw_line)
        norm_text = strip_accents(raw_line)

        diameter_inch: Optional[str] = None
        diameter_mm: Optional[float] = None
        length_m: Optional[float] = None
        weight_kg: Optional[float] = None
        material_type: Optional[str] = None
        canonical_term = remaining if remaining else raw_line

        # 1. Jerga regional de Acero / Hierros del NOA:
        # 'hierro del 8', 'barra del 8', 'hierro de 10', 'acero del 12', 'hierro 6'
        # Protección: excluir chapas, alambres o perfiles, y no capturar si va seguido de fracción '/2'
        VALID_REBAR_DIAMETERS = {4, 6, 8, 10, 12, 14, 16, 20, 25, 32}
        if "chapa" not in norm_text and "perfil" not in norm_text and "alambre" not in norm_text:
            re_hierro = re.search(r"\b(?:hierro|barra|acero)\s+(?:del?|de)?\s*(\d+)(?!\s*/\s*\d)\b", norm_text)
            if re_hierro:
                diam_val = float(re_hierro.group(1))
                if int(diam_val) in VALID_REBAR_DIAMETERS:
                    diameter_mm = diam_val
                    length_m = 12.0  # Longitud estándar de barras de acero aletado
                    material_type = "Acero"
                    canonical_term = f"Barra acero aletado Ø {int(diam_val)} mm x 12 m"
                    return NormalizedItemDraft(
                        line_order=line_order,
                        raw_line=raw_line,
                        requested_term=canonical_term,
                        quantity=qty,
                        requested_unit="BARRA" if unit == "BARRA" else "UN",
                        diameter_mm=diameter_mm,
                        length_m=length_m,
                        weight_kg=weight_kg,
                        material_type=material_type,
                        completeness="complete",
                        is_confirmed=True,
                    )

        # 2. Cemento / Bolsas:
        if "cemento" in norm_text:
            material_type = "Cemento"
            # Buscar peso explícito ej: '25 kg', '50 kg'
            re_peso = re.search(r"\b(\d+)\s*kg\b", norm_text)
            if re_peso:
                weight_kg = float(re_peso.group(1))
            else:
                weight_kg = 50.0  # Estándar NOA 50kg por bolsa
            
            brand_hint = ""
            if "loma negra" in norm_text:
                brand_hint = "Loma Negra"
            elif "avellaneda" in norm_text:
                brand_hint = "Avellaneda"
            elif "holcim" in norm_text or "minetti" in norm_text:
                brand_hint = "Holcim"

            canonical_term = f"Cemento Portland {brand_hint} {int(weight_kg)} kg".strip()
            return NormalizedItemDraft(
                line_order=line_order,
                raw_line=raw_line,
                requested_term=canonical_term,
                quantity=qty,
                requested_unit="BOLSA",
                weight_kg=weight_kg,
                material_type=material_type,
                completeness="complete",
                is_confirmed=True,
            )

        # 3. Detección de Material constructivo explícito:
        for key, mat_name in KNOWN_MATERIALS.items():
            if re.search(rf"\b{key}\b", norm_text):
                material_type = mat_name
                break

        # 4. Detección de Diámetro en Milímetros explícito (ej: '40 mm', '110 mm', 'ø 10 mm'):
        re_mm = re.search(r"(?:ø|diametro|d)?\s*(\d+(?:[.,]\d+)?)\s*mm\b", norm_text)
        if re_mm:
            diameter_mm = float(re_mm.group(1).replace(",", "."))
        else:
            # Buscar si se especificó en pulgadas fraccionarias
            inch_res = cls.detect_fractional_inch(raw_line)
            if inch_res:
                diameter_inch, diameter_mm = inch_res

        # 5. Detección de Longitud comercial en metros:
        re_len = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:m|mts|metros)\b", norm_text)
        if re_len:
            length_m = float(re_len.group(1).replace(",", "."))
        elif ("caño" in norm_text or "cano" in norm_text) and material_type == "PVC":
            length_m = 4.0  # Caños sanitarios estándar de 4 metros

        # 6. Detección de familias críticas que exigen material y diámetro (caño, tubo, codo, tee, cupla, union):
        is_critical_family = any(fam in norm_text for fam in MATERIAL_FAMILIES)
        
        if is_critical_family:
            missing_material = not material_type
            missing_dimension = diameter_mm is None

            if missing_material or missing_dimension:
                dim_desc = f"Ø {diameter_inch}\" ({diameter_mm} mm)" if diameter_inch and diameter_mm else (f"Ø {diameter_mm} mm" if diameter_mm else "")
                
                if missing_material and missing_dimension:
                    clarification_prompt = (
                        "Especificar diámetro y material del caño/accesorio: "
                        "¿PVC (40 mm, 110 mm), Termofusión (1/2, 3/4) o Corrugado?"
                    )
                elif missing_material:
                    clarification_prompt = (
                        f"Especificar material/uso del caño/accesorio {dim_desc}: "
                        f"¿PVC cloacal/agua, Polipropileno roscado, Termofusión (agua/gas) o Corrugado eléctrico?"
                    ).strip()
                else:
                    clarification_prompt = (
                        f"Especificar diámetro del {material_type}: "
                        f"¿40 mm, 50 mm, 63 mm, 110 mm o fracción de pulgada (1/2, 3/4, 1)?"
                    )

                req_term = f"Caño {material_type or ''} {dim_desc}".strip()
                return NormalizedItemDraft(
                    line_order=line_order,
                    raw_line=raw_line,
                    requested_term=req_term or "Caño",
                    quantity=qty,
                    requested_unit=unit,
                    diameter_inch=diameter_inch,
                    diameter_mm=diameter_mm,
                    length_m=length_m,
                    weight_kg=weight_kg,
                    material_type=material_type,
                    completeness="missing_critical_attribute",
                    clarification_prompt=clarification_prompt,
                    is_confirmed=False,
                )

        return NormalizedItemDraft(
            line_order=line_order,
            raw_line=raw_line,
            requested_term=raw_line if not remaining else remaining,
            quantity=qty,
            requested_unit=unit,
            diameter_inch=diameter_inch,
            diameter_mm=diameter_mm,
            length_m=length_m,
            weight_kg=weight_kg,
            material_type=material_type,
            completeness="complete",
            is_confirmed=True,
        )

    @classmethod
    def parse_and_normalize_line(cls, raw_input: str) -> List[NormalizedItemDraft]:
        """Procesa una entrada completa (multilínea o compuesta por conjunciones)
        y retorna una lista ordenada de NormalizedItemDraft."""
        segments = cls.split_conjunctions(raw_input)
        results: List[NormalizedItemDraft] = []
        for idx, segment in enumerate(segments, start=1):
            item = cls.parse_single_line(segment, line_order=idx)
            results.append(item)
        return results
