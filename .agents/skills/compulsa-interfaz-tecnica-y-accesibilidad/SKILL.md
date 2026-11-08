---
name: compulsa-interfaz-tecnica-y-accesibilidad
description: >-
  Rige la interfaz de usuario de CompulsaObra bajo el estándar Industrial
  Utilitarian & Swiss Technical Grid (DESIGN_SPEC.md), tokens W3C DTCG
  (Claro #FAF8F5 / Oscuro #111315), WCAG 2.2 Nivel AA, ISO/IEC 25010:2023,
  guardia dimensional HITL accesible y reasignación manual segura de productos.
---

# Interfaz Técnica, Diseño Suizo-Industrial y Accesibilidad WCAG 2.2 AA (CompulsaObra)

## 1. Arquetipo Visual y Sistema de Tokens W3C DTCG
- **Tema Claro (Papel Técnico):** Superficie `#FAF8F5`, tarjetas `#FFFFFF`, bordes `#D5D0C7`, texto `#1C1917` y acento Terracota de Obra (`#B83B14`).
- **Tema Oscuro (Pizarra de Taller):** Superficie `#111315`, tarjetas `#1A1D20`, bordes `#2A2E33` y texto `#F2EFE9` bajo `[data-theme="dark"]`.
- **Tipografías Técnicas:**
  - `Plus Jakarta Sans`: Títulos, jerarquías principales y encabezados.
  - `Public Sans`: Lectura en prosa técnica y etiquetas de formularios.
  - `JetBrains Mono`: Cifras monetarias ARS con `.tabular-nums`, SKUs, códigos de barras, dimensiones físicas y hashes.
- **Regla Anti-Slop Estricta:** Cero gradientes decorativos genéricos (`bg-indigo-*`, `bg-purple-*`, `bg-violet-*`), cero radios inflados (`rounded-2xl`, `rounded-3xl` prohibidos; máximo `rounded-md`).

## 2. Retícula Asimétrica de 12 Columnas (Layout 8 + 4)
- **8 Columnas (Izquierda):** Flujo técnico secuencial del cómputo métrico:
  1. `PASO 01`: Ingesta Multimodal (Presets NOA, editor monoespaciado, subida de imágenes accesible).
  2. `PASO 02`: Guardia Dimensional y Consola HITL de Desambiguación.
  3. `PASO 03`: Matriz Comparativa Multi-Corralón con primera columna fija (`sticky left-0`).
- **4 Columnas (Derecha):** Panel financiero y logístico adherente (`sticky top-4`):
  - Selector de modalidades de pago (Contado vs Lista vs Acopio).
  - Checkbox de fletes logísticos consolidados.
  - Desglose auditable de Carrito Dividido (*Split Cart*) vs Mejor Proveedor Único.
  - Simulador de Acopio con porcentajes de anticipo, saldo y preaviso logístico.
  - Acciones de cierre: Congelar presupuesto (Terracota `#B83B14`), descargar PDFs y copiar enlace público HMAC.

## 3. Accesibilidad WCAG 2.2 Nivel AA y Usabilidad ISO/IEC 25010
- **Guardia Dimensional HITL (Nielsen #5):**
  - Botón de compulsa con `aria-disabled="true"` mientras existan ítems con `missing_critical_attribute`.
  - Auto-enfoque accesible hacia la primera fila que requiere clarificación al intentar compulsar.
  - Píldoras táctiles de al menos 36px (`min-h-[36px]`) para selección de material en 1 clic y anuncios en `aria-live="polite"`.
- **Cero Sustitución Ciega en Matriz (WCAG 1.4.1):**
  - Celdas `NOT_CARRIED` combinan texto explícito (`[NO TRABAJA MEDIDA]`), ícono semántico de descarte y trama diagonal a 45° (`.bg-not-carried-pattern`). Jamás usar solo color para comunicar estado.
- **Protección de Foco No Oculto (WCAG 2.4.11):**
  - Contenedor `.matrix-scroll-container` con `scroll-padding-inline-start: 280px` y `scroll-padding-top: 96px`.
- **Reasignación Manual Segura (`applyMatrixOverride`):**
  - Diálogo modal con `<dialog>` nativo accesible (`showModal()`).
  - Al sustituir un producto, enviar `overrideMatch` y actualizar `currentMatrix` en el store Zustand sin llamar a `runComparison` para no destruir la personalización técnica.
