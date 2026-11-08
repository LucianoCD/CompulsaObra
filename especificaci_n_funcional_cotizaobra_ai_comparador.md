# Especificación Funcional y Arquitectura del Sistema: CotizaObra AI (Enfoque Presupuestador y Comprador Multi-Negocio)

---

## 1. MANIFIESTO DEL SISTEMA Y REGLAS DEL ORQUESTADOR (`AGENT_RULES.md`)

### 1.1 Resumen Ejecutivo y Dominio
El sistema redefine la arquitectura original de **CotizaObra AI** (concebida inicialmente como un SaaS B2B exclusivo para el mostrador de un único corralón o ferretería en San Salvador de Jujuy, Palpalá, Perico y El Carmen) para posicionar como actor central y cliente directo a **la persona que elabora presupuestos (presupuestador profesional, arquitecto, maestro mayor de obra, contratista o encargado de compras)** y al **usuario final comprador (autoconstructor o particular que ejecuta una remodelación u obra)**. En lugar de que cada comercio opere como un silo aislado, la plataforma funciona como un **Sistema Inteligente de Elaboración de Presupuestos y Comparación Multi-Negocio de Materiales de Construcción**.

El flujo operativo resuelve de raíz las cuatro fricciones del mercado local —demora comercial al consultar múltiples negocios, errores de interpretación dimensional entre medidas nominales, pérdida de trazabilidad sobre vigencia o condiciones de pago, y abandono de listas extensas de 20 a 50 ítems— invirtiendo el control hacia el comprador y el presupuestador mediante cinco capacidades funcionales integradas:

1. **Ingesta Multimodal y Estandarización Técnica de Pedidos:** El usuario (comprador o presupuestador) ingresa fotografías de listas manuscritas redactadas en obra por albañiles, plomeros o electricistas, textos libres con jerga regional y abreviaturas de WhatsApp, o planillas de cómputo métrico. El sistema transforma la entrada desestructurada en un **Pliego Técnico Normalizado de Materiales (`NormalizedRequisition`)**, separando cada ítem base de sus restricciones físicas (diámetros en milímetros o pulgadas fraccionarias, longitudes comerciales de $4\text{ m}$, $6\text{ m}$ o $12\text{ m}$, pesos de bolsa de $25\text{ kg}$, $40\text{ kg}$ o $50\text{ kg}$, y material constructivo).
2. **Desambiguación Asistida Pre-Cotización (Human-in-the-Loop del Comprador/Presupuestador):** Antes de cotizar o comparar precios, el motor de validación dimensional detecta atributos críticos faltantes (por ejemplo, pedir `"4 caño de 3/4"` sin especificar si es PVC cloacal, polipropileno roscado, termofusión o corrugado eléctrico). La interfaz bloquea el emparejamiento ciego y guía al usuario para definir la especificación técnica exacta con un clic, guardando sus preferencias y equivalencias frecuentes en su diccionario de alias supervisado.
3. **Gestión Multi-Fuente de Precios de Negocios (`VendorPriceSources`):** El usuario puede alimentar el comparador a través de tres vías complementarias: (a) importar listas de precios en archivos `.xlsx`, `.xls` o `.csv` obtenidas de distintos corralones y ferreterías mediante un mapeador visual con control de versiones y hash SHA-256 por fila; (b) cargar presupuestos recibidos de distintos negocios (en PDF, imagen o enlace público) para extraer sus precios unitarios y condiciones comerciales; o (c) consultar catálogos de negocios locales adheridos en el directorio regional.
4. **Motor de Comparación Multi-Negocio y Optimización de Compra:** Una vez normalizados los ítems del pedido, el sistema cruza cada renglón contra múltiples negocios aplicando un filtro dimensional duro en PostgreSQL (`FTS + pg_trgm`) para garantizar que jamás se compare un caño de PVC de $40\text{ mm}$ de un comercio contra uno de $110\text{ mm}$ de otro. El comparador genera una **Matriz Comparativa Multi-Comercio** que evalúa cuatro estrategias deterministas:
   - **Compra Unificada (Un Solo Proveedor):** Costo total por negocio considerando el porcentaje de cobertura de la lista (ítems disponibles vs. faltantes) para ahorrar fletes.
   - **Compra Optimizada (Carrito Dividido / Cherry-Picking):** Selección del negocio más económico para cada línea individual, calculando el ahorro bruto y descontando el costo logístico estimado de retirar o recibir entregas de múltiples comercios.
   - **Comparativa por Modalidad Comercial (Contado vs. Financiado vs. Acopio):** Evaluación financiera lado a lado entre bonificaciones por pago al contado/transferencia, precio de lista financiado y condiciones de **Acopio de Materiales** (porcentaje de anticipo exigido para congelar precio, plazo de vigencia en días corridos, límite de retiro y preaviso logístico).
   - **Equivalencia de 1ª y 2ª Marca:** Comparación transparente cuando dos negocios cotizan el mismo atributo físico bajo distintas marcas comerciales.
5. **Emisión de Presupuestos Profesionales y Pliegos de Compulsa:** El presupuestador puede agregar su margen de gestión o mano de obra, congelar una instantánea (`snapshot`) inmutable de los precios comparados y exportar un documento PDF membretado o un enlace público firmado, ya sea como presupuesto final para su comitente o como solicitud de cotización estandarizada (RFQ) para enviar por WhatsApp a nuevos corralones.

---

### 1.2 Stack Tecnológico Congelado

| Capa | Tecnología y Versión | Convención Estricta / Patrón Obligatorio | Prohibición Explícita (Anti-Patrón) |
|---|---|---|---|
| **Backend API** | Python 3.12 + FastAPI 0.115+ | Arquitectura en capas (`routers -> services -> repositories -> models`). Inyección de dependencias con `Annotated[..., Depends(...)]`. | Prohibido incluir consultas SQL o lógica de negocio dentro de los endpoints HTTP. |
| **Validación y Contratos** | Pydantic v2 (`>=2.9.0`) | Uso exclusivo de `model_validate`, `model_dump`, `ConfigDict(from_attributes=True)` y `@field_validator`. | Prohibido usar métodos deprecados de Pydantic v1 (`.dict()`, `.parse_obj()`, `@validator`, `class Config:`). |
| **Persistencia y Búsqueda** | PostgreSQL 16 + SQLAlchemy 2.0 (Async/Sync 2.0 style) + Alembic | Consultas tipadas con `select()`, índices `GIN` sobre `tsvector` (`spanish`) y extensión `pg_trgm` con filtro dimensional SQL estricto previo al ranking léxico. | Prohibido usar `session.query()` legado de SQLAlchemy 1.x, consultas `N+1` en bucles o emparejar productos sin filtrar primero por dimensiones físicas exactas. |
| **Ingesta Multimodal y Archivos** | SDK Multimodal con Structured Outputs JSON + `openpyxl` / `pandas` | Extracción determinista ajustada al esquema Pydantic `ExtractedLineItem` y cálculo de huella `SHA-256` por fila normalizada en importaciones Excel/CSV. | Prohibido ejecutar OCR libre sin validación de esquema JSON o reprocesar filas de catálogos cuyo hash `SHA-256` no haya cambiado. |
| **Frontend Web / PWA** | React 18 + TypeScript 5.x (Strict Mode) + Vite + Zustand + Tailwind CSS | Estado global tipado dividido en stores modulares (`useWorkspaceStore`, `useRequisitionStore`, `useComparisonStore`). Diseño adaptable a escritorio y móvil. | Prohibido el uso del tipo `any`, mutación directa de estado fuera de acciones de Zustand o llamadas `fetch` sin cliente HTTP centralizado. |
| **Documentación y Exportación** | Motor de plantillas HTML/CSS a PDF + Tokens HMAC-SHA256 para enlaces públicos | Todo presupuesto o comparativa emitida persiste un `snapshot_json` inmutable de los precios y reglas de acopio vigentes al momento de emisión. | Prohibido recalcular dinámicamente un presupuesto histórico leyendo precios actuales del catálogo sin crear una nueva revisión versionada. |

