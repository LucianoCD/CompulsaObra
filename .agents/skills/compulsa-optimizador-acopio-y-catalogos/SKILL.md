---
name: compulsa-optimizador-acopio-y-catalogos
description: >-
  Rige la importación de listas de precios Excel/CSV con deduplicación SHA-256
  incremental (catalog_importer.py), el algoritmo de compulsa multi-negocio,
  Compra Dividida Óptima (Split Cart) con fletes y simulador de Acopio
  (comparison_optimizer.py), y la emisión de snapshots inmutables firmados con
  HMAC-SHA256 y PDF vectorial con fpdf2 (pdf_generator.py). Úsala en TASK-03,
  TASK-06, TASK-07 y pruebas E2E-03 y E2E-04.
---

# Importador SHA-256, Optimizador Split Cart, Acopio y Emisión PDF (CompulsaObra)

## 1. Importación Multi-Fuente con Deduplicación Incremental (`catalog_importer.py`)
- Soportar archivos `.xlsx` (`openpyxl`), `.xls` binario (`xlrd>=2.0.1`) y `.csv` con mapeo de columnas (`ColumnMappingSchema`).
- Validar autorización por `workspace_id` tanto en el endpoint como en el servicio, impidiendo importar catálogos sobre comercios públicos o ajenos (`CO-03`).
- Parsear importes en formato moneda argentina (`$ 10.500,50`, `10.500` o `9500.00`) validando `price_cash_ars > 0` y `price_list_ars > 0`. Si no se provee precio contado específico y el corralón tiene `cash_discount_pct > 0`, calcular automáticamente el precio contado con descuento.
- Calcular para cada fila:
  `row_sha256 = hashlib.sha256(f"{sku.strip().upper()}||{normalized_desc}".encode()).hexdigest()`
- Deduplicar intra-lote (`seen_hashes_in_batch`) para evitar insertar duplicados idénticos en el mismo archivo (`CO-12`).
- Consultar la versión activa previa (`price_lists` con `is_active = True`) del mismo `vendor_id`:
  - Si `row_sha256` coincide con un producto previo, **clonar directamente** `diameter_mm`, `length_m`, `weight_kg` y `material_type` sin re-ejecutar el parser dimensional e incrementar `unchanged_skipped_rows`.
  - Si es nuevo o cambió la descripción, ejecutar `unit_normalizer` para extraer dimensiones e incrementar `new_or_updated_rows`.
- Desactivar la lista anterior (`is_active = False`) y activar la nueva (`version_number = prev + 1`, `is_active = True`) dentro de la misma transacción.

## 2. Algoritmo de Compulsa Multi-Negocio (`comparison_optimizer.py`)
1. **Mejor Proveedor Único (`Best Single Vendor`):**
   - Evaluar cada negocio $v \in V$: calcular `coverage_pct` (porcentaje de ítems confirmados con `match_status == 'EXACT_MATCH'`).
   - Ordenar los negocios priorizando **1° mayor `coverage_pct`** y **2° menor `SingleTotal`** (donde `SingleTotal = sum(line_subtotal_ars) + (estimate_delivery_fee_ars if include_delivery_fees else 0)`).
2. **Compra Dividida Óptima por Subconjuntos (`Optimal Split Cart`):**
   - Evaluar los subconjuntos globales de comercios para minimizar $\sum \text{materiales} + \sum \text{fletes únicos utilizados}$.
   - Evita la trampa de selección voraz que añade corralones por centavos incrementando el costo logístico total (`CO-07`).
   - Calcular `split_cart_savings_ars = best_single_total_ars - split_cart_total_ars`.
   - En el escenario de referencia `E2E-03` (`50 bolsas de cemento` + `40 barras del 8`), verificar que `best_single_total_ars == 892000.00`, `split_cart_total_ars == 857000.00` y `split_cart_savings_ars == 35000.00`.
3. **Simulador de Acopio (`ACOPIO`):**
   - Soportar política tarifaria explícita `price_basis: "LIST" | "CASH"` (`CO-09`).
   - A partir de `vendor.acopio_config_json` (`enabled`, `min_down_payment_pct`, `freeze_days`, `max_withdrawal_days`, `min_notice_hours`, `price_basis`), calcular:
     - `down_payment_ars = total_ars * (min_down_payment_pct / 100.0)`
     - `remaining_balance_ars = total_ars - down_payment_ars`
     - `freeze_until_date = created_at + timedelta(days=freeze_days)`
     - `max_withdrawal_date = created_at + timedelta(days=max_withdrawal_days)`
4. **Margen Profesional (`markup_pct`):**
   - Calcular los importes finales al cliente aplicando `total_with_markup = total * (1 + markup_pct / 100.0)` para el rol `ESTIMATOR`.

## 3. Congelamiento Inmutable (`lock-budget`) y Generación PDF (`pdf_generator.py`)
- Al congelar una comparativa (`LOCKED_BUDGET`), sellar `status: LOCKED_BUDGET` dentro de `comparison_matrix_json` como instantánea inmutable por corrida (`CO-05`). Posteriores importaciones jamás alteran un presupuesto histórico congelado.
- Reasignación manual (`override_item_match` / `applyMatrixOverride`): actualizar en la misma transacción las columnas relacionales de `ComparisonRun` y la matriz sin sobrescribir la corrida (`CO-06`).
- Generar PDFs vectoriales con `fpdf2` (sin dependencias C/GTK externas) incorporando fletes de entrega tanto en `mode="comparison"` como en `mode="client_budget"` (`CO-08`).
