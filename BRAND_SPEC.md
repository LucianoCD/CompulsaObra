# Especificación Técnica de Identidad Visual y Logotipo (`BRAND_SPEC.md`) — CompulsaObra

* **Versión del Documento:** `1.0.0` (Complemento de Identidad de Marca para `DESIGN_SPEC.md` v2.0.0)
* **Sistema Objetivo:** CompulsaObra (`frontend/` — React 18.3, TypeScript 5.4, Tailwind CSS v3.4, Lucide React)
* **Arquetipo Visual:** *Estudio Constructivo Cálido y Claridad Guiada* (*Warm Architectural Studio & Guided Clarity*)
* **Ámbito Geográfico y Operativo:** San Salvador de Jujuy, Palpalá, Perico y El Carmen (NOA, Argentina)
* **Marco Normativo:** ISO/IEC 25010:2023 (SQuaRE — Calidad en Uso y Usabilidad), 10 Heurísticas de Usabilidad de Jakob Nielsen y WCAG 2.2 Nivel AA

> **ADVERTENCIA CRÍTICA DE USABILIDAD Y ACCESIBILIDAD (A11y):**
> La incorporación de un logotipo y recursos gráficos de marca **prohíbe explícitamente** dos prácticas de alto riesgo:
> 1. **Sustituir el nombre textual por un isotipo aislado en la navegación:** Un enlace de retorno al inicio compuesto únicamente por un símbolo gráfico vulnera **Nielsen #2 (Relación entre el sistema y el mundo real)**, **Nielsen #6 (Reconocimiento antes que recuerdo)** y **WCAG 2.2 (Criterios 2.4.4 y 4.1.2)**, además de comprometer la accesibilidad de la cabecera actual (`aria-label="Ir al inicio de CompulsaObra"`). El isotipo debe ir siempre acompañado del *wordmark* legible **CompulsaObra** y declararse con `aria-hidden="true"`.
> 2. **Aplicar tramas arquitectónicas o marcas de agua detrás de cifras financieras:** Colocar texturas de marca detrás de precios unitarios, subtotales o totales en `MultiVendorMatrix`, `SplitCartOptimizerCard` o `PublicBudgetViewPage` degrada el contraste por debajo del mínimo obligatorio **WCAG 1.4.3 (`4.5:1`)** y perjudica la **Operabilidad (ISO/IEC 25010)**. Todo detalle estético complementario debe confinarse a contenedores estructurales libres de texto superpuesto.

---

## 1. Análisis de Usabilidad (Nielsen & SQuaRE)

### 1.1 Diagnóstico del Estado Actual de Marca

La revisión del repositorio actual (`frontend/`) evidencia que, si bien la paleta cálida y la arquitectura de componentes ya se encuentran alineadas con *Estudio Constructivo Cálido*, la identidad gráfica de marca presenta vacíos que reducen la confianza institucional en oficina técnica y frente al comitente final:

1. **Identificador genérico en cabecera (`DemoBanner.tsx` y `PublicBudgetViewPage.tsx`):** El bloque actual de `36×36 px` (`h-9 w-9`) muestra únicamente las iniciales `"CO"` en tipografía plana, sin diferenciación semántica respecto de cualquier herramienta genérica.
2. **Ausencia de identidad en pestaña del navegador (`frontend/index.html`):** El documento sigue referenciando `/vite.svg` como icono principal, proyectando un estado de prototipo sin terminar.
3. **Discontinuidad visual en vistas periféricas (`App.tsx` y `TractionEvidencePage.tsx`):** La vista de verificación de correo (`EmailVerificationPage`) y el tablero `/traccion` carecen de cabecera de marca unificada, debilitando la coherencia entre pasos del flujo.

### 1.2 Evaluación Normativa de la Propuesta *"Escuadra y Cotejo"*