---

### 1.3 Invariantes Globales de Seguridad y Calidad
1. **Aislamiento por Espacio de Trabajo (`workspace_id`):** Cada presupuestador o comprador opera dentro de un espacio de trabajo aislado (`workspaces`, evolución del concepto `tenant_id` centrado en el usuario). Todas las consultas a proyectos, listas de materiales, catálogos privados importados, alias de productos y comparativas deben incluir el predicado obligatorio `WHERE workspace_id = :current_workspace_id` (con excepción de los catálogos públicos de demostración marcados con `is_public_directory = TRUE`).
2. **Invariante de Seguridad Dimensional (Cero Sustitución Ciega):** Si una línea solicitada especifica una dimensión física (`diameter_mm`, `length_m`, `weight_kg` o `thickness_mm`), el motor de comparación tiene **estrictamente prohibido** emparejarla con un producto de catálogo que posea un valor distinto en esa dimensión, incluso si la similitud trigramática (`pg_trgm`) del nombre supera el $0.90$. Si a la línea solicitada le falta un atributo físico crítico (`completeness = 'missing_critical_attribute'`), el estado del renglón debe permanecer en `NEEDS_CLARIFICATION` y no puede incluirse como confirmado en un cierre de presupuesto sin acción explícita del usuario.
3. **Trazabilidad y Privacidad de Listas de Precios (`/traccion` y Repositorio):** Las listas de precios Excel cargadas por usuarios o comercios piloto nunca se exponen públicamente ni se versionan en el repositorio Git. El endpoint público `/api/v1/metrics/traction` expone únicamente agregados estadísticos auditables de cuentas reales (`is_demo = FALSE`), excluyendo por completo las ejecuciones realizadas en el entorno `[MODO DEMO DATOS COMERCIALES ILUSTRATIVOS]`.
4. **Configuración Determinista y Variables de Entorno:** Ninguna credencial, clave secreta JWT/HMAC ni cadena de conexión puede escribirse en el código fuente. Toda configuración se valida en el arranque mediante `pydantic-settings` en `backend/app/core/config.py`.

---

## 2. MAPA ESTRUCTURAL DEL REPOSITORIO (`DIRECTORY_TREE`)

```text
cotizaobra-comparador/
├── docker-compose.yml                          # Orquestacion de PostgreSQL 16, Backend FastAPI y Frontend Vite
├── .env.example                                # Plantilla determinista de variables de entorno
├── README.md                                   # Guia de despliegue rapido y ejecucion de pruebas
├── backend/
│   ├── Dockerfile                              # Imagen Python 3.12-slim con dependencias del sistema para PDF
│   ├── pyproject.toml                          # Dependencias exactas, configuracion de pytest y ruff
│   ├── alembic.ini                             # Configuracion de migraciones de base de datos
│   ├── alembic/
│   │   ├── env.py                              # Entorno de ejecucion de Alembic conectado a Base
│   │   └── versions/
│   │       └── 0001_initial_schema.py          # Migracion inicial con extensiones pg_trgm, unaccent y tablas core
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                             # Punto de entrada FastAPI, middlewares CORS y registro de routers
│   │   ├── core/
│   │   │   ├── config.py                       # Validacion de entorno con Pydantic Settings V2
│   │   │   ├── database.py                     # Engine SQLAlchemy 2.0, SessionLocal y dependencia get_db
│   │   │   ├── security.py                     # JWT Auth, hashing de contraseñas y firma HMAC de links publicos
│   │   │   └── exceptions.py                   # Excepciones de dominio y manejadores HTTP deterministas
│   │   ├── models/
│   │   │   ├── __init__.py                     # Exportacion centralizada de modelos SQLAlchemy 2.0
│   │   │   ├── workspace.py                    # Modelos Workspace y User (Comprador / Presupuestador)
│   │   │   ├── vendor.py                       # Modelos Vendor (Negocio/Corralon), PriceList, VendorProduct y ProductAlias
│   │   │   ├── requisition.py                  # Modelos Requisition (Pedido/Obra) y RequisitionItem (Item normalizado)
│   │   │   └── comparison.py                   # Modelos ComparisonRun, VendorQuoteOption, VendorItemMatch y SavedBudget
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── common.py                       # Esquemas base Pydantic V2, paginacion y respuestas de error
│   │   │   ├── dimensions.py                   # Esquemas PhysicalDimensions, equivalencias pulgadas/mm y validadores
│   │   │   ├── vendor.py                       # Contratos de importacion Excel/CSV, negocios y reglas de acopio
│   │   │   ├── requisition.py                  # Contratos de ingesta multimodal, desambiguacion y pliego de materiales
│   │   │   └── comparison.py                   # Contratos de matriz comparativa multi-negocio, carrito dividido y PDF
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── unit_normalizer.py              # Diccionario determinista de unidades, pulgadas a mm y jerga NOA
│   │   │   ├── catalog_importer.py             # Lector Excel/CSV, mapeo de columnas y deduplicacion SHA-256 por fila
│   │   │   ├── multimodal_extractor.py         # Procesador de fotos manuscritas y texto libre hacia esquemas tipados
│   │   │   ├── matching_engine.py              # Motor SQL FTS + pg_trgm con filtro duro dimensional y memoria de alias
│   │   │   ├── comparison_optimizer.py         # Algoritmo comparador multi-negocio, carrito dividido y calculo de acopio
│   │   │   └── pdf_generator.py                # Generador de pliegos comparativos y presupuestos en PDF con snapshot
│   │   └── api/
│   │       └── v1/
│   │           ├── __init__.py
│   │           ├── router.py                   # Enrutador maestro v1
│   │           ├── endpoints/
│   │           │   ├── auth.py                 # Registro, login y cambio de modo Demo / Real
│   │           │   ├── vendors.py              # ABM de negocios comparados, reglas de acopio e importacion Excel/CSV
│   │           │   ├── requisitions.py         # Ingesta por foto/texto, desambiguacion HITL y alias supervisados
│   │           │   ├── comparisons.py          # Ejecucion de comparativa multi-negocio, optimizacion y emision de presupuesto
│   │           │   └── public.py               # Vista publica de presupuestos firmados y tablero auditable /traccion
│   └── tests/
│       ├── conftest.py                         # Fixtures de base de datos de prueba y catálogos semilla de corralones
│       ├── test_unit_normalizer.py             # Tests de conversion dimensional (1/2", 3/4", barras 8mm vs 10mm)
│       ├── test_catalog_importer.py            # Tests de importacion Excel/CSV y hash SHA-256 incremental
│       ├── test_matching_engine.py             # Tests de bloqueo dimensional duro y no-sustitucion ciega
│       └── test_comparison_optimizer.py        # Tests de matriz multi-negocio, compra dividida y reglas de acopio
└── frontend/
    ├── Dockerfile                              # Imagen Node 20-alpine para construccion y previsualizacion
    ├── package.json                            # Dependencias React 18, Zustand, Tailwind, Lucide, Vitest
    ├── tsconfig.json                           # Configuracion TypeScript con strict: true
    ├── vite.config.ts                          # Configuracion Vite y proxy a /api/v1
    ├── index.html                              # Documento raiz con metadatos PWA
    └── src/
        ├── main.tsx                            # Punto de montaje de React
        ├── App.tsx                             # Rutas principales y layout con barra de estado Demo/Real
        ├── types/
        │   └── api.ts                          # Interfaces TypeScript espejadas con los esquemas Pydantic V2
        ├── services/
        │   └── apiClient.ts                    # Cliente HTTP tipado con manejo centralizado de errores
        ├── store/
        │   ├── useWorkspaceStore.ts            # Estado de sesion, perfil (Comprador vs Presupuestador) y modo Demo
        │   ├── useRequisitionStore.ts          # Estado de la lista de materiales activa y resolucion de ambigüedades
        │   └── useComparisonStore.ts           # Estado de negocios seleccionados, matriz comparativa y estrategia elegida
        ├── components/
        │   ├── DemoBanner.tsx                  # Cintillo obligatorio [MODO DEMO DATOS COMERCIALES ILUSTRATIVOS]
        │   ├── IngestionDropzone.tsx           # Carga de foto manuscrita, texto de WhatsApp o seleccion de presets
        │   ├── DisambiguationTable.tsx         # Consola Human-in-the-Loop (verde/amarillo) con selector dimensional
        │   ├── VendorCatalogModal.tsx          # Mapeador visual de columnas Excel/CSV y editor de reglas de acopio
        │   ├── MultiVendorMatrix.tsx           # Tabla comparativa lado a lado entre negocios y alerta de faltantes
        │   ├── SplitCartOptimizerCard.tsx      # Tarjeta comparativa: Mejor Proveedor Unico vs Compra Dividida Optima
        │   └── AcopioSimulatorPanel.tsx        # Comparador de condiciones de Contado, Lista y Acopio por comercio
        └── pages/
            ├── BuilderDashboardPage.tsx        # Flujo principal de 4 pasos para elaborar y comparar presupuestos
            ├── PublicBudgetViewPage.tsx        # Vista compartible por enlace unico para clientes o proveedores
            └── TractionEvidencePage.tsx        # Tablero publico auditable (/traccion) con metricas reales
```

