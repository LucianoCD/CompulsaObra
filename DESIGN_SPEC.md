# Especificación Técnica de Diseño UI/UX (`DESIGN_SPEC.md`) — CompulsaObra

* **Versión del Documento:** `2.0.0` (Arquetipo *Estudio Constructivo Cálido y Claridad Guiada*)
* **Sistema Objetivo:** CompulsaObra (`frontend/` — React 18.3, TypeScript 5.4, Tailwind CSS v3.4, Zustand 4.5, Lucide React)
* **Ámbito Geográfico y Operativo:** San Salvador de Jujuy, Palpalá, Perico y El Carmen (NOA, Argentina)
* **Marco Normativo:** ISO/IEC 25010:2023 (SQuaRE — Calidad en Uso y Usabilidad), 10 Heurísticas de Usabilidad de Jakob Nielsen y WCAG 2.2 Nivel AA

> **ADVERTENCIA CRÍTICA DE USABILIDAD Y ACCESIBILIDAD (A11y):**
> La transición hacia una interfaz más amigable y de menor carga cognitiva **prohíbe explícitamente** adoptar simplificaciones de tipo comercio electrónico B2C (ocultar precios unitarios, suprimir medidas físicas como `Ø mm`, `kg` o `m`, o reemplazar etiquetas textuales por indicadores exclusivos de color), ya que ello vulneraría **WCAG 1.4.1 (Uso del color)**, **Nielsen #6 (Reconocimiento antes que recuerdo)** y **ISO/IEC 25010 (Operabilidad y Protección contra errores)**.
>
> Asimismo, toda implementación derivada de esta especificación **debe corregir de inmediato** seis vulneraciones críticas detectadas en el código fuente actual:
>
> 1. **Destrucción de estado en navegación (`App.tsx`, `DemoBanner.tsx`, `TractionEvidencePage.tsx`):** Los enlaces nativos `<a href="/">` y `<a href="/traccion">` provocan recargas completas que borran compulsas en curso de Zustand y reinician el tema a `light` (viola **Nielsen #3 y #5**). Debe implementarse enrutamiento SPA mediante `History API` (`pushState` / `popstate`) con guardia `beforeunload` y persistencia de tema en `localStorage`.
> 2. **Pérdida silenciosa de datos del comitente (`IngestionDropzone.tsx` / `useRequisitionStore.ts`):** El campo `clientName` (`#req-client`) se captura en estado local pero se descarta al invocar `ingestText`, omitiendo `client_name` en la API y en los presupuestos emitidos con HMAC-SHA256 (viola **ISO/IEC 25010 *User Error Protection***).
> 3. **Bloqueo sin salida en ambigüedad de diámetro y fallo de foco HITL (`DisambiguationTable.tsx`):** Actualmente solo se ofrecen píldoras de `material_type`, dejando irresolubles los ítems marcados como `missing_critical_attribute` por falta de diámetro (`diameter_mm === null`). Además, `firstAmbiguousButtonRef` evalúa `index === 0` sobre la lista total de ítems en lugar del primer ítem pendiente (viola **WCAG 2.4.3** y **Nielsen #9**).
> 4. **Clases CSS inexistentes en Tailwind v3.4 (`DisambiguationTable.tsx`, `BuilderDashboardPage.tsx`, `VendorCatalogModal.tsx`, `TractionEvidencePage.tsx`):** `bg-semantic-dangerBg` y `text-semantic-dangerText` no están definidos en `tailwind.config.js` (ocultan alertas de error); `lg:top-18` anula el posicionamiento `sticky` del panel financiero derecho; `shadow-xs` y `backdrop:backdrop-blur-xs` no existen en Tailwind v3.4.
> 5. **Controles de formulario sin vinculación programática (`VendorCatalogModal.tsx`):** Doce etiquetas `<label>` carecen de atributo `htmlFor` o anidamiento de `<input>`, y el selector de archivos nativo incumple el tamaño táctil mínimo (viola **WCAG 1.3.1, 2.5.8 y 4.1.2**).
> 6. **Fallo silencioso y animación sin control de movimiento (`TractionEvidencePage.tsx`, `DisambiguationTable.tsx`):** El bloque `catch` en `/traccion` deja la pantalla vacía sin mensaje ni reintento (**Nielsen #1 y #9**), y `animate-pulse` ignora `prefers-reduced-motion` (**WCAG 2.3.3**).

---

## 1. Análisis de Usabilidad (Nielsen & SQuaRE)

### 1.1 Evaluación del Cambio de Arquetipo Visual

El sistema original operaba bajo un arquetipo puramente contable-industrial (*Industrial Utilitarian & Technical Computation Ledger*), diseñado desde la perspectiva del desarrollador y del calculista, pero generador de **carga cognitiva extrínseca** para el contratista o comprador de obra que necesita cotizar una lista de WhatsApp en menos de 60 segundos.

El nuevo arquetipo **Estudio Constructivo Cálido y Claridad Guiada (*Warm Architectural Studio & Guided Clarity*)** equilibra la calidez visual y la divulgación progresiva con el rigor metrológico y financiero exigido por la construcción en el NOA:

| Dimensión Normativa (Nielsen / SQuaRE / WCAG) | Estado en el Frontend Actual | Solución en el Arquetipo *Estudio Constructivo Cálido* |
| :--- | :--- | :--- |
| **Nielsen #1: Visibilidad del estado del sistema** / *SQuaRE: Inteligibilidad* | Cinta superior distingue Modo Demo vs Espacio Real, pero cambiar corralones tras compulsar no avisa desactualización de matriz y `/traccion` falla en blanco. | Stepper global de 3 hitos claros, detector de matriz desactualizada (`isMatrixStale`) con acción *"Actualizar precios"* y estado de error recuperable en `/traccion`. |
| **Nielsen #2: Relación entre el sistema y el mundo real** / *SQuaRE: Aprendizabilidad* | Encabezados exponen jerga de auditoría de software (`HITL`, `SHA-256`, `HMAC-SHA256`, `Split Cart`) y rutas crudas (`/traccion`) en la navegación. | Lenguaje natural del obrador (*"1. Cargar lista"*, *"2. Confirmar medidas"*, *"3. Comparar precios"*, *"Compra combinada más barata"*), relegando hashes criptográficos a insignias de verificación auditables. |
| **Nielsen #3 y #5: Control, libertad y prevención de errores** / *SQuaRE: Protección contra errores* | Navegación `<a href>` destruye el estado en Zustand; `clientName` se pierde al ingestar; no hay edición rápida de cantidades en Paso 2. | Enrutamiento SPA sin recarga, guardia `beforeunload` si hay compulsas sin congelar, propagación completa de `client_name` y edición inline de cantidad/unidad. |
| **Nielsen #4 y #8: Consistencia y diseño minimalista** / *SQuaRE: Estética* | Cinco módulos compiten simultáneamente en pantalla; Paso 1 queda expandido tras ingestar; Acopio siempre desplegado; selector de archivos inconsistente. | Divulgación progresiva mediante acordeón (Paso 1 colapsa a `60px` tras extraer; Acopio colapsado salvo en modalidad `ACOPIO`) y componente unificado de carga de archivos (`44px`). |
| **Nielsen #6 y #7: Reconocimiento y flexibilidad de uso** / *SQuaRE: Operabilidad* | `lg:top-18` rompe `sticky` del panel derecho; la matriz carece de filtros rápidos y el cambio de rol `ESTIMATOR` / `BUYER` apenas modifica un subtítulo. | Rail derecho adherido (`lg:top-[120px]`), columna de materiales fijada (`sticky left-0`), filtros de matriz y adaptación funcional del rol `BUYER` (ocultando márgenes de honorarios). |
| **WCAG 2.2 Nivel AA (`1.3.1`, `1.4.3`, `2.3.3`, `2.4.3`, `2.5.8`)** | Tokens `danger` rotos; foco HITL apunta a `index === 0`; 12 `<label>` sin `htmlFor`; tipografía de `10px–11px` en tablas. | Piso tipográfico de `13px` en tablas y formularios, radios táctiles de `8px–12px`, foco determinista al primer ítem pendiente, `id`/`htmlFor` completos y `motion-safe:animate-pulse`. |

---

## 2. Estructura y Layout (Low-Fidelity)

### 2.1 Sistema de Grillas, Densidad y Breakpoints

* **Desktop (`>= 1280px`):** Grilla de **12 columnas** | `max-width: 1440px` (optimizado para portátiles de `1366×768px` y `1440×900px`) | `gutter: 24px` (`gap-6`) | `margin: 24px` (`px-6`). Distribución asimétrica de **8 columnas** (flujo técnico guiado) + **4 columnas** (panel financiero `sticky`).
* **Tablet (`768px - 1279px`):** Grilla de **8 columnas** | `gutter: 16px` (`gap-4`) | `margin: 20px` (`px-5`). Flujo vertical único donde el panel de decisión financiero se posiciona inmediatamente debajo de la matriz comparativa.
* **Mobile (`< 768px`):** Grilla de **4 columnas** | `gutter: 12px` (`gap-3`) | `margin: 16px` (`px-4`). Controles táctiles de altura mínima `42px–44px`, tablas con desplazamiento horizontal contenido (`overflow-x-auto`) y primera columna fijada (`sticky left-0`).

### 2.2 Arquitectura Espacial y Orden de Tabulación (`Tab Order`)

````text
+---------------------------------------------------------------------------------------------------+
| <header role="banner"> (h: 60px, sticky top-0, z-40, bg-surface-elevated, border-b hairline)      |
| [1] CompulsaObra (NOA)   | <nav>: [2] Presupuestar | [3] Corralones | [4] Impacto | [5] Tema | [6] Cuenta |
+---------------------------------------------------------------------------------------------------+
| <aside aria-label="Modo de trabajo"> (h: 44px, sticky top-[60px], z-40)                           |
| Píldora: (i) Modo Exploración con 3 corralones de Jujuy | [7] Vista: (Presupuestador | Comprador) | [8] Crear cuenta |
+---------------------------------------------------------------------------------------------------+
| <main id="main-workspace"> (max-w: 1440px, px-6, py-6, grid-cols-12, gap-6)                       |
|                                                                                                   |
|  [9] PROGRESO (12 cols, h: 48px):  (✓) 1. Cargar lista  --->  (!) 2. Confirmar medidas  --->  (3) 3. Comparar |
|  [10] CORRALONES (12 cols): [✓ El Pórtico · Jujuy]  [✓ Cuyaya · Jujuy]  [✓ Palpalá]  [+ Agregar]  |
|       (Si selectedVendorIds difiere de currentMatrix -> Banner info: "Cambios detectados [Actualizar]") |
|                                                                                                   |
|  +---------------------------------------------------------------+ +----------------------------+ |
|  | COLUMNA DE TRABAJO (lg:col-span-8, space-y-6)                 | | PANEL DE DECISIÓN          | |
|  |                                                               | | (lg:col-span-4, z-30)      | |
|  | +-----------------------------------------------------------+ | | sticky top-[120px]         | |
|  | | [11] PASO 1: Pedido "Casa Los Perales" · Comitente: Pérez | | | +------------------------+ | |
|  | |      5 materiales detectados            [Editar lista]     | | | | [14] RESUMEN DE COMPRA | | |
|  | +-----------------------------------------------------------+ | | | Ahorro estimado:       | | |
|  |                                                               | | | | $ 35.000 (Compra mixta)| | |
|  | +-----------------------------------------------------------+ | | |                        | | |
|  | | [12] PASO 2: Confirmación de Medidas (1 ítem por definir) | | | | [Compra Mixta][1 Local]| | |
|  | | # | Material solicitado | Cantidad | Medida     | Estado   | | | | [Contado][Lista][Acopio]| | |
|  | | 1 | Barra acero aletado | [20] BAR | Ø 8mm×12m  | Listo    | | | | [x] Incluir fletes     | | |
|  | | 2 | Caño de 3/4"        | [ 4] UN  | Ø 19.05mm  | Definir  | | | |                        | | |
|  | |   +-> ¿De qué material es este caño?                       | | | | Total: $ 857.000       | | |
|  | |       [PVC] [Termofusión] [Polipropileno] [Corrugado]      | | | | [Confirmar Presupuesto]| | |
|  | |                                     [Comparar Precios ->] | | | +------------------------+ | |
|  | +-----------------------------------------------------------+ | |                            | |
|  |                                                               | | +------------------------+ | |
|  | +-----------------------------------------------------------+ | | | [15] Condiciones de    | | |
|  | | [13] PASO 3: Comparativa por Corralón  [Filtros: Todos]   | | | | Acopio (3 locales) [v] | | |
|  | | Material (Sticky)  | El Pórtico    | Cuyaya     | Palpalá  | | | +------------------------+ | |
|  | | Cemento 50kg (x50) | $ 9.500 Mejor | $ 10.500   | $ 10.200 | | |                            | |
|  | | Caño PVC 40mm (x5) | $ 6.200       | No trabaja | $ 5.900* | | |                            | |
|  | +-----------------------------------------------------------+ | |                            | |
|  +---------------------------------------------------------------+ +----------------------------+ |
+---------------------------------------------------------------------------------------------------+
| <footer role="contentinfo"> (border-t hairline · ISO/IEC 25010:2023 · WCAG 2.2 AA · Cero Sustitución Ciega) |
+---------------------------------------------------------------------------------------------------+
````

### 2.3 Jerarquía de Capas (`z-index`)

* `z-10`: Columna inicial adherida (`sticky left-0`) de la matriz comparativa.
* `z-20`: Encabezados de columnas de corralones (`sticky top-0`) y celda esquina superior izquierda de la matriz.
* `z-30`: Panel de decisión financiero derecho (`lg:sticky lg:top-[120px]`).
* `z-40`: Barra global de navegación (`h: 60px`) y cinta contextual de modo de trabajo (`h: 44px`).
* `z-50`: Diálogos modales (`<dialog>`) y notificaciones *toast*.
* `z-100`: Enlace de salto accesible (`.skip-link`).

---

## 3. Tokens de Diseño (Hi-Fidelity)

### 3.1 Definición Formal W3C DTCG (`$version: "2025.10"`)

````json
{
  "$version": "2025.10",
  "color": {
    "surface": {
      "canvas": {
        "$type": "color",
        "$value": {
          "light": { "hex": "#F7F4EE", "oklch": "oklch(0.968 0.008 82)" },
          "dark": { "hex": "#121316", "oklch": "oklch(0.186 0.006 255)" }
        }
      },
      "elevated": {
        "$type": "color",
        "$value": {
          "light": { "hex": "#FFFFFF", "oklch": "oklch(1.000 0.000 0)" },
          "dark": { "hex": "#1A1C20", "oklch": "oklch(0.224 0.008 255)" }
        }
      },
      "subtle": {
        "$type": "color",
        "$value": {
          "light": { "hex": "#EFECE4", "oklch": "oklch(0.942 0.011 80)" },
          "dark": { "hex": "#23262C", "oklch": "oklch(0.268 0.011 255)" }
        }
      },
      "borderHairline": {
        "$type": "color",
        "$value": {
          "light": { "hex": "#DED8CC", "oklch": "oklch(0.882 0.015 80)" },
          "dark": { "hex": "#2F333C", "oklch": "oklch(0.326 0.014 255)" }
        }
      },
      "borderStrong": {
        "$type": "color",
        "$value": {
          "light": { "hex": "#8C8478", "oklch": "oklch(0.618 0.018 76)" },
          "dark": { "hex": "#646B78", "oklch": "oklch(0.525 0.018 255)" }
        }
      }
    },
    "text": {
      "primary": {
        "$type": "color",
        "$value": {
          "light": { "hex": "#1C1917", "oklch": "oklch(0.215 0.006 60)" },
          "dark": { "hex": "#F5F4F0", "oklch": "oklch(0.966 0.004 85)" }
        }
      },
      "secondary": {
        "$type": "color",
        "$value": {
          "light": { "hex": "#44403C", "oklch": "oklch(0.372 0.009 65)" },
          "dark": { "hex": "#C2C6CE", "oklch": "oklch(0.822 0.012 258)" }
        }
      },
      "muted": {
        "$type": "color",
        "$value": {
          "light": { "hex": "#57534E", "oklch": "oklch(0.445 0.009 68)" },
          "dark": { "hex": "#949BA6", "oklch": "oklch(0.688 0.018 256)" }
        }
      }
    },
    "action": {
      "primary": {
        "$type": "color",
        "$value": {
          "light": { "hex": "#A83511", "oklch": "oklch(0.492 0.162 34)" },
          "dark": { "hex": "#E8683A", "oklch": "oklch(0.668 0.172 38)" }
        }
      },
      "primaryHover": {
        "$type": "color",
        "$value": {
          "light": { "hex": "#8C2B0D", "oklch": "oklch(0.425 0.145 33)" },
          "dark": { "hex": "#F27D52", "oklch": "oklch(0.718 0.168 39)" }
        }
      },
      "focusRing": {
        "$type": "color",
        "$value": {
          "light": { "hex": "#1D4ED8", "oklch": "oklch(0.488 0.215 264)" },
          "dark": { "hex": "#60A5FA", "oklch": "oklch(0.718 0.145 254)" }
        }
      }
    },
    "semantic": {
      "winnerBg": { "$type": "color", "$value": { "light": "#ECFDF5", "dark": "#083327" } },
      "winnerText": { "$type": "color", "$value": { "light": "#065F46", "dark": "#6EE7B7" } },
      "hitlBg": { "$type": "color", "$value": { "light": "#FEF9EC", "dark": "#362408" } },
      "hitlBorder": { "$type": "color", "$value": { "light": "#D97706", "dark": "#F59E0B" } },
      "hitlText": { "$type": "color", "$value": { "light": "#78350F", "dark": "#FDE68A" } },
      "dangerBg": { "$type": "color", "$value": { "light": "#FEF2F2", "dark": "#3B1619" } },
      "dangerBorder": { "$type": "color", "$value": { "light": "#DC2626", "dark": "#F87171" } },
      "dangerText": { "$type": "color", "$value": { "light": "#991B1B", "dark": "#FECACA" } },
      "infoBg": { "$type": "color", "$value": { "light": "#EFF6FF", "dark": "#172554" } },
      "infoText": { "$type": "color", "$value": { "light": "#1E40AF", "dark": "#BFDBFE" } }
    }
  },
  "typography": {
    "fontFamily": {
      "display": { "$type": "fontFamily", "$value": ["Plus Jakarta Sans", "system-ui", "sans-serif"] },
      "sans": { "$type": "fontFamily", "$value": ["Public Sans", "system-ui", "sans-serif"] },
      "mono": { "$type": "fontFamily", "$value": ["JetBrains Mono", "monospace"] }
    },
    "numericPolicy": { "$type": "string", "$value": "tabular-nums slashed-zero" }
  },
  "space": {
    "baseUnit": { "$type": "dimension", "$value": "4px" }
  },
  "radius": {
    "control": { "$type": "dimension", "$value": "8px" },
    "container": { "$type": "dimension", "$value": "12px" },
    "pill": { "$type": "dimension", "$value": "9999px" }
  },
  "elevation": {
    "card": {
      "$type": "shadow",
      "$value": {
        "light": "0 2px 8px -2px rgba(28, 25, 23, 0.06)",
        "dark": "0 2px 8px -2px rgba(0, 0, 0, 0.35)"
      }
    },
    "modal": {
      "$type": "shadow",
      "$value": {
        "light": "0 20px 25px -5px rgba(28, 25, 23, 0.18)",
        "dark": "0 20px 25px -5px rgba(0, 0, 0, 0.55)"
      }
    }
  },
  "motion": {
    "easingOutExpo": { "$type": "cubicBezier", "$value": [0.22, 1, 0.36, 1] },
    "durationFast": { "$type": "duration", "$value": "160ms" }
  }
}
````

### 3.2 Verificación de Contraste WCAG 2.2 AA/AAA

| Par Semántico | Tema Claro (Texto / Fondo) | Ratio Claro | Tema Oscuro (Texto / Fondo) | Ratio Oscuro | Nivel |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `content.primary` / `surface.elevated` | `#1C1917` / `#FFFFFF` | `17.4:1` | `#F5F4F0` / `#1A1C20` | `16.2:1` | **AAA** |
| `content.secondary` / `surface.elevated` | `#44403C` / `#FFFFFF` | `10.1:1` | `#C2C6CE` / `#1A1C20` | `10.3:1` | **AAA** |
| `content.muted` / `surface.subtle` | `#57534E` / `#EFECE4` | `6.1:1` | `#949BA6` / `#23262C` | `5.6:1` | **AA** |
| Texto CTA / `action.primary` | `#FFFFFF` / `#A83511` | `5.9:1` | `#121316` / `#E8683A` | `6.3:1` | **AA** |
| `semantic.winnerText` / `semantic.winnerBg` | `#065F46` / `#ECFDF5` | `7.6:1` | `#6EE7B7` / `#083327` | `9.4:1` | **AAA** |
| `semantic.hitlText` / `semantic.hitlBg` | `#78350F` / `#FEF9EC` | `8.3:1` | `#FDE68A` / `#362408` | `10.1:1` | **AAA** |
| `semantic.dangerText` / `semantic.dangerBg` | `#991B1B` / `#FEF2F2` | `7.9:1` | `#FECACA` / `#3B1619` | `9.6:1` | **AAA** |
| `semantic.infoText` / `semantic.infoBg` | `#1E40AF` / `#EFF6FF` | `8.5:1` | `#BFDBFE` / `#172554` | `10.4:1` | **AAA** |

### 3.3 Escala Tipográfica y Metrología Numérica

| Rol Tipográfico | Familia | Tamaño / Interlineado | Peso | Regla de Uso |
| :--- | :--- | :--- | :--- | :--- |
| `Page Title H1` | `Plus Jakarta Sans` | `22px` (`1.375rem`) / `1.25` | `800` | Tracking `-0.02em`, `text-wrap: balance`. |
| `Section Title H2` | `Plus Jakarta Sans` | `16px` (`1rem`) / `1.35` | `700` | Tracking `-0.01em`, encabezados de tarjeta y paso. |
| `Financial KPI` | `JetBrains Mono` | `24px` (`1.5rem`) / `1.2` | `700` | `tabular-nums slashed-zero` para ahorro neto y total final. |
| `Body & Description` | `Public Sans` | `14px` (`0.875rem`) / `1.5` | `400 / 600` | Descripciones de materiales, prompts HITL y textos guía. |
| `Table & Control` | `Public Sans` | `13px` (`0.8125rem`) / `1.45` | `500 / 600` | Piso mínimo en `<th>`, `<td>`, `<label>`, `<input>` y botones. |
| `Numeric Cell & SKU` | `JetBrains Mono` | `13px` (`0.8125rem`) / `1.4` | `500 / 700` | `tabular-nums slashed-zero` en precios, diámetros (`Ø mm`), pesos (`kg`) y SKUs. |
| `Status Pill` | `Public Sans` | `12px` (`0.75rem`) / `1.2` | `600` | Etiquetas de estado en celdas y cabecera (`rounded-full`). |

### 3.4 Matriz Completa de Estados Interactivos (8 Estados)

| Componente | Default | Hover | Focus-Visible | Active | Disabled / Locked | Loading / Skeleton | Empty / Zero-Data | Error / Invalid |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Botón Primario** | `#A83511`, texto `#FFFFFF`, `h: 44px`, `rounded-lg`. | `#8C2B0D`, elevación sutil. | Anillo `2px solid #1D4ED8`, `offset: 2px`. | Escala `0.99`, `#732209`. | `opacity-55 cursor-not-allowed` (mantiene foco si `aria-disabled="true"`). | Spinner `16px` + etiqueta de acción en curso. | N/A | N/A |
| **Píldora HITL** | `#FFFFFF`, borde `1px #DED8CC`, `h: 38px`, `rounded-lg`. | `#FEF9EC`, borde `#D97706`, texto `#78350F`. | Anillo `2px solid #1D4ED8`, `offset: 2px`. | `#FDE68A`, dispara `resolveItem`. | Deshabilitada durante envío de aclaración. | Spinner inline en píldora pulsada. | N/A | Banner `semantic-dangerBg` debajo de la tabla. |
| **Chip Corralón (`aria-pressed`)** | `true`: `#A83511/10`, borde `#A83511/40`. `false`: `#EFECE4`. | Borde `#8C8478`. | Anillo `2px solid #1D4ED8`, `offset: 2px`. | Alterna selección y dispara aviso si hay matriz previa. | Icono candado si `is_locked === true`. | Chips skeleton durante `loadVendors`. | CTA directo `+ Registrar Nuevo Corralón`. | Banner si `selectedVendorIds.length === 0`. |
| **Celda de Matriz** | `#FFFFFF`; si `is_best_price`, `#ECFDF5` + borde izq. `3px #059669`. | Borde `#8C8478` + botón editar visible. | Anillo interno `2px` protegido por `scroll-padding`. | Abre modal de sustitución manual. | Solo lectura con icono candado si `is_locked`. | 4 filas skeleton de altura `52px`. | Mensaje guía antes de ejecutar compulsa. | Modal `422 DIMENSION_MISMATCH` con justificación obligatoria. |
| **Input / Select** | `#EFECE4`, borde `1px #DED8CC`, `h: 40px`, `rounded-lg`. | Borde `#8C8478`. | `#FFFFFF`, borde `#1D4ED8`, anillo `2px`. | Mantiene focus. | `#EFECE4`, texto `#57534E`. | N/A | Placeholder claro con ejemplo del NOA. | Borde `#DC2626`, `aria-invalid="true"` + texto error. |

---

## 4. Especificaciones de Componentes y Handoff

### 4.1 Decisiones de Arquitectura y Economía de Dependencias

1. **Cero dependencias UI externas innecesarias:** Conservar el stack actual (`React 18.3`, `TypeScript 5.4`, `Tailwind CSS v3.4`, `Zustand 4.5`, `Lucide React`). No instalar `react-router-dom`, `@radix-ui/*` ni `sonner`.
2. **Enrutamiento SPA Nativo (`History API`):** Implementar `<AppLink>` y un hook de ruta en `App.tsx` basados en `window.history.pushState` y `popstate`, preservando el estado en memoria de `useRequisitionStore` y `useComparisonStore`, persistiendo `compulsa_theme` en `localStorage` y registrando `beforeunload` cuando `currentRequisition !== null && !currentMatrix?.is_locked`.
3. **Purga estricta de utilidades Tailwind v3.4:** Prohibido usar `top-18`, `shadow-xs`, `backdrop-blur-xs` o colores literales Hex en archivos `.tsx`. Registrar `dangerBg`, `dangerBorder`, `dangerText`, `infoBg` e `infoText` en `tailwind.config.js` e `index.css`.
4. **Invariantes de Compatibilidad E2E (`frontend/e2e/compulsa-flow.spec.ts`):** Mantener intactos los roles y textos accesibles asertados por Playwright (`Acceder`, `Manuscrito de Obra (Guardia HITL)`, `PVC Cloacal / Agua`, `Ejecutar Compulsa Multi-Corralón`, `Congelar Presupuesto Definitivo (Lock-Budget)`, `PDF Cliente`, `+ Registrar Nuevo Corralón`).

### 4.2 Contratos Detallados por Módulo

| Módulo / Archivo | Responsabilidad Funcional y Mejoras de UX | Contratos ARIA, Teclado y Manejo de Errores |
| :--- | :--- | :--- |
| **`App.tsx` & `DemoBanner.tsx`** | Cabecera global (`h: 60px`) + cinta contextual (`h: 44px`). Renderiza cabecera minimalista (marca, tema, retorno) en `/p/:token` y `/traccion`. En rol `BUYER`, oculta `markup_pct` en el panel financiero y prioriza el ahorro neto de bolsillo. | `role="radiogroup"` en selector `Presupuestador` / `Comprador` con navegación por flechas izquierda/derecha; sincronización inicial de `data-theme` antes del montaje. |
| **`IngestionDropzone.tsx` & `useRequisitionStore.ts`** | Acordeón colapsable: tras recibir `currentRequisition`, se contrae a una barra resumen de `60px` mostrando título, `client_name` y conteo de ítems con botón *"Editar lista"*. Propaga `client_name` en `ingestText` e `ingestFile`. | `role="tablist"` con `aria-controls` y `role="tabpanel"`; atajo `Ctrl/Cmd + Enter` en `<textarea>`; selector de archivos mediante `<input className="sr-only">` + `<label>` de `44px` de altura. |
| **`DisambiguationTable.tsx`** | Edición inline de `quantity` (`min="0.01"`, `tabular-nums`) y `requested_unit`. Si `completeness === 'missing_critical_attribute'`, muestra píldoras de `material_type` cuando falte material y selector de diámetro (`1/2"`, `3/4"`, `1"`, `40 mm`, `110 mm`) cuando `diameter_mm === null`. | `firstAmbiguousButtonRef` asignado al primer ítem con `completeness === 'missing_critical_attribute'` (no `index === 0`); `aria-live="polite"` en contador; `motion-safe:animate-pulse` y tokens `semantic-dangerBg` / `semantic-dangerText`. |
| **`MultiVendorMatrix.tsx`** | Barra de filtros rápidos (`Todos`, `Mejor precio`, `Sin stock / No trabaja`), columna 1 `sticky left-0 z-10`, píldora `bg-semantic-infoBg` para conversiones de empaque (`conversion_note` / `commercial_qty`) e indicador auditado tras override manual. | `.matrix-scroll-container` con `scroll-padding-top: 96px` y `scroll-padding-inline-start: 260px`; modal de sustitución exige `force_dimension_override` y `override_reason` (`minLength: 10`) ante `422 DIMENSION_MISMATCH`. |
| **`SplitCartOptimizerCard.tsx` & `AcopioSimulatorPanel.tsx`** | Rail derecho `lg:col-span-4 lg:sticky lg:top-[120px] max-h-[calc(100vh-136px)] overflow-y-auto z-30`. `AcopioSimulatorPanel` colapsado por defecto salvo cuando `paymentModality === 'ACOPIO'`. Descarga PDF vía `fetch` + `Blob`. | Si `fulfillment_status === 'partial'`, exige marcar checkbox *"Acepto emitir presupuesto parcial"* (`accept_partial: true`) antes de habilitar `Lock-Budget`; confirma copiado de `/p/:token` mediante `aria-live="polite"`. |
| **`VendorCatalogModal.tsx`** | `<dialog>` nativo (`rounded-xl`, `backdrop:backdrop-blur-sm`). Auto-selecciona `+ Registrar Nuevo Corralón` si `vendors.length === 0`. Incluye `max_withdrawal_days` y `min_notice_hours` en acopio y sección desplegable para columnas opcionales (`unidad`, `marca`, `categoria`). | Vinculación `id` / `htmlFor` en los 12 pares de formulario; disparador de archivo unificado de `44px` con validación previa de tamaño máximo (`12 MB`); cierre con `Escape` y retorno de foco. |
| **`PublicBudgetViewPage.tsx` & `TractionEvidencePage.tsx`** | Cabecera minimalista compartida con cambio de tema. `/traccion` presenta estado cero explicativo cuando `active_real_workspaces === 0` y tarjeta de error con botón *"Reintentar"* ante fallos HTTP. | `/p/:token` exhibe badge `Snapshot Inmutable HMAC-SHA256 Verificado`, pantalla dedicada ante HTTP `403` y prohíbe renderizar nombres de corralones, SKUs o márgenes. |

### 4.3 Reglas de Configuración en Tailwind CSS v3.4 (`tailwind.config.js` e `index.css`)

1. **Variables CSS obligatorias en `index.css` (`:root` y `[data-theme="dark"]`):** Registrar `--danger-bg`, `--danger-border`, `--danger-text`, `--info-bg` e `--info-text` junto a las superficies cálidas `--surface-canvas`, `--surface-elevated` y `--surface-subtle` definidas en la Sección 3.1.
2. **Tokens semánticos en `tailwind.config.js`:** Mapear en `theme.extend.colors.semantic` las claves `dangerBg`, `dangerBorder`, `dangerText`, `infoBg` e `infoText`; actualizar `theme.extend.borderRadius` a `control: '8px'` y `container: '12px'`.
3. **Utilidades de movimiento y lectura numérica:** Mantener `.tabular-nums { font-variant-numeric: tabular-nums slashed-zero; font-family: var(--font-mono); }` y `.bg-not-carried-pattern` para cumplimiento estricto de WCAG 1.4.1.

### 4.4 Criterios de Aceptación para Verificación Automatizada

1. **Integridad SPA y Persistencia de Datos:** Cambiar entre `/`, `/traccion` y `/` preserva `data-theme` y `currentRequisition`; ingestar con `client_name` refleja el nombre del comitente en la tarjeta resumen, en el PDF emitido y en `/p/:token`.
2. **Desambiguación HITL Completa y Foco:** En Preset 2 (`manuscrito_obra`), pulsar *"Ejecutar Compulsa Multi-Corralón"* sin resolver la fila 2 enfoca automáticamente la primera píldora de material de dicha fila; ingestar `"4 caño pvc"` permite elegir el diámetro (`40 mm` / `110 mm`) y desbloquear la compulsa.
3. **Auditoría WCAG 2.2 AA (Axe-core) y Regresión E2E:** `0` violaciones críticas o serias en `/`, `/traccion`, `/p/:token` y `VendorCatalogModal`; `100%` de inputs con `<label htmlFor>` asociado; botones primarios con altura `>= 42px`; y ejecución exitosa de `frontend/e2e/compulsa-flow.spec.ts`.