| Pilar Normativo | Criterio / Heurística Evaluada | Justificación de Diseño del Imagotipo y Detalles Estéticos |
| :--- | :--- | :--- |
| **ISO/IEC 25010 (SQuaRE)** | *Appropriateness recognizability* & *Aesthetics* | La síntesis geométrica de una escuadra de obra (medida exacta) junto con dos barras comparativas (cotejo de precios) comunica instantáneamente el dominio de construcción y ahorro sin requerir explicaciones previas. |
| **Heurísticas de Nielsen** | `#2 Relación con el mundo real` & `#4 Consistencia` | Replicar el mismo emblema en la cabecera operativa, el favicon adaptativo, la verificación de cuenta y el sello de presupuesto público `/p/:token` unifica la experiencia de extremo a extremo. |
| **Heurísticas de Nielsen** | `#8 Diseño estético y minimalista` | Los detalles complementarios (retículas de cota en esquinas de dropzones y filete superior de `3px` en presupuestos emitidos) actúan como guías visuales funcionales de baja densidad sin competir con los datos numéricos. |
| **WCAG 2.2 Nivel AA** | `1.4.3 Contrast`, `1.4.11 Non-text Contrast` & `2.3.3 Animation` | El isotipo utiliza tokens CSS de alto contraste (`>= 5.9:1`) adaptados a modo claro y oscuro, y sus micro-transiciones respetan `prefers-reduced-motion: reduce`. |

---

## 2. Estructura y Layout (Low-Fidelity)

### 2.1 Anatomía Geométrica del Imagotipo: *"Escuadra y Cotejo"*

El imagotipo se compone de un **isotipo vectorial cuadrado** construido sobre una retícula ortogonal de `32×32` unidades (con esquinas redondeadas `rx="7"`, trazo uniforme de `2.6` unidades y remates redondeados `stroke-linecap="round"`) acoplado horizontalmente al *wordmark* tipográfico **CompulsaObra**:

1. **La Escuadra de Obra (Contorno en "C"):** Perfil estructural abierto hacia la derecha que evoca una escuadra de replanteo y dibuja la inicial **C** (*Compulsa*), simbolizando precisión metrológica y cero sustitución ciega.
2. **Las Barras de Cotejo (Núcleo en "O"):** Dos barras horizontales paralelas contenidas dentro de la escuadra. La barra superior representa el precio de lista estándar y la barra inferior, acortada hacia la izquierda, simboliza la optimización de costo lograda mediante la comparativa multi-corralón.
3. **El Vértice de Cota (Punto de Precisión):** Un nodo circular sólido de radio `2.2` unidades ubicado a la derecha de la barra inferior que remite a una cota de plano técnico y cierra visualmente la lectura de la letra **O** (*Obra*).

```text
RETÍCULA DEL ISOTIPO (32 x 32 u)              COMPOSICIÓN EN CABECERA GLOBAL (h: 60px)
+------------------------------------+        +----------------------------------------------------+
|  (rx=7, fondo --brand-mark-bg)     |        | [ISOTIPO]  CompulsaObra   ( NOA · Jujuy )          |
|    +--------------------------+    |        |  36x36px   800 / 600      Pill 12px                |
|    |  ======================  |    |        +----------------------------------------------------+
|    |  (Barra precio estándar) |    |
|    |                          |    |        VARIANTE SELLO DE PRESUPUESTO (/p/:token)
|    |  =============   ( ● )   |    |        +----------------------------------------------------+
|    +--- (Ahorro y cota) ------+    |        | [ISOTIPO 24px]  Snapshot Inmutable Verificado      |
+------------------------------------+        +----------------------------------------------------+
```

### 2.2 Variantes, Escalas y Área de Resguardo (*Clearspace*)