---

## 3. ESPECIFICACIÓN DE CONTRATOS Y DOMINIO (`CONTRACTS.md`)

### 3.1 Esquema de Persistencia y Modelos de Datos

| Entidad / Tabla | Campos y Tipos Exactos | Claves e Índices | Invariantes y Restricciones de Integridad |
|---|---|---|---|
| `workspaces` | `id: UUID`, `name: VARCHAR(120)`, `owner_role: VARCHAR(30)` (`'BUYER'` \| `'ESTIMATOR'`), `is_demo: BOOLEAN DEFAULT FALSE`, `created_at: TIMESTAMPTZ` | `PK(id)`, `IDX(is_demo)` | Aísla los proyectos, listas de precios privadas y presupuestos de cada usuario. Las cuentas con `is_demo = TRUE` quedan excluidas de `/traccion`. |
| `users` | `id: UUID`, `workspace_id: UUID`, `email: VARCHAR(180)`, `full_name: VARCHAR(120)`, `password_hash: VARCHAR(255)`, `role: VARCHAR(30)`, `created_at: TIMESTAMPTZ` | `PK(id)`, `FK(workspace_id -> workspaces.id ON DELETE CASCADE)`, `UNIQUE(email)` | `CHECK (role IN ('BUYER', 'ESTIMATOR', 'ADMIN'))`. |
| `vendors` | `id: UUID`, `workspace_id: UUID NULL`, `name: VARCHAR(140)`, `locality: VARCHAR(80)`, `whatsapp_phone: VARCHAR(30) NULL`, `is_public_directory: BOOLEAN DEFAULT FALSE`, `cash_discount_pct: NUMERIC(5,2) DEFAULT 0.00`, `estimate_delivery_fee_ars: NUMERIC(12,2) DEFAULT 0.00`, `acopio_config_json: JSONB`, `created_at: TIMESTAMPTZ` | `PK(id)`, `FK(workspace_id -> workspaces.id ON DELETE CASCADE)`, `IDX(workspace_id, is_public_directory)` | Representa cada negocio o corralón a comparar (ej. en San Salvador de Jujuy, Palpalá, Perico o El Carmen). `acopio_config_json` almacena: `enabled: bool`, `min_down_payment_pct: float`, `freeze_days: int`, `max_withdrawal_days: int`, `min_notice_hours: int`. |
| `price_lists` | `id: UUID`, `vendor_id: UUID`, `version_number: INTEGER`, `source_filename: VARCHAR(255)`, `valid_from: TIMESTAMPTZ`, `valid_until: TIMESTAMPTZ NULL`, `row_count: INTEGER`, `is_active: BOOLEAN DEFAULT TRUE` | `PK(id)`, `FK(vendor_id -> vendors.id ON DELETE CASCADE)`, `UNIQUE(vendor_id, version_number)` | Cada importación de Excel/CSV o carga de cotización crea una versión inmutable vinculada al negocio proveedor. `CHECK (version_number >= 1)`. |
| `vendor_products` | `id: UUID`, `price_list_id: UUID`, `vendor_id: UUID`, `sku: VARCHAR(80)`, `raw_description: TEXT`, `normalized_description: TEXT`, `brand: VARCHAR(80) NULL`, `brand_tier: VARCHAR(20) DEFAULT 'STANDARD'`, `category: VARCHAR(80) NULL`, `sale_unit: VARCHAR(30)`, `price_cash_ars: NUMERIC(14,2)`, `price_list_ars: NUMERIC(14,2)`, `stock_available: BOOLEAN DEFAULT TRUE`, `diameter_mm: NUMERIC(8,2) NULL`, `length_m: NUMERIC(8,2) NULL`, `weight_kg: NUMERIC(8,2) NULL`, `material_type: VARCHAR(60) NULL`, `row_sha256: CHAR(64)`, `search_vector: TSVECTOR` | `PK(id)`, `FK(price_list_id -> price_lists.id ON DELETE CASCADE)`, `FK(vendor_id -> vendors.id ON DELETE CASCADE)`, `IDX_GIN(search_vector)`, `IDX_TRGM(normalized_description gin_trgm_ops)`, `IDX_DIM(vendor_id, diameter_mm, length_m, weight_kg)` | `CHECK (price_cash_ars > 0 AND price_list_ars > 0)`. `row_sha256` evita reprocesar atributos técnicos cuando el código y descripción no cambiaron entre versiones de listas. |
| `product_aliases` | `id: UUID`, `workspace_id: UUID`, `vendor_id: UUID NULL`, `alias_term: VARCHAR(180)`, `canonical_term: VARCHAR(180)`, `target_vendor_product_id: UUID NULL`, `is_active: BOOLEAN DEFAULT TRUE`, `created_at: TIMESTAMPTZ` | `PK(id)`, `FK(workspace_id -> workspaces.id ON DELETE CASCADE)`, `FK(target_vendor_product_id -> vendor_products.id ON DELETE SET NULL)`, `UNIQUE(workspace_id, vendor_id, alias_term)` | Guarda las equivalencias supervisadas por el presupuestador o comprador sin contaminar otros espacios de trabajo. |
| `requisitions` | `id: UUID`, `workspace_id: UUID`, `title: VARCHAR(160)`, `client_name: VARCHAR(140) NULL`, `source_type: VARCHAR(20)` (`'IMAGE'` \| `'TEXT'` \| `'SPREADSHEET'`), `raw_input_text: TEXT NULL`, `status: VARCHAR(30)`, `created_at: TIMESTAMPTZ`, `updated_at: TIMESTAMPTZ` | `PK(id)`, `FK(workspace_id -> workspaces.id ON DELETE CASCADE)`, `IDX(workspace_id, status)` | Representa el pedido o cómputo de materiales a presupuestar y comparar. `CHECK (status IN ('DRAFT_EXTRACTED', 'NEEDS_CLARIFICATION', 'READY_TO_COMPARE', 'COMPARED', 'LOCKED_BUDGET'))`. |
| `requisition_items` | `id: UUID`, `requisition_id: UUID`, `line_order: INTEGER`, `raw_line: TEXT`, `requested_term: VARCHAR(200)`, `quantity: NUMERIC(12,2)`, `requested_unit: VARCHAR(40)`, `diameter_inch: VARCHAR(20) NULL`, `diameter_mm: NUMERIC(8,2) NULL`, `length_m: NUMERIC(8,2) NULL`, `weight_kg: NUMERIC(8,2) NULL`, `material_type: VARCHAR(60) NULL`, `completeness: VARCHAR(40)`, `clarification_prompt: TEXT NULL`, `is_confirmed: BOOLEAN DEFAULT FALSE` | `PK(id)`, `FK(requisition_id -> requisitions.id ON DELETE CASCADE)`, `UNIQUE(requisition_id, line_order)` | `CHECK (quantity > 0)`. `CHECK (completeness IN ('complete', 'missing_critical_attribute', 'user_resolved'))`. |
| `comparison_runs` | `id: UUID`, `requisition_id: UUID`, `workspace_id: UUID`, `payment_modality: VARCHAR(20)` (`'CASH'` \| `'LIST'` \| `'ACOPIO'`), `markup_pct: NUMERIC(5,2) DEFAULT 0.00`, `best_single_vendor_id: UUID NULL`, `best_single_total_ars: NUMERIC(14,2) NULL`, `split_cart_total_ars: NUMERIC(14,2) NULL`, `split_cart_savings_ars: NUMERIC(14,2) NULL`, `comparison_matrix_json: JSONB`, `public_share_token: VARCHAR(128) UNIQUE`, `created_at: TIMESTAMPTZ` | `PK(id)`, `FK(requisition_id -> requisitions.id ON DELETE CASCADE)`, `FK(workspace_id -> workspaces.id ON DELETE CASCADE)`, `UNIQUE(public_share_token)` | Almacena la instantánea (`snapshot`) completa de la comparativa multi-negocio, el cálculo de ahorro por compra dividida y las condiciones de acopio de cada proveedor. |
| `comparison_item_matches` | `id: UUID`, `comparison_run_id: UUID`, `requisition_item_id: UUID`, `vendor_id: UUID`, `vendor_product_id: UUID NULL`, `match_status: VARCHAR(30)` (`'EXACT_MATCH'` \| `'AMBIGUOUS_CANDIDATES'` \| `'OUT_OF_STOCK'` \| `'NOT_CARRIED'`), `unit_price_applied_ars: NUMERIC(14,2) NULL`, `line_subtotal_ars: NUMERIC(14,2) NULL`, `similarity_score: NUMERIC(5,4) NULL`, `is_selected_for_split_cart: BOOLEAN DEFAULT FALSE` | `PK(id)`, `FK(comparison_run_id -> comparison_runs.id ON DELETE CASCADE)`, `FK(requisition_item_id -> requisition_items.id ON DELETE CASCADE)`, `FK(vendor_id -> vendors.id ON DELETE CASCADE)` | Vincula cada ítem del pedido con la oferta específica de cada negocio comparado. Si `match_status = 'NOT_CARRIED'`, el negocio no posee ese artículo con la medida exigida. |

