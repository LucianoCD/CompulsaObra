"""Normalizador físico determinista de unidades, pulgadas a mm por familia y jerga del NOA."""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple
from app.schemas.dimensions import NormalizedItemDraft

# Mapa físico exacto (1 pulgada = 25.40 mm)
PHYSICAL_INCH_TO_MM_MAP: Dict[str, float] = {
    "1/2": 12.70,
    "3/4": 19.05,
    "1": 25.40,
    "1 1/4": 31.75,
    "1 1/2": 38.10,
    "2": 50.80,
    "2 1/2": 63.50,
    "3": 76.20,
    "4": 101.60,
}

# Compatibilidad de mapa global comercial heredado para pruebas/consultas genéricas
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

# Equivalencias comerciales por familia constructiva (H-06):
# El primer valor representa el diámetro primario asignado en parsing; la lista completa son equivalentes aceptados en matching.
FAMILY_NOMINAL_INCH_TO_MM_MAP: Dict[str, Dict[str, List[float]]] = {
    "PVC": {
        "1/2": [12.70, 20.00],
        "3/4": [19.05, 25.00],
        "1": [25.40, 32.00],
        "1 1/4": [31.75, 40.00],
        "1 1/2": [38.10, 40.00, 50.00],
        "2": [50.80, 50.00, 63.00],
        "2 1/2": [63.50, 63.00, 75.00],
        "3": [75.00, 76.20],
        "4": [110.00],
    },
    "Termofusión": {
        "1/2": [12.70, 20.00],
        "3/4": [19.05, 20.00, 25.00],
        "1": [25.40, 32.00],
        "1 1/4": [31.75, 40.00],
        "1 1/2": [38.10, 50.00],
        "2": [50.80, 63.00],
        "2 1/2": [63.50, 75.00],
        "3": [75.00, 76.20, 90.00],
        "4": [110.00],
    },
    "Polipropileno": {
        "1/2": [12.70, 20.00],
        "3/4": [19.05, 20.00, 25.00],
        "1": [25.40, 32.00],
        "1 1/4": [31.75, 40.00],
        "1 1/2": [38.10, 50.00],
        "2": [50.80, 63.00],
        "2 1/2": [63.50, 75.00],
        "3": [75.00, 76.20, 90.00],
        "4": [110.00],
    },
    "Corrugado": {
        "1/2": [12.70, 16.00],
        "3/4": [19.05, 20.00],
        "1": [25.40, 25.00],
        "1 1/4": [31.75, 32.00],
        "1 1/2": [38.10, 40.00],
        "2": [50.80, 50.00],
    },
    "Acero": {
        k: [v] for k, v in PHYSICAL_INCH_TO_MM_MAP.items()
    },
}

MATERIAL_FAMILIES = ["caño", "cano", "tubo", "codo", "tee", "cupla", "union"]

_PIPE_FAMILY_REGEX = re.compile(r"\b(canos?|tubos?|codos?|tees?|cuplas?|union(?:es)?)\b")

_PRODUCT_NOUN_UNITS = {"cano", "canos", "ladrillo", "ladrillos"}

