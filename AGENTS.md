# AGENTS.md — Contrato Arquitectónico y Operativo de CompulsaObra (`compulsa-obra`)

## 1. Visión y Contexto del Sistema
**CompulsaObra** (evolución de *CotizaObra AI Comparador*, especificación en [`especificaci_n_funcional_cotizaobra_ai_comparador.md`](file:///C:/Users/lucia/OneDrive/Documents/Pruebas/ComPresupuesto/especificaci_n_funcional_cotizaobra_ai_comparador.md)) es un **Sistema Inteligente de Elaboración de Presupuestos y Comparación Multi-Negocio de Materiales de Construcción** orientado a presupuestadores profesionales (`ESTIMATOR`) y compradores finales (`BUYER`) del NOA (San Salvador de Jujuy, Palpalá, Perico y El Carmen).

### Estructura del Repositorio
- **`backend/`**: API REST en **Python 3.12+ / FastAPI 0.115+**, validación con **Pydantic v2 (`>=2.9.0`)**, persistencia híbrida en **SQLAlchemy 2.0** (`PostgreSQL 16` con `pg_trgm` + `unaccent` + `TSVECTOR` en producción/Docker y compatibilidad transparente con `SQLite` para desarrollo local y `pytest`), migraciones **Alembic**, ingesta multimodal con **Google GenAI SDK (`google-genai`, `gemini-2.5-flash`) + Fallback Determinista Local**, importación Excel/CSV con **`openpyxl`** y generación de PDFs vectoriales nativos con **`fpdf2`**.
- **`frontend/`**: Aplicación Web/PWA en **React 18 + TypeScript 5.x (`strict: true`, cero `any`) + Vite + Zustand + Tailwind CSS + Lucide Icons**.
- **`docker-compose.yml`**: Orquestación de `PostgreSQL 16` (`:5432`), `backend` (`:8000`) y `frontend` (`:5173`).

---

## 2. Invariantes Innegociables de Dominio y Seguridad

1. **Invariante de Seguridad Dimensional (Cero Sustitución Ciega):**
   - **Normalización Física Determinista (`unit_normalizer.py`):** Conversión exacta de pulgadas fraccionarias a milímetros (`"1/2"` -> `12.70`, `"3/4"` -> `19.05`, `"1"` -> `25.40`, `"1 1/4"` -> `31.75`, `"1 1/2"` -> `38.10`, `"2"` -> `50.80`, `"2 1/2"` -> `63.50`, `"3"` -> `75.00`, `"4"` -> `110.00` sanitario PVC cloacal), separación de conjunciones (`" y "`, `" + "`), longitud por defecto `12.0 m` en barras de acero aletado y peso `50.0 kg` en bolsas de cemento estándar.
   - **Bloqueo Pre-Cotización Human-in-the-Loop:** Si un ítem pertenece a familias que exigen material (`caño`, `tubo`, `codo`, `tee`, `cupla`, `union`) y no se especificó (`PVC`, `Polipropileno`, `Termofusión`, `Corrugado`, `Hierro estructural`), se marca `completeness = 'missing_critical_attribute'` y la requisición queda en `NEEDS_CLARIFICATION`. Si `matching_engine.py` recibe un ítem en ese estado, debe lanzar `AmbiguousItemCannotBeMatchedError`.
   - **Filtro Dimensional Duro SQL (`matching_engine.py`):** Previo a cualquier ranking léxico (`FTS + pg_trgm` o ranking determinista en SQLite), la consulta SQL debe exigir tolerancia estricta:
     - `diameter_mm`: `ABS(vendor_products.diameter_mm - :d) <= 0.5` (y `IS NOT NULL`)
     - `length_m`: `ABS(vendor_products.length_m - :l) <= 0.05`
     - `weight_kg`: `ABS(vendor_products.weight_kg - :w) <= 0.5`
     - `material_type`: coincidencia normalizada cuando el ítem lo especifica.
   - **Prohibición absoluta:** Jamás emparejar un `"Caño PVC 110 mm"` cuando se pide `"Caño PVC 40 mm"`, ni una `"Barra Ø 10 mm"` cuando se pide `"Barra Ø 8 mm"`. Si el comercio no trabaja esa medida exacta, devolver `match_status = 'NOT_CARRIED'`.

2. **Deduplicación Incremental de Catálogos (`catalog_importer.py`):**
   - Toda fila importada de `.xlsx`, `.xls` o `.csv` limpia moneda ARS (`$ 10.500,50`) y calcula `row_sha256 = hashlib.sha256(f"{sku.strip().upper()}||{normalized_desc}".encode()).hexdigest()`.
   - Si el `row_sha256` ya existe en la versión activa previa (`price_lists`) del mismo `vendor_id`, se clonan sus atributos dimensionales sin re-ejecutar el parser técnico, reportando `unchanged_skipped_rows` vs. `new_or_updated_rows`.

3. **Motor de Compulsa Multi-Negocio, Carrito Dividido y Simulador de Acopio (`comparison_optimizer.py`):**
   - **Mejor Proveedor Único (`Best Single Vendor`):** Ordena por máxima cobertura (`coverage_pct`) y luego menor costo total con flete (`SingleTotal = sum(subtotal) + estimate_delivery_fee_ars`).
   - **Compra Dividida Óptima (`Optimal Split Cart`):** Selecciona el proveedor más económico por ítem, suma los fletes únicos (`estimate_delivery_fee_ars`) de cada proveedor utilizado en la canasta dividida y calcula `split_cart_savings_ars = best_single_total_ars - split_cart_total_ars`.
   - **Simulación de Acopio (`ACOPIO`):** Calcula `down_payment_ars`, `remaining_balance_ars`, `freeze_until_date` (`created_at + freeze_days`), `max_withdrawal_date` (`created_at + max_withdrawal_days`) y `min_notice_hours`.
   - **Inmutabilidad y Firma (`lock-budget` & `pdf_generator.py`):** Congela `comparison_matrix_json` inmutable, emite `public_share_token` firmado con `HMAC-SHA256` y genera PDFs vectoriales con `fpdf2` en modo `comparison` (Comparativa de Compra) y `client_budget` (Presupuesto al Cliente Final con `markup_pct`).

4. **Aislamiento por `workspace_id`, Modo Demo y Trazabilidad `/traccion`:**
   - Toda consulta a recursos privados filtra por `WHERE workspace_id = :current_workspace_id` (excepto catálogos con `is_public_directory = TRUE`).
   - La aplicación inicia en sesión Demo (`is_demo = TRUE`) con los 3 corralones semilla de Jujuy (`Corralón El Pórtico - Demo`, `Ferretería Industrial Cuyaya - Demo`, `Sanitarios y Materiales Palpalá - Demo`) exhibiendo el cintillo `[MODO DEMO DATOS COMERCIALES ILUSTRATIVOS]`.
   - El endpoint `GET /api/v1/public/traction` y la vista `/traccion` contabilizan **exclusivamente** espacios de trabajo reales (`WHERE workspaces.is_demo = FALSE`).

---

## 3. Convenciones Técnicas Estrictas (Pydantic v2 / SQLAlchemy 2.0 / TypeScript Strict)
- **Pydantic v2:** Usar exclusivamente `model_validate`, `model_dump`, `ConfigDict(from_attributes=True)` y `@field_validator`. Prohibido `.dict()`, `.parse_obj()` o `class Config:`.
- **SQLAlchemy 2.0:** Usar exclusivamente `Mapped[...]`, `mapped_column(...)` y `select(...)`. Prohibido `session.query()` legado o consultas `N+1`.
- **Frontend React + TS:** Espejar 1:1 `frontend/src/types/api.ts` con `backend/app/schemas/`. Prohibido el uso de `any`. Mantener stores modulares en Zustand (`useWorkspaceStore`, `useRequisitionStore`, `useComparisonStore`) y números tabulares (`tabular-nums`) para importes ARS.
- **Revisión Fuera del Diff (`ponytail-review`):** Todo cambio en esquemas `backend/app/schemas/` o modelos `backend/app/models/` exige inspeccionar y actualizar sus consumidores en `backend/app/services/`, `backend/app/api/v1/endpoints/`, `backend/tests/` y `frontend/src/types/api.ts`.

---

## 4. Arnés de Verificación Empírica (Obligatorio Antes de Cerrar)
1. **Modelos SQLAlchemy 2.0:**
   `cd backend && python -c "from app.models import Workspace, Vendor, PriceList, VendorProduct, Requisition, ComparisonRun; print('MODELS_OK')"`
2. **Suite Backend Completa (`pytest` — Escenarios `E2E-01` a `E2E-05`):**
   `cd backend && pytest -v`
3. **Extractor Multimodal y Presets:**
   `cd backend && python -c "from app.services.multimodal_extractor import MultimodalExtractorService; svc = MultimodalExtractorService(); res = svc.extract_from_preset('whatsapp_jerga_noa'); assert len(res) >= 3; print('EXTRACTOR_OK')"`
4. **Typecheck y Build Frontend:**
   `cd frontend && npx tsc --noEmit && npm run build`