---

### 3.2 Máquinas de Estado y Reglas de Negocio Críticas

| Flujo / Entidad | Estado Origen | Evento Disparador | Condición de Guarda (Invariante) | Estado Destino | Efectos Secundarios |
|---|---|---|---|---|---|
| **Ingesta de Pedido (`Requisition`)** | `NULL` | `POST /api/v1/requisitions/ingest` (Foto manuscrita o texto libre) | Archivo de imagen válido (`<=10MB`) o texto no vacío (`>=3` caracteres). | `DRAFT_EXTRACTED` o `NEEDS_CLARIFICATION` | Extrae renglones con Pydantic V2, convierte pulgadas fraccionarias ($1/2^{\prime\prime}$, $3/4^{\prime\prime}$, $1^{\prime\prime}$, $2^{\prime\prime}$) a milímetros ($12.70$, $19.05$, $25.40$, $50.80\text{ mm}$). Si algún ítem tiene `completeness == 'missing_critical_attribute'`, pasa a `NEEDS_CLARIFICATION`. |
| **Desambiguación Técnica (`RequisitionItem`)** | `NEEDS_CLARIFICATION` | `PATCH /api/v1/requisitions/{id}/items/{item_id}/resolve` | El usuario selecciona el atributo físico faltante (`material_type`, `diameter_mm` o `length_m`) y opcionalmente guarda un alias. | `READY_TO_COMPARE` (cuando `COUNT(items WHERE NOT is_confirmed) == 0`) | Actualiza `completeness = 'user_resolved'` e `is_confirmed = TRUE`. Si `save_alias == TRUE`, inserta/actualiza registro en `product_aliases` para ese `workspace_id`. |
| **Importación de Lista de Negocio (`PriceList`)** | `NULL` | `POST /api/v1/vendors/{vendor_id}/catalogs/import` | Archivo `.xlsx`, `.xls` o `.csv` con columnas mínimas mapeadas (`sku`, `description`, `price_cash_ars`). | `ACTIVE_VERSION` | Calcula `SHA-256(sku + normalized_description)` por fila. Copia atributos dimensionales de la versión previa para hashes idénticos y ejecuta parser dimensional sólo en filas nuevas o modificadas. |
| **Compulsa Multi-Negocio (`ComparisonRun`)** | `READY_TO_COMPARE` | `POST /api/v1/requisitions/{id}/compare` con `vendor_ids: list[UUID]` | `len(vendor_ids) >= 1` y todos los `requisition_items` tienen `is_confirmed == TRUE`. | `COMPARED` | Para cada negocio y cada ítem: aplica **Filtro Dimensional Duro SQL** (`diameter_mm`, `length_m`, `weight_kg`) antes de ordenar por `ts_rank_cd` y `similarity()`. Calcula el mejor negocio único (mayor cobertura + menor precio), la canasta óptima dividida (incluyendo `estimate_delivery_fee_ars`) y el desglose de acopio. |
| **Congelamiento y Emisión (`ComparisonRun`)** | `COMPARED` | `POST /api/v1/comparisons/{run_id}/lock-budget` | Todos los ítems seleccionados en la estrategia elegida (`SINGLE_VENDOR` o `SPLIT_CART`) poseen producto asignado o exclusión explícita. | `LOCKED_BUDGET` | Sella `comparison_matrix_json` como snapshot inmutable, genera token público HMAC y habilita descarga de PDF comparativo o presupuesto final con margen del presupuestador. |

#### Reglas Deterministas de los Motores de Dominio