| Variante del Componente `BrandLogo` | Tamaño Isotipo | Elementos Visibles | Contexto de Aplicación y Resguardo |
| :--- | :--- | :--- | :--- |
| **`full` (Cabecera Principal)** | `36×36 px` (`h-9 w-9`) | Isotipo + Wordmark `CompulsaObra` + Píldora `NOA · Jujuy` (`>= 640px`). | Barra global en `DemoBanner.tsx`. Área de resguardo mínima de `8px` (`0.25×` altura) libre alrededor del bloque. |
| **`compact` (Vistas Secundarias)** | `32×32 px` (`h-8 w-8`) | Isotipo + Wordmark `CompulsaObra` (sin píldora regional). | Cabecera minimalista de `PublicBudgetViewPage.tsx`, `TractionEvidencePage.tsx` y `EmailVerificationPage`. |
| **`seal` (Sello Auditado)** | `24×24 px` (`h-6 w-6`) | Isotipo monocromático en `--winner-text` sin contenedor terracota. | Integrado dentro de la insignia `Snapshot Inmutable HMAC-SHA256 Verificado` en `/p/:token`. |
| **`favicon` (Pestaña Navegador)** | `16×16` / `32×32 px` | Exclusivamente el Isotipo (`frontend/public/favicon.svg`), sin texto. | Pestaña del navegador y accesos directos PWA, con margen interno de `4px` en el `viewBox`. |

### 2.3 Detalles Estéticos Complementarios Coherentes con el Logotipo

Para extender la identidad visual de forma sutil y funcional sin incrementar la carga cognitiva:

1. **Retículas de Cota en Esquinas (*Drafting Corner Ticks*):** En los contenedores de carga de archivos de `IngestionDropzone.tsx` (pestaña *Foto de Pedido*) y `VendorCatalogModal.tsx` (pestaña *Importar Lista*), incorporar cuatro escuadras interiores de `10×10 px` en las esquinas (`border-2` en `--action-primary` con `opacity-45` en reposo y `opacity-100` en `:hover` / `:focus-within`).
2. **Contraste Tipográfico Dual en el Wordmark:** Diferenciar visualmente los dos lexemas mediante peso tipográfico sin separar la cadena accesible para lectores de pantalla: **`Compulsa`** en peso `800` (`content.primary`) + **`Obra`** en peso `600` (`content.secondary`).
3. **Filete Arquitectónico de Emisión en Presupuesto Público:** Aplicar un borde superior de `3px` en `--action-primary` (`border-t-[3px] border-action-primary`) sobre la tarjeta principal de `PublicBudgetViewPage.tsx`, acompañando el sello `BrandLogo` en variante `seal`.

---

## 3. Tokens de Diseño (Hi-Fidelity)

### 3.1 Extensión de Tokens W3C DTCG (`$version: "2025.10"`)

Los tokens de marca se integran directamente en `frontend/src/index.css` y `frontend/tailwind.config.js` respetando la paleta cálida establecida en `DESIGN_SPEC.md`:

```json
{
  "$version": "2025.10",
  "color": {
    "brand": {
      "markBg": {
        "$type": "color",
        "$value": {
          "light": { "hex": "#A83511", "oklch": "oklch(0.492 0.162 34)" },
          "dark": { "hex": "#E8683A", "oklch": "oklch(0.668 0.172 38)" }
        }
      },
      "markFg": {
        "$type": "color",
        "$value": {
          "light": { "hex": "#FFFFFF", "oklch": "oklch(1.000 0.000 0)" },
          "dark": { "hex": "#121316", "oklch": "oklch(0.186 0.006 255)" }
        }
      },
      "markAccent": {
        "$type": "color",
        "$value": {
          "light": { "hex": "#FDE68A", "oklch": "oklch(0.924 0.115 92)" },
          "dark": { "hex": "#083327", "oklch": "oklch(0.295 0.068 165)" }
        }
      }
    }
  },
  "typography": {
    "wordmark": {
      "fontFamily": { "$type": "fontFamily", "$value": ["Plus Jakarta Sans", "system-ui", "sans-serif"] },
      "sizeDesktop": { "$type": "dimension", "$value": "18px" },
      "sizeMobile": { "$type": "dimension", "$value": "16px" },
      "letterSpacing": { "$type": "dimension", "$value": "-0.025em" },
      "lineHeight": { "$type": "number", "$value": 1.1 }
    }
  }
}
```