KNOWN_MATERIALS = {
    "pvc": "PVC",
    "termofusion": "Termofusión",
    "termo fusión": "Termofusión",
    "polipropileno": "Polipropileno",
    "corrugado": "Corrugado",
    "hierro": "Acero",
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
    def resolve_inch_to_mm_by_family(
        cls,
        inch_str: str,
        material_type: Optional[str] = None,
    ) -> Optional[float]:
        """Convierte pulgadas fraccionarias a milímetros diferenciando familia nominal vs física (H-06)."""
        norm_mat = normalize_material_label(material_type)
        if norm_mat and norm_mat in FAMILY_NOMINAL_INCH_TO_MM_MAP:
            family_map = FAMILY_NOMINAL_INCH_TO_MM_MAP[norm_mat]
            if inch_str in family_map:
                return family_map[inch_str][0]
        if inch_str in PHYSICAL_INCH_TO_MM_MAP:
            return PHYSICAL_INCH_TO_MM_MAP[inch_str]
        return INCH_TO_MM_MAP.get(inch_str)

    @classmethod
    def get_equivalent_diameters_mm(
        cls,
        diameter_mm: float,
        material_type: Optional[str] = None,
        diameter_inch: Optional[str] = None,
    ) -> List[float]:
        """Retorna diámetros comerciales equivalentes dentro de la misma familia sin mezcla física/nominal (H-06)."""
        norm_mat = normalize_material_label(material_type)
        candidates: List[float] = [float(diameter_mm)]

        if not norm_mat or norm_mat not in FAMILY_NOMINAL_INCH_TO_MM_MAP:
            return candidates

        family_map = FAMILY_NOMINAL_INCH_TO_MM_MAP[norm_mat]
        if diameter_inch and diameter_inch in family_map:
            for val in family_map[diameter_inch]:
                if val not in candidates:
                    candidates.append(val)
            return candidates

        # Buscar equivalencia inversa desde pulgada física o primer nominal de la familia
        for inch_key, equiv_list in family_map.items():
            phys_mm = PHYSICAL_INCH_TO_MM_MAP.get(inch_key)
            # Solo expandir desde medida en pulgada física (ej. 19.05 -> [19.05, 20.0, 25.0]) o nominal primario
            # sin colapsar milímetros métricos distintos (ej. 40 mm PVC no se confunde con 110 mm)
            if phys_mm is not None and abs(diameter_mm - phys_mm) <= 0.15:
                for val in equiv_list:
                    if val not in candidates:
                        candidates.append(val)
            elif equiv_list and abs(diameter_mm - equiv_list[0]) <= 0.15 and phys_mm is not None and abs(equiv_list[0] - phys_mm) <= 0.15:
                for val in equiv_list:
                    if val not in candidates:
                        candidates.append(val)

        return candidates

    @classmethod
    def split_conjunctions(cls, raw_text: str) -> List[str]:
        """Divide líneas compuestas por ' y ', ' + ', saltos de línea o ';'."""
        lines = []
        for segment in raw_text.splitlines():
            segment = segment.strip()
            if not segment:
                continue

            parts = [p.strip() for p in re.split(r";", segment) if p.strip()]
            for part in parts:
                subparts = [sp.strip() for sp in re.split(r"\s+\+\s+", part) if sp.strip()]
                for sp in subparts:
                    y_split = re.split(r"\s+y\s+(?=\d)", sp, flags=re.IGNORECASE)
                    for item in y_split:
                        item_clean = item.strip()
                        if item_clean:
                            lines.append(item_clean)
        return lines

    @classmethod
    def extract_quantity_and_unit(cls, text: str) -> Tuple[float, str, str]:
        """Extrae la cantidad inicial, unidad y el texto remanente sin consumir dimensiones."""
        clean_text = text.strip()

        m_thousand = re.match(
            r"^(\d{1,3}(?:\.\d{3})+)(?:,(\d+))?(?!\d|[.,]\d)(?!\s*(?:/\s*\d|\d+\s*/\s*\d|\"|''|mm\b|cm\b|pulg))\s*(?:(barras?|bolsas?|caños?|canos?|unidades?|unids?|un|mts?|metros?|m|kg|kilos?|litros?|lts?|rollos?|ladrillos?)\b\s*)?(.*)$",
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
            if strip_accents(unit_raw).strip().lower() in _PRODUCT_NOUN_UNITS:
                rest = f"{unit_raw} {rest}".strip()
            return qty, unit_normalized, rest.strip()

        match = re.match(
            r"^(\d+(?:[.,]\d+)?)(?!\d|[.,]\d)(?!\s*(?:/\s*\d|\d+\s*/\s*\d|\"|''|mm\b|cm\b|pulg))\s*(?:(barras?|bolsas?|caños?|canos?|unidades?|unids?|un|mts?|metros?|m|kg|kilos?|litros?|lts?|rollos?|ladrillos?)\b\s*)?(.*)$",
            clean_text,
            re.IGNORECASE,
        )
        if match:
            qty_str = match.group(1).replace(",", ".")
            qty = float(qty_str)
            unit_raw = match.group(2) or "UN"
            rest = match.group(3) or ""
            unit_normalized = cls._normalize_unit_name(unit_raw)
            if strip_accents(unit_raw).strip().lower() in _PRODUCT_NOUN_UNITS:
                rest = f"{unit_raw} {rest}".strip()
            return qty, unit_normalized, rest.strip()

        return 1.0, "UN", clean_text

    @classmethod
    def _normalize_unit_name(cls, unit_str: str) -> str:
        u = strip_accents(unit_str).strip().lower()
        if "barra" in u:
            return "BARRA"
        if "bolsa" in u:
            return "BOLSA"
        if "cano" in u:
            return "CAÑO"
        if u in {"m", "mt", "mts", "metro", "metros"}:
            return "M"
        if "kg" in u or "kilo" in u:
            return "KG"
        if "litro" in u or u in {"lt", "lts"}:
            return "LT"
        if "rollo" in u:
            return "ROLLO"
        return "UN"

    @classmethod
    def detect_fractional_inch(
        cls,
        text: str,
        material_type: Optional[str] = None,
    ) -> Optional[Tuple[str, float]]:
        """Detecta fracciones de pulgada y devuelve (inch_str, mm_val) según la familia del material."""
        compound_match = re.search(r"\b([1-3]\s+[1-3]/[2-8])\s*(?:\"|pulg|pulgadas?)?", text, re.IGNORECASE)
        if compound_match:
            fraction = compound_match.group(1).strip()
            mm_val = cls.resolve_inch_to_mm_by_family(fraction, material_type)
            if mm_val is not None:
                return fraction, mm_val

        simple_match = re.search(r"\b([1-3]/[2-8])\s*(?:\"|pulg|pulgadas?)?", text, re.IGNORECASE)
        if simple_match:
            fraction = simple_match.group(1).strip()
            mm_val = cls.resolve_inch_to_mm_by_family(fraction, material_type)
            if mm_val is not None:
                return fraction, mm_val

        inch_int_match = re.search(r"\b([1-4])\s*(?:\"|pulg|pulgadas?)(?:\s|$)", text, re.IGNORECASE)
        if inch_int_match:
            val_str = inch_int_match.group(1).strip()
            mm_val = cls.resolve_inch_to_mm_by_family(val_str, material_type)
            if mm_val is not None:
                return val_str, mm_val

        return None

    @classmethod
    def parse_single_line(
        cls,
        line: str,
        line_order: int = 1,
        is_catalog_description: bool = False,
    ) -> NormalizedItemDraft:
        """Parsea y normaliza una línea individual hacia un NormalizedItemDraft."""
        raw_line = line.strip()
        if is_catalog_description:
            qty, unit, remaining = 1.0, "UN", raw_line
        else:
            qty, unit, remaining = cls.extract_quantity_and_unit(raw_line)
        norm_text = strip_accents(raw_line)
        norm_remaining = strip_accents(remaining if remaining else raw_line)

        diameter_inch: Optional[str] = None
        diameter_mm: Optional[float] = None
        length_m: Optional[float] = None
        weight_kg: Optional[float] = None
        material_type: Optional[str] = None
        canonical_term = remaining if remaining else raw_line

        re_len = re.compile(r"(?:\bx\b\s*)?(\d+(?:[.,]\d+)?)\s*(?:m|mts|metros)\b")

        # 1. Jerga regional de Acero / Hierros del NOA
        VALID_REBAR_DIAMETERS = {4, 4.2, 6, 8, 10, 12, 14, 16, 20, 25, 32}
        steel_excluded = any(
            w in norm_text
            for w in (
                "chapa",
                "perfil",
                "angulo",
                "alambre",
                "malla",
                "clavo",
                "cano",
                "tubo",
                "codo",
                "tee",
                "cupla",
                "union",
            )
        )
        if not steel_excluded:
            re_hierro = re.search(
                r'\b(?:(?:barras?\s+(?:de\s+)?)?(?:hierros?|acero(?:\s+aletado)?)|barras?)\s*(?:aletad[oa]s?)?\s*(?:del?|de|ø|o|diametro)?\s*(\d+(?:[.,]\d+)?)\s*(?:mm)?(?!\s*(?:/\s*\d|"|pulg|m\b|mts\b|metros?\b|kg\b))\b',
                norm_remaining if not is_catalog_description else norm_text,
            )
            if not re_hierro:
                re_hierro = re.search(
                    r'\b(?:(?:barras?\s+(?:de\s+)?)?(?:hierros?|acero(?:\s+aletado)?)|barras?)\s*(?:aletad[oa]s?)?\s*(?:del?|de|ø|o|diametro)?\s*(\d+(?:[.,]\d+)?)\s*(?:mm)?(?!\s*(?:/\s*\d|"|pulg|m\b|mts\b|metros?\b|kg\b))\b',
                    norm_text,
                )
            if re_hierro:
                diam_val = float(re_hierro.group(1).replace(",", "."))
                if diam_val in VALID_REBAR_DIAMETERS or (diam_val.is_integer() and int(diam_val) in VALID_REBAR_DIAMETERS):
                    diameter_mm = diam_val
                    m_len_steel = re_len.search(norm_remaining)
                    if m_len_steel:
                        parsed_len = float(m_len_steel.group(1).replace(",", "."))
                        length_m = parsed_len if 0 < parsed_len <= 24.0 else (12.0 if unit not in ("M", "KG") else None)
                    else:
                        length_m = 12.0 if unit not in ("M", "KG") else None
                    material_type = "Acero"
                    diam_label = int(diam_val) if diam_val.is_integer() else diam_val
                    len_label = (
                        f" x {int(length_m) if length_m.is_integer() else length_m} m"
                        if length_m is not None
                        else ""
                    )
                    canonical_term = f"Barra acero aletado Ø {diam_label} mm{len_label}"
                    req_steel_unit = unit if unit in ("BARRA", "UN", "M", "KG") else "BARRA"
                    return NormalizedItemDraft(
                        line_order=line_order,
                        raw_line=raw_line,
                        requested_term=canonical_term,
                        quantity=qty,
                        requested_unit=req_steel_unit,
                        diameter_mm=diameter_mm,
                        length_m=length_m,
                        weight_kg=weight_kg,
                        material_type=material_type,
                        completeness="complete",
                        is_confirmed=True,
                    )

            # Si menciona barra/hierro estructural pero no especifica diámetro válido -> Bloqueo HITL (D-H4)
            if not is_catalog_description and re.search(r"\b(barras?|hierros?|acero\s+aletado)\b", norm_text):
                m_len_steel = re_len.search(norm_remaining)
                length_m_missing = (
                    float(m_len_steel.group(1).replace(",", "."))
                    if m_len_steel and 0 < float(m_len_steel.group(1).replace(",", ".")) <= 24.0
                    else (12.0 if unit not in ("M", "KG") else None)
                )
                inch_steel = cls.detect_fractional_inch(remaining if remaining else raw_line, material_type="Acero")
                if inch_steel:
                    d_in, d_mm = inch_steel
                    return NormalizedItemDraft(
                        line_order=line_order,
                        raw_line=raw_line,
                        requested_term=f'Barra acero aletado Ø {d_in}" ({d_mm} mm)',
                        quantity=qty,
                        requested_unit=unit if unit in ("BARRA", "UN", "M", "KG") else "BARRA",
                        diameter_inch=d_in,
                        diameter_mm=d_mm,
                        length_m=length_m_missing,
                        material_type="Acero",
                        completeness="complete",
                        is_confirmed=True,
                    )
                return NormalizedItemDraft(
                    line_order=line_order,
                    raw_line=raw_line,
                    requested_term=remaining if remaining else raw_line,
                    quantity=qty,
                    requested_unit=unit if unit in ("BARRA", "UN", "M", "KG") else "BARRA",
                    diameter_mm=None,
                    length_m=length_m_missing,
                    weight_kg=None,
                    material_type="Acero",
                    completeness="missing_critical_attribute",
                    clarification_prompt=(
                        "Falta especificar el diámetro de la barra de hierro/acero "
                        "(ej: 6 mm, 8 mm, 10 mm, 12 mm). Confirmá la medida antes de cotizar."
                    ),
                    is_confirmed=False,
                )

        # 2. Cemento / Bolsas (excluye cemento de albañilería y pegamentos/adhesivos)
        if re.search(r"\bcemento\b", norm_text) and not any(
            x in norm_text for x in ("albanileria", "contacto", "pegamento", "adhesivo", "cola")
        ):
            material_type = "Cemento"
            re_peso = re.search(r"\b(\d+)\s*kg\b", norm_remaining)
            if re_peso:
                weight_kg = float(re_peso.group(1))
            elif unit != "KG":
                weight_kg = 50.0

            brand_hint = ""
            if "loma negra" in norm_text:
                brand_hint = "Loma Negra"
            elif "avellaneda" in norm_text:
                brand_hint = "Avellaneda"
            elif "holcim" in norm_text or "minetti" in norm_text:
                brand_hint = "Holcim"

            req_unit = "KG" if unit == "KG" else "BOLSA"
            w_desc = f"{int(weight_kg)} kg" if weight_kg else "50 kg"
            canonical_term = f"Cemento Portland {brand_hint} {w_desc}".strip()
            return NormalizedItemDraft(
                line_order=line_order,
                raw_line=raw_line,
                requested_term=canonical_term,
                quantity=qty,
                requested_unit=req_unit,
                weight_kg=weight_kg,
                material_type=material_type,
                completeness="complete",
                is_confirmed=True,
            )

        # 3. Detección de Material constructivo explícito
        for key, mat_name in KNOWN_MATERIALS.items():
            if re.search(rf"\b{key}\b", norm_text):
                material_type = mat_name
                break

        # 4. Detección de Diámetro en Milímetros explícito o en pulgadas diferenciando familia
        re_mm = re.search(r"(?:ø|diametro|d)?\s*(\d+(?:[.,]\d+)?)\s*mm\b", norm_remaining)
        if re_mm:
            diameter_mm = float(re_mm.group(1).replace(",", "."))
        else:
            inch_res = cls.detect_fractional_inch(remaining if remaining else raw_line, material_type=material_type)
            if inch_res:
                diameter_inch, diameter_mm = inch_res

        # 5. Detección de Longitud comercial en metros (buscada solo en el remanente para no confundir con qty en metros)
        m_len = re_len.search(norm_remaining)
        if m_len:
            length_m = float(m_len.group(1).replace(",", "."))
        elif re.search(r"\bcanos?\b", norm_text) and material_type == "PVC" and unit != "M":
            length_m = 4.0

        # 6. Detección de familias críticas que exigen material y diámetro (con límite de palabra)
        family_match = _PIPE_FAMILY_REGEX.search(norm_text)
        if family_match:
            missing_material = not material_type
            missing_dimension = diameter_mm is None

            if missing_material or missing_dimension:
                dim_desc = (
                    f"Ø {diameter_inch}\" ({diameter_mm} mm)"
                    if diameter_inch and diameter_mm
                    else (f"Ø {diameter_mm} mm" if diameter_mm else "")
                )

                raw_piece = family_match.group(1).lower()
                if raw_piece.startswith("tubo"):
                    piece_label = "Tubo"
                elif raw_piece.startswith("codo"):
                    piece_label = "Codo"
                elif raw_piece.startswith("tee"):
                    piece_label = "Tee"
                elif raw_piece.startswith("cupla"):
                    piece_label = "Cupla"
                elif raw_piece.startswith("union"):
                    piece_label = "Unión"
                else:
                    piece_label = "Caño"

                if missing_material and missing_dimension:
                    clarification_prompt = (
                        "Especificar diámetro y material del caño/accesorio: "
                        "¿PVC (40 mm, 110 mm), Termofusión (1/2, 3/4) o Corrugado?"
                    )
                elif missing_material:
                    clarification_prompt = (
                        f"Especificar material/uso del {piece_label.lower()}/accesorio {dim_desc}: "
                        f"¿PVC cloacal/agua, Polipropileno roscado, Termofusión (agua/gas) o Corrugado eléctrico?"
                    ).strip()
                else:
                    clarification_prompt = (
                        f"Especificar diámetro del {piece_label.lower()} {material_type}: "
                        f"¿40 mm, 50 mm, 63 mm, 110 mm o fracción de pulgada (1/2, 3/4, 1)?"
                    )

                req_term = f"{piece_label} {material_type or ''} {dim_desc}".strip()
                return NormalizedItemDraft(
                    line_order=line_order,
                    raw_line=raw_line,
                    requested_term=req_term or piece_label,
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
        """Procesa una entrada completa (multilínea o compuesta por conjunciones)."""
        segments = cls.split_conjunctions(raw_input)
        results: List[NormalizedItemDraft] = []
        for idx, segment in enumerate(segments, start=1):
            item = cls.parse_single_line(segment, line_order=idx)
            results.append(item)
        return results
