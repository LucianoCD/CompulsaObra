"""Pruebas unitarias para el normalizador físico determinista (TASK-02 y E2E-01)."""

from app.services.unit_normalizer import UnitNormalizerService, INCH_TO_MM_MAP


def test_conjunction_splitting_and_e2e_01():
    """E2E-01: '20 barra del 8 y 4 caño de 3/4' produce 2 renglones:
    uno completo y otro con missing_critical_attribute.
    """
    raw_input = "20 barra del 8 y 4 caño de 3/4"
    items = UnitNormalizerService.parse_and_normalize_line(raw_input)

    assert len(items) == 2

    # Renglón 1: Barra de acero
    item1 = items[0]
    assert item1.line_order == 1
    assert item1.quantity == 20.0
    assert item1.diameter_mm == 8.0
    assert item1.length_m == 12.0
    assert item1.material_type == "Acero"
    assert item1.completeness == "complete"
    assert item1.is_confirmed is True

    # Renglón 2: Caño 3/4 sin material especificado
    item2 = items[1]
    assert item2.line_order == 2
    assert item2.quantity == 4.0
    assert item2.diameter_inch == "3/4"
    assert item2.diameter_mm == 19.05
    assert item2.material_type is None
    assert item2.completeness == "missing_critical_attribute"
    assert item2.is_confirmed is False
    assert item2.clarification_prompt is not None
    assert "PVC" in item2.clarification_prompt
    assert "Termofusión" in item2.clarification_prompt


def test_fractional_inch_conversions():
    """Verifica la conversión exacta de pulgadas a milímetros requerida por AGENTS.md."""
    expected_map = {
        "1/2": 12.70,
        "3/4": 19.05,
        "1": 25.40,
        "1 1/4": 31.75,
        "1 1/2": 38.10,
        "2": 50.80,
        "2 1/2": 63.50,
        "3": 75.00,
        "4": 110.00,
    }

    for inch_str, mm_val in expected_map.items():
        assert INCH_TO_MM_MAP[inch_str] == mm_val

    # Prueba de detección de fracción 1/2 con PVC
    items = UnitNormalizerService.parse_and_normalize_line("10 caño pvc 1/2")
    assert len(items) == 1
    assert items[0].diameter_mm == 12.70
    assert items[0].material_type == "PVC"
    assert items[0].completeness == "complete"

    # Prueba de detección de 4" sanitario
    items_4 = UnitNormalizerService.parse_and_normalize_line("5 caño pvc 4\"")
    assert len(items_4) == 1
    assert items_4[0].diameter_mm == 110.00
    assert items_4[0].material_type == "PVC"


def test_cement_bag_standard_weight():
    """Verifica que la bolsa de cemento asuma por defecto 50.0 kg."""
    items = UnitNormalizerService.parse_and_normalize_line("50 bolsas de cemento")
    assert len(items) == 1
    assert items[0].quantity == 50.0
    assert items[0].weight_kg == 50.0
    assert items[0].material_type == "Cemento"
    assert items[0].completeness == "complete"


def test_hierro_del_10_and_del_6():
    """Verifica normalización de barras de acero de 10mm y 6mm."""
    items = UnitNormalizerService.parse_and_normalize_line("15 hierro del 10 y 30 hierro del 6")
    assert len(items) == 2
    assert items[0].diameter_mm == 10.0
    assert items[0].length_m == 12.0
    assert items[1].diameter_mm == 6.0
    assert items[1].length_m == 12.0


def test_caño_pvc_with_explicit_mm():
    """Verifica caños de PVC con milímetros explícitos (40 mm y 110 mm)."""
    items = UnitNormalizerService.parse_and_normalize_line("5 caño PVC 40 mm")
    assert len(items) == 1
    assert items[0].quantity == 5.0
    assert items[0].diameter_mm == 40.0
    assert items[0].material_type == "PVC"
    assert items[0].completeness == "complete"

    items_110 = UnitNormalizerService.parse_and_normalize_line("2 caño PVC 110 mm")
    assert len(items_110) == 1
    assert items_110[0].quantity == 2.0
    assert items_110[0].diameter_mm == 110.0
    assert items_110[0].material_type == "PVC"
    assert items_110[0].completeness == "complete"
