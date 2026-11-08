---
name: ponytail-mvp-audit
description: >-
  Aplica la suite completa de minimalismo senior (Ponytail) en CompulsaObra:
  (1) ponytail-review para revisión fuera del diff entre esquemas Pydantic v2,
  motores de dominio y tipos TypeScript en frontend/src/types/api.ts,
  (2) ponytail-audit para mapeo de entrypoints y priorización en el motor SQL
  dimensional e importador SHA-256, y
  (3) ponytail-debt para auditar deuda técnica controlada (// shortcut: [PPS-MVP]).
---

# Ponytail Suite — Minimalismo Senior, Revisión Out-of-Diff y Auditoría en CompulsaObra

## 1. Protocolo `ponytail-review` — Revisión Fuera del Diff (*Out-of-Diff Review*)
Al modificar modelos en `backend/app/models/`, esquemas en `backend/app/schemas/`, servicios en `backend/app/services/` o contratos en `frontend/src/types/api.ts`:
1. **Identifica cada símbolo modificado** en el `git diff`.
2. **Inspecciona todos los llamadores y consumidores fuera del diff:**
   - Si cambia un esquema Pydantic v2 en `backend/app/schemas/`, verifica su reflejo exacto en `frontend/src/types/api.ts`, los stores de Zustand (`useWorkspaceStore`, `useRequisitionStore`, `useComparisonStore`) y los tests en `backend/tests/`.
   - Si cambia `unit_normalizer.py`, verifica cómo impacta en `catalog_importer.py`, `multimodal_extractor.py` y `matching_engine.py`.
3. **Confirma las invariantes físicas y de aislamiento:** Ningún cambio puede relajar el filtro dimensional duro (`diameter_mm`, `length_m`, `weight_kg`), la deduplicación `row_sha256` ni el filtro `WHERE workspace_id = :current_workspace_id`.

## 2. Protocolo `ponytail-audit` — Mapeo de Entrypoints y Carga
1. Enumera los endpoints en `backend/app/api/v1/endpoints/` y las páginas/componentes en `frontend/src/`.
2. Concentra las optimizaciones algorítmicas e índices SQL en las rutas calientes:
   - `POST /api/v1/vendors/{vendor_id}/catalogs/import` (deduplicación incremental por `row_sha256` e inserción por lotes).
   - `POST /api/v1/requisitions/{req_id}/compare` (precarga sin consultas `N+1` y filtro dimensional indexado en `vendor_products`).
3. Evita sobre-ingeniería en vistas estáticas o modales de configuración.

## 3. Protocolo `ponytail-debt` — Auditoría de Deuda Técnica Controlada
Escanea `backend/` y `frontend/` en busca del marcador estándar:
`// shortcut: [PPS-MVP] <descripción de la simplificación> | trigger: <condición técnica o de escala para evolucionarlo>`
(o `# shortcut: [PPS-MVP] ...` en Python) y compila la tabla consolidada con enlaces clicables a cada archivo, disparador de evolución y arquitectura objetivo.