1. **Tabla de Equivalencias Físicas y Regionales (`unit_normalizer.py`):**
   - **Pulgadas a Milímetros Nominales:** `"1/2\""` $\rightarrow 12.70\text{ mm}$, `"3/4\""` $\rightarrow 19.05\text{ mm}$, `"1\""` $\rightarrow 25.40\text{ mm}$, `"1 1/4\""` $\rightarrow 31.75\text{ mm}$, `"1 1/2\""` $\rightarrow 38.10\text{ mm}$, `"2\""` $\rightarrow 50.80\text{ mm}$, `"4\""` $\rightarrow 110.00\text{ mm}$ (equivalencia sanitaria PVC cloacal estándar).
   - **Jerga de Obra a Atributo Normalizado:** Expresiones como `"hierro del 8"` o `"barra del 8"` se normalizan a `canonical_term = "barra acero aletado"`, `diameter_mm = 8.0`, `length_m = 12.0`. Si el usuario ingresa `"caño de 3/4"` sin especificar material, el normalizador asigna `diameter_mm = 19.05`, `material_type = None`, `completeness = "missing_critical_attribute"` y genera `clarification_prompt = "Especificar material/uso del caño Ø 3/4\" (19.05 mm): ¿PVC cloacal/agua, Polipropileno roscado, Termofusión (agua/gas) o Corrugado eléctrico?"`.
   - **Pesos Estándar de Bolsas:** Si se solicita `"bolsa de cemento"` sin peso explícito, se asume el estándar de $50.0\text{ kg}$ (configurable si el catálogo del comercio registra bolsas de $25.0\text{ kg}$); para adhesivos impermeables o mezclas se validan presentaciones de $25.0\text{ kg}$, $30.0\text{ kg}$ y $40.0\text{ kg}$.

2. **Algoritmo de Comparación Multi-Negocio y Carrito Dividido (`comparison_optimizer.py`):**
   Dado un conjunto de ítems normalizados $I = \{1, \dots, n\}$ con cantidades $q_i$ y un conjunto de negocios seleccionados $V = \{1, \dots, m\}$:
   - **Precio Unitario Efectivo según Modalidad ($P_{i,v}^{\text{mod}}$):**
     - Si `payment_modality == 'CASH'`: $P_{i,v}^{\text{CASH}} = \text{price\_cash\_ars}_{i,v}$.
     - Si `payment_modality == 'LIST'`: $P_{i,v}^{\text{LIST}} = \text{price\_list\_ars}_{i,v}$.
     - Si `payment_modality == 'ACOPIO'`: Si el negocio $v$ admite acopio (`acopio_config_json.enabled == true`), se aplica el precio base de acopio configurado y se calcula el **Anticipo Exigido**:
       $$\text{DownPayment}_v = \text{Total}_v \times \left(\frac{\text{min\_down\_payment\_pct}_v}{100}\right)$$
       junto con la fecha exacta de vencimiento de congelamiento (`created_at + freeze_days`) y la fecha límite de retiro (`created_at + max_withdrawal_days`).
   - **Criterio de Mejor Proveedor Único (`Best Single Vendor`):**
     Se ordenan los negocios $v \in V$ maximizando primero la tasa de cobertura:
     $$\text{Coverage}_v = \frac{|\{i \in I : \text{matched}(i,v)\}|}{|I|}$$
     y minimizando en segundo lugar el costo total con flete:
     $$\text{SingleTotal}_v = \sum_{i \in I} \left(q_i \cdot P_{i,v}^{\text{mod}}\right) + \text{delivery\_fee}_v$$
   - **Criterio de Compra Dividida Óptima (`Optimal Split Cart`):**
     Para cada ítem $i \in I$, se selecciona el negocio $v^*(i) = \arg\min_{v \in V} \left(q_i \cdot P_{i,v}^{\text{mod}}\right)$. El costo total del carrito dividido penalizado por logística es:
     $$\text{SplitTotal} = \sum_{i \in I} q_i \cdot P_{i,v^*(i)}^{\text{mod}} + \sum_{v \in V_{\text{usados}}} \text{delivery\_fee}_v$$
     El sistema recomienda la compra dividida únicamente si $\text{Savings} = \text{BestSingleTotal} - \text{SplitTotal} > 0$ sobre los ítems comparables comunes.

---

### 3.3 Contratos de API e Interfaces de Comunicación

| Método y Ruta | Permisos / Auth | Payload de Entrada (Esquema) | Respuesta Exitosa (2xx) | Errores Deterministas (4xx/5xx) |
|---|---|---|---|---|
| `POST /api/v1/vendors` | Bearer JWT (`BUYER` \| `ESTIMATOR`) | `VendorCreateRequest`: `{name, locality, whatsapp_phone, cash_discount_pct, estimate_delivery_fee_ars, acopio_config}` | `201 Created` -> `VendorResponse` | `422 Unprocessable Entity` si porcentajes `< 0` o `> 100`. |
| `POST /api/v1/vendors/{vendor_id}/catalogs/import` | Bearer JWT | `multipart/form-data`: archivo `.xlsx`/`.csv` + `column_mapping_json` (`sku_col`, `desc_col`, `price_cash_col`, `price_list_col`, `unit_col`, `brand_col`) | `201 Created` -> `CatalogImportSummary`: `{price_list_id, version_number, total_rows, new_or_updated_rows, unchanged_skipped_rows}` | `400 Bad Request` si faltan columnas obligatorias o archivo corrupto; `404 Not Found` si `vendor_id` no pertenece al workspace. |
| `POST /api/v1/requisitions/ingest` | Bearer JWT o Demo Session | `multipart/form-data` o JSON `RequisitionIngestRequest`: `{title, client_name, raw_text, image_file, preset_id}` | `201 Created` -> `RequisitionDetailResponse` con lista de `items` y estado `NEEDS_CLARIFICATION` o `READY_TO_COMPARE` | `400 Bad Request` si no se envía ni imagen ni texto; `413 Payload Too Large` si la imagen supera 10 MB. |
| `PATCH /api/v1/requisitions/{req_id}/items/{item_id}/resolve` | Bearer JWT o Demo Session | `ItemClarificationResolveRequest`: `{diameter_mm, length_m, weight_kg, material_type, confirmed_term, save_as_alias: bool, vendor_id: UUID | null}` | `200 OK` -> `RequisitionDetailResponse` actualizado (cambia estado global a `READY_TO_COMPARE` al resolver el último ítem ambiguo) | `404 Not Found` si el ítem no existe; `409 Conflict` si la medida sigue siendo incompleta. |
| `POST /api/v1/requisitions/{req_id}/compare` | Bearer JWT o Demo Session | `RunComparisonRequest`: `{vendor_ids: list[UUID], payment_modality: 'CASH' | 'LIST' | 'ACOPIO', markup_pct: float, include_delivery_fees: bool}` | `200 OK` -> `ComparisonMatrixResponse`: contiene resumen por negocio, detalle línea por línea, optimización de carrito dividido y simulación de acopio | `400 Bad Request` si la requisición aún tiene ítems con `completeness == 'missing_critical_attribute'`; `422` si `vendor_ids` está vacío. |
| `PATCH /api/v1/comparisons/{run_id}/matches/{match_id}` | Bearer JWT o Demo Session | `ManualVendorMatchOverride`: `{vendor_product_id: UUID, save_vendor_alias: bool}` | `200 OK` -> `ComparisonMatrixResponse` recalculada en tiempo real | `400 Bad Request` si el producto elegido viola una dimensión física explícita sin bandera `force_dimension_override: true`. |
| `GET /api/v1/public/comparisons/{share_token}` | Público (Firma HMAC) | Parámetro de ruta `share_token` y opcional `?format=pdf` | `200 OK` -> JSON del presupuesto/comparativa congelada o stream `application/pdf` membretado | `404 Not Found` o `403 Forbidden` si el token es inválido. |
| `GET /api/v1/public/traction` | Público | Sin parámetros | `200 OK` -> `TractionMetricsResponse`: `{active_real_workspaces, real_vendors_compared, real_budgets_generated, total_lines_processed, median_elaboration_seconds}` | `200 OK` determinista (filtra estrictamente `WHERE workspaces.is_demo = FALSE`). |