### 3.2 Verificación de Contraste WCAG 2.2 (Isotipo y Wordmark)

| Elemento Gráfico / Textual | Tema Claro (Primer Plano / Fondo) | Ratio Claro | Tema Oscuro (Primer Plano / Fondo) | Ratio Oscuro | Cumplimiento |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Escuadra y Barra Superior (`markFg` / `markBg`)** | `#FFFFFF` / `#A83511` | `5.9:1` | `#121316` / `#E8683A` | `6.3:1` | **WCAG 1.4.11 AA (`>= 3:1`)** |
| **Barra Ahorro y Punto Cota (`markAccent` / `markBg`)** | `#FDE68A` / `#A83511` | `4.8:1` | `#083327` / `#E8683A` | `4.6:1` | **WCAG 1.4.11 AA (`>= 3:1`)** |
| **Contenedor Isotipo (`markBg` / `surface.elevated`)** | `#A83511` / `#FFFFFF` | `5.9:1` | `#E8683A` / `#1A1C20` | `5.7:1` | **WCAG 1.4.11 AA (`>= 3:1`)** |
| **Wordmark `"Compulsa"` (`text.primary` / `surface.elevated`)** | `#1C1917` / `#FFFFFF` | `17.4:1` | `#F5F4F0` / `#1A1C20` | `16.2:1` | **WCAG 1.4.3 AAA** |
| **Wordmark `"Obra"` (`text.secondary` / `surface.elevated`)** | `#44403C` / `#FFFFFF` | `10.1:1` | `#C2C6CE` / `#1A1C20` | `10.3:1` | **WCAG 1.4.3 AAA** |

### 3.3 Matriz de Estados Interactivos del Bloque de Marca y Retículas

| Elemento | Default | Hover | Focus-Visible | Active | Reduced Motion |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Enlace de Marca (`<a href="/">`)** | Contenedor en `--brand-mark-bg`, radio `8px`, `shadow-card`. | Fondo `--action-primary-hover`; barra inferior interna desplaza `2px` a la derecha (`160ms`). | Anillo `2px solid var(--action-focus)`, `outline-offset: 2px` alrededor del conjunto. | Escala `0.98` en el contenedor del isotipo sin alterar altura de cabecera. | Desactiva desplazamiento de barra y escala (`transition-duration: 0.01ms`). |
| **Retículas de Esquina en Dropzones** | 4 escuadras `10×10 px` en `border-action-primary/45`. | Opacidad `100%` (`border-action-primary`) al pasar el puntero sobre la zona. | Opacidad `100%` cuando el `<label>` de selección recibe foco de teclado. | Mantiene opacidad `100%` durante la selección de archivo. | Cambio instantáneo de opacidad sin interpolación. |

---

## 4. Especificaciones de Componentes y Handoff

### 4.1 Directivas de Implementación por Archivo

1. **Componente `BrandLogo` (`frontend/src/components/BrandLogo.tsx`):**
   * Crear un componente puro y tipado sin dependencias externas que acepte `variant?: 'full' | 'compact' | 'seal'`, `showRegionBadge?: boolean` y `className?: string`.
   * Encapsular el isotipo en un elemento `<svg viewBox="0 0 32 32" role="img" aria-hidden="true" focusable="false">` utilizando las variables CSS `var(--brand-mark-bg)`, `var(--brand-mark-fg)` y `var(--brand-mark-accent)` para `full` y `compact`, y `currentColor` para `seal`.
   * Renderizar el *wordmark* como un único flujo textual (`<span>Compulsa<span>Obra</span></span>`) para que los lectores de pantalla lo pronuncien como una palabra continua sin fragmentación silábica.

