---
name: compulsa-normalizacion-y-matching
description: >-
  Rige la ingesta multimodal (Gemini 2.5 Flash + fallback determinista), la
  normalización física de unidades y jerga del NOA (pulgadas a mm, separación de
  conjunciones), el bloqueo Human-in-the-Loop ante atributos críticos faltantes y
  el Filtro Dimensional Duro SQL (FTS + pg_trgm / SQLite) con Cero Sustitución
  Ciega en CompulsaObra. Úsala al implementar o modificar unit_normalizer.py,
  multimodal_extractor.py, matching_engine.py, DisambiguationTable.tsx o tests
  E2E-01 y E2E-02.
---

# Normalización Dimensional, Desambiguación HITL y Motor de Matching (CompulsaObra)

## 1. Tabla Determinista de Equivalencias Físicas (`unit_normalizer.py`)
El normalizador debe aplicar sin ambigüedad el mapa exacto de pulgadas nominales a milímetros:
```python
INCH_TO_MM_MAP: dict[str, float] = {
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
```
- **Separación de conjunciones:** Si una línea contiene `" y "`, `" + "` o `;` donde el segundo segmento inicia con una cantidad numérica (ej. `"20 barra del 8 y 4 caño de 3/4"`), debe dividirse en ítems independientes manteniendo el orden `line_order`.
- **Jerga regional del NOA:**
  - `"hierro del 8"` / `"barra del 8"` $\rightarrow$ `canonical_term = "barra acero aletado"`, `diameter_mm = 8.0`, `length_m = 12.0`, `material_type = "Acero"`.
  - `"bolsa de cemento"` sin peso explícito $\rightarrow$ `weight_kg = 50.0`.
- **Detección de Atributos Críticos Faltantes (`missing_critical_attribute`):**
  - Para familias que exigen material constructivo (`caño`, `tubo`, `codo`, `tee`, `cupla`, `union`), si la entrada no especifica `PVC`, `Polipropileno`, `Termofusión`, `Corrugado` o `Hierro estructural`, asignar `completeness = 'missing_critical_attribute'`, `is_confirmed = False` y poblar `clarification_prompt` con las opciones estructuradas para la consola Human-in-the-Loop (`DisambiguationTable.tsx`).

## 2. Ingesta Multimodal con Fallback Determinista (`multimodal_extractor.py`)
- Soportar los 3 presets instantáneos: `manuscrito_obra`, `whatsapp_jerga_noa` y `computo_tecnico`.
- Cuando se recibe `image_bytes` y existe `GEMINI_API_KEY`, usar el SDK `google-genai` (`gemini-2.5-flash`) con Structured Outputs (`response_schema=RequisitionExtractionBatch`) y pasar cada renglón por `parse_and_normalize_line`.
- Si no hay `GEMINI_API_KEY` en entorno local/CI, aplicar el extractor determinista de respaldo sin lanzar errores 500.

## 3. Motor de Matching con Cero Sustitución Ciega (`matching_engine.py`)
Orden estricto de evaluación para cada `(workspace_id, item, vendor_id)`:
1. **Guarda de Completitud:** Si `item.completeness == 'missing_critical_attribute'`, lanzar inmediatamente `AmbiguousItemCannotBeMatchedError` (`400 Bad Request`).
2. **Memoria de Alias Supervisada (`product_aliases`):** Buscar por `(workspace_id, vendor_id, requested_term)` o `(workspace_id, NULL, requested_term)`. Verificar siempre que el `target_vendor_product_id` cumpla las dimensiones físicas del ítem antes de retornarlo.
3. **Filtro Dimensional Duro SQL (Innegociable):**
   - Si `item.diameter_mm IS NOT NULL`: `vendor_products.diameter_mm IS NOT NULL AND ABS(vendor_products.diameter_mm - :d) <= 0.5`
   - Si `item.length_m IS NOT NULL`: `vendor_products.length_m IS NOT NULL AND ABS(vendor_products.length_m - :l) <= 0.05`
   - Si `item.weight_kg IS NOT NULL`: `vendor_products.weight_kg IS NOT NULL AND ABS(vendor_products.weight_kg - :w) <= 0.5`
   - Si `item.material_type IS NOT NULL`: coincidencia normalizada del material.
4. **Ranking Léxico sobre Candidatos Físicamente Válidos:**
   - Ordenar únicamente los productos que superaron el filtro dimensional (`ts_rank_cd` + `similarity` en PostgreSQL 16, o puntaje léxico determinista por tokens/trigramas en SQLite).
   - Si ningún producto del comercio cumple la dimensión física exacta (ej. pide `"Caño PVC 40 mm"` y el comercio sólo tiene `"Caño PVC 110 mm"`), devolver `match_status = 'NOT_CARRIED'` (`unit_price_applied_ars = None`). **Jamás sustituir por otra medida.**