---

## 4. GRAFO DE EJECUCIÓN PARA EL ORQUESTADOR DE AGENTES (`TASKS_DAG.md`)

### `TASK-01`: Inicialización de Infraestructura, Configuración Base y Esquema SQLAlchemy 2.0
- **Ola de Ejecución:** `Ola 0` | **Depende de:** `Ninguna`
- **Archivos Objetivo (Escritura):** `docker-compose.yml`, `.env.example`, `backend/pyproject.toml`, `backend/app/core/config.py`, `backend/app/core/database.py`, `backend/app/models/__init__.py`, `backend/app/models/workspace.py`, `backend/app/models/vendor.py`, `backend/app/models/requisition.py`, `backend/app/models/comparison.py`, `backend/alembic/versions/0001_initial_schema.py`
- **Archivos de Contexto (Solo Lectura):** `AGENT_RULES.md`, `CONTRACTS.md`
- **Especificación de Implementación:**
  1. Configurar `docker-compose.yml` con PostgreSQL 16 (ejecutando `CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;` en inicialización), contenedor `backend` y contenedor `frontend`.
  2. Implementar los 10 modelos declarativos en SQLAlchemy 2.0 usando `Mapped[...]` y `mapped_column(...)`, respetando todos los tipos, claves foráneas, índices `GIN` (`search_vector`) y restricciones `CHECK` definidos en la Sección 3.1.
  3. Crear la migración inicial de Alembic `0001_initial_schema.py` con funciones `upgrade()` y `downgrade()` reversibles.
- **Arnés de Verificación (Definition of Done Ejecutable):**
```bash
cd backend && pytest -q --collect-only && python -c "from app.models import Workspace, Vendor, PriceList, VendorProduct, Requisition, ComparisonRun; print('MODELS_OK')"
```

### `TASK-02`: Esquemas Pydantic V2 y Normalizador Determinista de Unidades y Medidas Físicas
- **Ola de Ejecución:** `Ola 1` | **Depende de:** `TASK-01`
- **Archivos Objetivo (Escritura):** `backend/app/schemas/dimensions.py`, `backend/app/schemas/requisition.py`, `backend/app/schemas/vendor.py`, `backend/app/schemas/comparison.py`, `backend/app/services/unit_normalizer.py`, `backend/tests/test_unit_normalizer.py`
- **Archivos de Contexto (Solo Lectura):** `backend/app/models/requisition.py`, `backend/app/models/vendor.py`
- **Especificación de Implementación:**
  1. En `backend/app/schemas/dimensions.py`, definir `PhysicalDimensions(BaseModel)` con campos `diameter_inch: str | None`, `diameter_mm: float | None`, `length_m: float | None`, `weight_kg: float | None`, `material_type: str | None` y `completeness: Literal['complete', 'missing_critical_attribute', 'user_resolved']`.
  2. En `backend/app/services/unit_normalizer.py`, implementar `parse_and_normalize_line(raw_line: str) -> list[NormalizedItemDraft]`:
     - Separar líneas compuestas por conjunciones (ej. `"20 barra del 8 y 4 caño de 3/4"` produce 2 ítems independientes).
     - Convertir fracciones de pulgada ($1/2^{\prime\prime}$, $3/4^{\prime\prime}$, $1^{\prime\prime}$, $1\ 1/2^{\prime\prime}$, $2^{\prime\prime}$) a su equivalente exacto en milímetros ($19.05\text{ mm}$ para $3/4^{\prime\prime}$).
     - Detectar categorías que exigen atributo material obligatorio (`caño`, `tubo`, `codo`, `tee`, `cupla`): si `material_type` no está presente en la línea, marcar `completeness = "missing_critical_attribute"` y poblar `clarification_prompt` con las opciones válidas del rubro.
- **Arnés de Verificación (Definition of Done Ejecutable):**
```bash
cd backend && pytest tests/test_unit_normalizer.py -v
```

### `TASK-03`: Importador Multi-Negocio de Catálogos Excel/CSV con Versionado y Hash SHA-256
- **Ola de Ejecución:** `Ola 1` | **Depende de:** `TASK-01`, `TASK-02`
- **Archivos Objetivo (Escritura):** `backend/app/services/catalog_importer.py`, `backend/tests/test_catalog_importer.py`
- **Archivos de Contexto (Solo Lectura):** `backend/app/models/vendor.py`, `backend/app/services/unit_normalizer.py`
- **Especificación de Implementación:**
  1. Implementar `CatalogImporterService.import_vendor_catalog(db: Session, vendor_id: UUID, file_bytes: bytes, filename: str, mapping: ColumnMappingSchema) -> CatalogImportSummary`.
  2. Soportar archivos `.xlsx`, `.xls` y `.csv`, limpiando símbolos monetarios (`$`, puntos de miles y comas decimales argentinas) y validando que `price_cash_ars > 0`.
  3. Calcular `row_sha256 = hashlib.sha256(f"{sku.strip().upper()}||{normalized_desc}".encode()).hexdigest()` para cada fila.
  4. Consultar la versión activa anterior (`price_lists` de ese `vendor_id`): si un `row_sha256` ya existe en la versión anterior, clonar directamente sus atributos dimensionales (`diameter_mm`, `length_m`, `weight_kg`, `material_type`) sin re-ejecutar el parser técnico; ejecutar la extracción dimensional únicamente sobre filas con hash nuevo o modificado.
- **Arnés de Verificación (Definition of Done Ejecutable):**
```bash
cd backend && pytest tests/test_catalog_importer.py -v
```

### `TASK-04`: Servicio de Ingesta Multimodal (Fotos Manuscritas y Texto) con Fallback Determinista
- **Ola de Ejecución:** `Ola 1` | **Depende de:** `TASK-02`
- **Archivos Objetivo (Escritura):** `backend/app/services/multimodal_extractor.py`
- **Archivos de Contexto (Solo Lectura):** `backend/app/schemas/requisition.py`, `backend/app/services/unit_normalizer.py`
- **Especificación de Implementación:**
  1. Implementar `MultimodalExtractorService.extract_requisition_items(raw_text: str | None, image_bytes: bytes | None, preset_id: str | None) -> list[NormalizedItemDraft]`.
  2. Integrar el llamado a la API multimodal con esquema JSON estricto (`response_schema=RequisitionExtractionBatch`) para transcribir fotografías de listas manuscritas en obra y enriquecer cada ítem pasando el resultado por `unit_normalizer.parse_and_normalize_line`.
  3. Incluir los 3 presets realistas de demostración requeridos para pruebas instantáneas en menos de 60 segundos (Preset 1: Foto de lista manuscrita en obra; Preset 2: Mensaje de WhatsApp con jerga y abreviaturas del NOA; Preset 3: Listado técnico de materiales de construcción).
- **Arnés de Verificación (Definition of Done Ejecutable):**
```bash
cd backend && python -c "from app.services.multimodal_extractor import MultimodalExtractorService; svc = MultimodalExtractorService(); res = svc.extract_from_preset('whatsapp_jerga_noa'); assert len(res) >= 3; print('EXTRACTOR_OK')"
```

