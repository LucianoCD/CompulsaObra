---
name: compulsa-aislamiento-demo-y-qa
description: >-
  Garantiza el aislamiento multitenant por workspace_id, la separación estricta
  entre el entorno [MODO DEMO DATOS COMERCIALES ILUSTRATIVOS] (is_demo = TRUE con
  los 3 corralones semilla de Jujuy) y las métricas auditables de /traccion
  (is_demo = FALSE), y la verificación empírica de los escenarios E2E-01 a E2E-05.
---

# Aislamiento de Workspace, Modo Demo Jujuy, `/traccion` y QA E2E (CompulsaObra)

## 1. Aislamiento por `workspace_id`, Autenticación Real y Seguridad
- Todas las consultas sobre `requisitions`, `product_aliases`, `comparison_runs` y `vendors` privados deben filtrar por `workspace_id == current_workspace_id` (permitiendo en `vendors` aquellos con `is_public_directory == True`).
- Para operar en un espacio de trabajo real (`is_demo == False`), se exige autenticación auténtica (`/auth/register` o `/auth/login`); queda terminantemente prohibida la creación de usuarios sintéticos con contraseñas fijas.
- La dependencia `deps.py:get_current_workspace` exige obligatoriamente un token Bearer válido con `user_id` verificado en base de datos para espacios no-Demo.
- Si un usuario intenta acceder o modificar una requisición, catálogo o comparativa de otro `workspace_id`, lanzar `WorkspaceIsolationError` (`403 Forbidden` / `404 Not Found`). La importación de catálogos valida autorización tanto en endpoint como en servicio (`CO-03`).
- Validar siempre la firma `HMAC-SHA256` en `/api/v1/public/comparisons/{share_token}` usando `hmac.compare_digest` y exigir que la corrida esté sellada con `LOCKED_BUDGET` (`CO-05`).

## 2. Entorno Demo (`is_demo = TRUE`) vs. Trazabilidad Real (`/traccion`)
- **Seed Idempotente (`seed.py`):** Al iniciar la aplicación, asegurar la existencia del workspace Demo (`is_demo = True`) y los 3 comercios semilla de Jujuy:
  1. `Corralón El Pórtico - Demo` (San Salvador de Jujuy)
  2. `Ferretería Industrial Cuyaya - Demo` (San Salvador de Jujuy)
  3. `Sanitarios y Materiales Palpalá - Demo` (Palpalá)
- **Interfaz Demo (`DemoBanner.tsx`):** Mientras `workspace.is_demo === true`, exhibir de forma visible la etiqueta `[MODO DEMO DATOS COMERCIALES ILUSTRATIVOS]`, el selector de rol (`BUYER` / `ESTIMATOR`) y el botón **"Pasar a Espacio Real"** que abre el modal de registro/login auténtico (`AuthModal.tsx`).
- **Filtro Estricto en `/api/v1/public/traction` (`E2E-05`):**
  - Las métricas públicas (`active_real_workspaces`, `real_vendors_compared`, `real_budgets_generated`, `total_lines_processed`, `median_elaboration_seconds`) deben filtrar **obligatoriamente** con `WHERE Workspace.is_demo == False`. Ninguna ejecución del modo Demo puede contaminar `/traccion`.

## 3. Matriz de Verificación Obligatoria (`E2E-01` a `E2E-05`)
Antes de dar por completada cualquier tarea de backend o frontend, verificar que pasen los 5 escenarios del contrato:
- **`E2E-01` (Ingesta y Bloqueo Dimensional):** `"20 barra del 8 y 4 caño de 3/4"` $\rightarrow$ 2 ítems (`8.0 mm x 12.0 m` completo y `19.05 mm` en `missing_critical_attribute`), bloqueando `/compare` hasta resolver el material del caño.
- **`E2E-02` (No-Sustitución Ciega):** Pedido de `"5 caño PVC 40 mm"` devuelve `NOT_CARRIED` en el negocio que sólo tiene `"Caño PVC 110 mm"` y `EXACT_MATCH` en el que sí tiene `40 mm`.
- **`E2E-03` (Split Cart vs. Proveedor Único):** `50 bolsas de cemento` + `40 barras del 8` con fletes $\rightarrow$ Mejor único `$892.000` vs. Carrito dividido `$857.000` $\rightarrow$ Ahorro neto `$35.000`.
- **`E2E-04` (Acopio y Snapshot PDF Inmutable):** Modalidad `ACOPIO` + margen `10%` + `lock-budget` $\rightarrow$ `public_share_token` válido, PDF `%PDF-1.4` descargable y `snapshot_json` inmutable ante nuevas listas Excel.
- **`E2E-05` (Aislamiento de `/traccion`):** 10 comparativas en `is_demo = TRUE` y 2 en `is_demo = FALSE` $\rightarrow$ `/api/v1/public/traction` reporta exactamente `real_budgets_generated == 2`.