2. **Favicon Adaptativo (`frontend/public/favicon.svg` e `index.html`):**
   * Definir `frontend/public/favicon.svg` con `viewBox="0 0 32 32"` incorporando una hoja de estilo embebida `@media (prefers-color-scheme: dark)` que conmute automáticamente los colores entre `#A83511`/`#FFFFFF`/`#FDE68A` (claro) y `#E8683A`/`#121316`/`#083327` (oscuro).
   * Reemplazar en `frontend/index.html` la referencia `<link rel="icon" type="image/svg+xml" href="/vite.svg" />` por `<link rel="icon" type="image/svg+xml" href="/favicon.svg" />`.

3. **Integración en Vistas Existentes (`DemoBanner.tsx`, `App.tsx`, `PublicBudgetViewPage.tsx`, `TractionEvidencePage.tsx`):**
   * En `DemoBanner.tsx`, reemplazar el contenedor `CO` por `<BrandLogo variant="full" showRegionBadge />` dentro del enlace `<a href="/" aria-label="Ir al inicio de CompulsaObra">`, preservando el selector E2E existente.
   * En `PublicBudgetViewPage.tsx`, sustituir el bloque `CO` de la cabecera minimalista por `<BrandLogo variant="compact" />`, añadir `border-t-[3px] border-action-primary` a la tarjeta principal del presupuesto e incluir `<BrandLogo variant="seal" />` dentro de la píldora `Snapshot Inmutable HMAC-SHA256 Verificado`.
   * En `EmailVerificationPage` (`App.tsx`) y `TractionEvidencePage.tsx`, incorporar `<BrandLogo variant="compact" />` en la cabecera para garantizar continuidad visual en flujos externos.

4. **Retículas de Escuadra en Zonas de Carga (`IngestionDropzone.tsx` y `VendorCatalogModal.tsx`):**
   * Agregar cuatro elementos decorativos (`aria-hidden="true"`) de `10×10 px` (`w-2.5 h-2.5`) posicionados absolutamente en las cuatro esquinas interiores del área `border-dashed`, utilizando `border-t-2 border-l-2`, `border-t-2 border-r-2`, `border-b-2 border-l-2` y `border-b-2 border-r-2` con `border-action-primary/45 group-hover:border-action-primary group-focus-within:border-action-primary`.

5. **Tokens CSS y Tailwind (`frontend/src/index.css` y `frontend/tailwind.config.js`):**
   * Declarar `--brand-mark-bg`, `--brand-mark-fg` y `--brand-mark-accent` tanto en `:root` como en `[data-theme="dark"]` dentro de `index.css`.
   * Registrar el grupo `brand: { markBg: "var(--brand-mark-bg)", markFg: "var(--brand-mark-fg)", markAccent: "var(--brand-mark-accent)" }` en `theme.extend.colors` de `tailwind.config.js`.

### 4.2 Criterios de Aceptación para Verificación Automatizada

1. **Integridad E2E (`frontend/e2e/compulsa-flow.spec.ts`):** El enlace principal conserva su nombre accesible `"Ir al inicio de CompulsaObra"` y texto visible `"CompulsaObra"`, sin alterar ninguno de los pasos de autenticación, importación CSV, HITL, compulsa, `lock-budget`, descarga PDF ni vistas públicas.
2. **Auditoría de Accesibilidad (WCAG 2.2 AA / Axe-core):** El `<svg>` del isotipo posee `aria-hidden="true"` sin nodos enfocados internos (`0` advertencias de imágenes sin texto alternativo ni enlaces duplicados) y cumple contraste `>= 4.5:1` en temas claro y oscuro.
3. **Verificación de Recursos Estáticos:** `frontend/public/favicon.svg` responde con `Content-Type: image/svg+xml` y `200 OK` en el build de producción (`vite build` / Nginx) sin referencias residuales a `/vite.svg`.