### `TASK-05`: Motor de Emparejamiento Físico-Léxico Multi-Catálogo y Memoria de Alias Supervisada
- **Ola de Ejecución:** `Ola 2` | **Depende de:** `TASK-02`, `TASK-03`
- **Archivos Objetivo (Escritura):** `backend/app/services/matching_engine.py`, `backend/tests/test_matching_engine.py`
- **Archivos de Contexto (Solo Lectura):** `backend/app/models/vendor.py`, `backend/app/models/requisition.py`
- **Especificación de Implementación:**
  1. Implementar `MatchingEngineService.match_item_against_vendor(db: Session, workspace_id: UUID, item: RequisitionItem, vendor_id: UUID) -> VendorItemMatchResult`.
  2. **Regla 1 (Bloqueo ante atributo faltante):** Si `item.completeness == 'missing_critical_attribute'`, lanzar `AmbiguousItemCannotBeMatchedError` impidiendo emparejar hasta que el usuario confirme la especificación.
  3. **Regla 2 (Prioridad de Alias Supervisado):** Verificar si existe un alias activo en `product_aliases` para `(workspace_id, vendor_id, item.requested_term)`. Si existe y el producto de destino cumple las dimensiones físicas del ítem, elevarlo al primer lugar marcando `match_origin = 'SUPERVISED_ALIAS'`.
  4. **Regla 3 (Filtro Dimensional Duro SQL):** Construir la consulta SQL sobre `vendor_products` de la lista activa del `vendor_id`:
     - Si `item.diameter_mm IS NOT NULL`: exigir `ABS(vendor_products.diameter_mm - :item_diameter_mm) <= 0.5`.
     - Si `item.length_m IS NOT NULL`: exigir `ABS(vendor_products.length_m - :item_length_m) <= 0.05`.
     - Si `item.weight_kg IS NOT NULL`: exigir `ABS(vendor_products.weight_kg - :item_weight_kg) <= 0.5`.
     - Jamás devolver un `"Caño PVC 110 mm"` cuando se solicita `"Caño PVC 40 mm"`, ni una `"Barra del 10"` cuando se solicita `"Barra del 8"`.
  5. Ordenar los candidatos que superaron el filtro dimensional combinando `ts_rank_cd(search_vector, plainto_tsquery('spanish', :term))` y `similarity(normalized_description, :term)` (`pg_trgm`).
- **Arnés de Verificación (Definition of Done Ejecutable):**
```bash
cd backend && pytest tests/test_matching_engine.py -v
```

### `TASK-06`: Motor Comparador Multi-Negocio, Optimizador de Carrito Dividido y Simulador de Acopio
- **Ola de Ejecución:** `Ola 2` | **Depende de:** `TASK-05`
- **Archivos Objetivo (Escritura):** `backend/app/services/comparison_optimizer.py`, `backend/tests/test_comparison_optimizer.py`
- **Archivos de Contexto (Solo Lectura):** `backend/app/models/comparison.py`, `backend/app/services/matching_engine.py`
- **Especificación de Implementación:**
  1. Implementar `ComparisonOptimizerService.run_multi_vendor_comparison(db: Session, requisition_id: UUID, vendor_ids: list[UUID], payment_modality: str, markup_pct: float, include_delivery_fees: bool) -> ComparisonMatrixResponse`.
  2. Ejecutar `MatchingEngineService.match_item_against_vendor` para cada par `(requisition_item, vendor_id)` y construir la matriz comparativa completa.
  3. Calcular para cada negocio:
     - Cantidad de ítems cotizados con éxito vs. ítems faltantes (`coverage_pct`).
     - Subtotal en Contado/Transferencia, Subtotal en Precio de Lista y Condiciones Estructuradas de Acopio (monto de anticipo requerido para congelar precio, fecha de vencimiento del congelamiento, fecha límite de retiro y horas de preaviso para entrega).
  4. Calcular la **Compra Dividida Óptima (`Optimal Split Cart`)**: seleccionar para cada ítem el negocio con menor costo unitario disponible, sumar los costos de envío (`estimate_delivery_fee_ars`) de los negocios intervinientes y determinar el ahorro neto exacto (`split_cart_savings_ars`) frente al mejor proveedor único.
  5. Aplicar el porcentaje de margen/honorarios (`markup_pct`) cuando el usuario opere con rol `'ESTIMATOR'` (presupuestador profesional que presenta un presupuesto consolidado a su cliente final).
- **Arnés de Verificación (Definition of Done Ejecutable):**
```bash
cd backend && pytest tests/test_comparison_optimizer.py -v
```

### `TASK-07`: Generador de PDF Comparativo / Presupuesto Final y Endpoints REST FastAPI
- **Ola de Ejecución:** `Ola 2` | **Depende de:** `TASK-03`, `TASK-04`, `TASK-06`
- **Archivos Objetivo (Escritura):** `backend/app/services/pdf_generator.py`, `backend/app/api/v1/endpoints/auth.py`, `backend/app/api/v1/endpoints/vendors.py`, `backend/app/api/v1/endpoints/requisitions.py`, `backend/app/api/v1/endpoints/comparisons.py`, `backend/app/api/v1/endpoints/public.py`, `backend/app/api/v1/router.py`, `backend/app/main.py`
- **Archivos de Contexto (Solo Lectura):** `CONTRACTS.md`, `backend/app/services/comparison_optimizer.py`
- **Especificación de Implementación:**
  1. Implementar `PDFGeneratorService` que renderiza dos formatos seleccionables sobre el `snapshot` congelado:
     - **Modo Comparativa de Compra (Para el Comprador/Presupuestador):** Tabla comparativa multi-comercio, desglose de compra en un solo negocio vs. orden de compra dividida por corralón, y cuadro comparativo de cláusulas de Acopio.
     - **Modo Presupuesto al Cliente Final (Para el Presupuestador):** Presupuesto formal numerado con precios finales (incluyendo margen configurado), modalidades Contado, Lista y Acopio, listo para compartir por WhatsApp mediante enlace firmado.
  2. Exponer todos los endpoints definidos en la Sección 3.3 e inicializar en el evento de arranque un dataset semilla con 3 comercios ilustrativos de Jujuy (`Corralón El Pórtico - Demo`, `Ferretería Industrial Cuyaya - Demo`, `Sanitarios y Materiales Palpalá - Demo`) identificados bajo `is_demo = TRUE`.
- **Arnés de Verificación (Definition of Done Ejecutable):**
```bash
cd backend && pytest -v
```

### `TASK-08`: Arquitectura Frontend React + TypeScript, Stores Zustand y Cliente API Tipado
- **Ola de Ejecución:** `Ola 3` | **Depende de:** `TASK-07`
- **Archivos Objetivo (Escritura):** `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/src/types/api.ts`, `frontend/src/services/apiClient.ts`, `frontend/src/store/useWorkspaceStore.ts`, `frontend/src/store/useRequisitionStore.ts`, `frontend/src/store/useComparisonStore.ts`, `frontend/src/components/DemoBanner.tsx`
- **Archivos de Contexto (Solo Lectura):** `backend/app/schemas/requisition.py`, `backend/app/schemas/comparison.py`
- **Especificación de Implementación:**
  1. Sincronizar `frontend/src/types/api.ts` exactamente con los esquemas de respuesta de FastAPI sin utilizar `any`.
  2. Implementar `DemoBanner.tsx` para mostrar de forma prominente la etiqueta `[MODO DEMO DATOS COMERCIALES ILUSTRATIVOS]` cuando `is_demo == true`, permitiendo alternar entre el perfil **Comprador Final** y **Presupuestador Profesional**.
- **Arnés de Verificación (Definition of Done Ejecutable):**
```bash
cd frontend && npm install && npx tsc --noEmit
```

### `TASK-09`: Interfaz de Ingesta, Consola Human-in-the-Loop y Gestor Multi-Catálogo Excel
- **Ola de Ejecución:** `Ola 3` | **Depende de:** `TASK-08`
- **Archivos Objetivo (Escritura):** `frontend/src/components/IngestionDropzone.tsx`, `frontend/src/components/DisambiguationTable.tsx`, `frontend/src/components/VendorCatalogModal.tsx`
- **Archivos de Contexto (Solo Lectura):** `frontend/src/store/useRequisitionStore.ts`, `frontend/src/types/api.ts`
- **Especificación de Implementación:**
  1. En `IngestionDropzone.tsx`, permitir subir una foto de lista manuscrita, pegar un texto de WhatsApp o cargar con un clic cualquiera de las 3 solicitudes realistas precargadas.
  2. En `DisambiguationTable.tsx`, renderizar las líneas con dimensiones completas en **verde** y las líneas con atributos críticos faltantes en **amarillo** (ej. elegir entre barra de acero nervurada $\emptyset 8\text{ mm} \times 12\text{ m}$ o barra lisa $\emptyset 8\text{ mm} \times 6\text{ m}$, o definir el material de un caño de $3/4^{\prime\prime}$), con casilla para guardar el alias supervisado.
  3. En `VendorCatalogModal.tsx`, permitir al usuario agregar un nuevo negocio, mapear las columnas de su planilla Excel/CSV y configurar sus parámetros de flete y reglas de acopio.
- **Arnés de Verificación (Definition of Done Ejecutable):**
```bash
cd frontend && npx tsc --noEmit
```

### `TASK-10`: Matriz Comparativa Multi-Negocio, Optimizador de Carrito Dividido y Vistas Públicas
- **Ola de Ejecución:** `Ola 3` | **Depende de:** `TASK-09`
- **Archivos Objetivo (Escritura):** `frontend/src/components/MultiVendorMatrix.tsx`, `frontend/src/components/SplitCartOptimizerCard.tsx`, `frontend/src/components/AcopioSimulatorPanel.tsx`, `frontend/src/pages/BuilderDashboardPage.tsx`, `frontend/src/pages/PublicBudgetViewPage.tsx`, `frontend/src/pages/TractionEvidencePage.tsx`, `frontend/src/App.tsx`
- **Archivos de Contexto (Solo Lectura):** `frontend/src/store/useComparisonStore.ts`, `frontend/src/components/DisambiguationTable.tsx`
- **Especificación de Implementación:**
  1. En `MultiVendorMatrix.tsx`, presentar las filas del pedido enfrentadas contra las columnas de los negocios seleccionados, destacando en verde el precio más bajo por renglón, alertando sobre faltantes de stock y permitiendo cambiar manualmente el producto emparejado de cualquier comercio en un clic.
  2. En `SplitCartOptimizerCard.tsx`, mostrar la comparativa directa entre **"Comprar todo en el mejor negocio único"** vs. **"Compra dividida optimizada por ítem"**, desglosando cuánto se ahorra en materiales, cuánto suman los fletes y cuál es el ahorro neto real de bolsillo.
  3. En `AcopioSimulatorPanel.tsx`, comparar lado a lado qué negocio ofrece mejores condiciones de **Acopio de Materiales** (anticipo exigido en pesos, días de congelamiento de precio y plazo máximo de retiro).
  4. En `TractionEvidencePage.tsx` (ruta `/traccion`), renderizar las métricas auditables de usuarios y presupuestos reales separadas del entorno de demostración.
- **Arnés de Verificación (Definition of Done Ejecutable):**
```bash
cd frontend && npm run build
```

---

## 5. PROTOCOLO DE PRUEBAS E2E Y CRITERIOS DE ACEPTACIÓN GLOBAL (`VERIFICATION.md`)

| ID Escenario | Flujo de Usuario / Sistema | Precondición (Seed Data) | Acción Ejecutada | Resultado Esperado Verificable |
|---|---|---|---|---|
| `E2E-01` | **Ingesta y Bloqueo Dimensional Anti-Error** | 3 negocios cargados con caños de PVC de $40\text{ mm}$ y $110\text{ mm}$, y barras de acero de $8\text{ mm}$ y $10\text{ mm}$. | El comprador ingresa el pedido `"20 barra del 8 y 4 caño de 3/4"` en `/api/v1/requisitions/ingest`. | El primer ítem se normaliza con `diameter_mm = 8.0`, `length_m = 12.0`, `completeness = 'complete'`. El segundo ítem se normaliza con `diameter_mm = 19.05` ($3/4^{\prime\prime}$), `completeness = 'missing_critical_attribute'` y el sistema **bloquea** la ejecución de la comparativa hasta que el usuario elija el material del caño. |
| `E2E-02` | **No-Sustitución Ciega entre Medidas Físicas** | El Negocio A tiene stock de `"Caño PVC 110 mm x 4 m"` pero no tiene `"Caño PVC 40 mm x 4 m"`. El Negocio B sí tiene `"Caño PVC 40 mm x 4 m"`. | El usuario solicita `"5 caño PVC 40 mm"` y ejecuta la comparativa entre Negocio A y Negocio B. | El motor SQL filtra estrictamente `diameter_mm = 40.0`. Para el Negocio A devuelve `match_status = 'NOT_CARRIED'` (jamás empareja el de $110\text{ mm}$ aunque comparta el $85\%$ de las palabras), y para el Negocio B devuelve `EXACT_MATCH`. |
| `E2E-03` | **Optimización de Compra Dividida vs. Proveedor Único** | El Negocio A vende el Cemento $50\text{ kg}$ a $\$9.500$ y el Hierro $\emptyset 8\text{ mm}$ a $\$11.000$ (Flete $\$15.000$). El Negocio B vende el Cemento $50\text{ kg}$ a $\$10.500$ y el Hierro $\emptyset 8\text{ mm}$ a $\$8.800$ (Flete $\$15.000$). | El comprador cotiza `50 bolsas de cemento` y `40 barras del 8` en modalidad `CASH` con `include_delivery_fees = true`. | Mejor proveedor único: Negocio B ($\$877.000 + \$15.000 = \$892.000$). Carrito dividido óptimo: Cemento en Negocio A ($\$475.000$) + Hierro en Negocio B ($\$352.000$) + 2 fletes ($\$30.000$) = $\$857.000$. El sistema informa un ahorro neto verificable de $\$35.000$ comprando en ambos negocios. |
| `E2E-04` | **Comparación de Reglas de Acopio y Emisión de Snapshot PDF** | El Negocio A exige $100\%$ de anticipo y da $30\text{ días}$ de acopio; el Negocio C exige $70\%$ de anticipo y da $90\text{ días}$ de acopio con preaviso de $48\text{ hs}$. | El presupuestador selecciona la modalidad `ACOPIO`, agrega un margen profesional del $10\%$ y congela el presupuesto (`lock-budget`). | Se genera un `public_share_token` válido y un PDF descargable que exhibe el anticipo exacto en pesos para cada negocio, la fecha límite de retiro y un `snapshot_json` inmutable que no se altera si luego se importa una nueva lista Excel en `price_lists`. |
| `E2E-05` | **Aislamiento de Métricas Reales en `/traccion`** | Se ejecutan 10 comparativas en la cuenta `[MODO DEMO]` (`is_demo = TRUE`) y 2 comparativas en un espacio de trabajo real (`is_demo = FALSE`). | Consulta pública a `GET /api/v1/public/traction`. | La respuesta contabiliza únicamente las `2` comparativas del espacio de trabajo real, garantizando cero contaminación de métricas de demostración. |