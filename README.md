# CompulsaObra (`compulsa-obra`)

Sistema Inteligente de Elaboración de Presupuestos y Comparación Multi-Negocio de Materiales de Construcción orientado a presupuestadores profesionales (`ESTIMATOR`) y compradores finales (`BUYER`) del NOA (San Salvador de Jujuy, Palpalá, Perico y El Carmen).

## Capacidades Principales
1. **Ingesta Multimodal y Normalización Dimensional:** Fotos manuscritas de obra, WhatsApp o planillas con conversión exacta de pulgadas fraccionarias a milímetros ($1/2^{\prime\prime} \rightarrow 12.70\text{ mm}$, $3/4^{\prime\prime} \rightarrow 19.05\text{ mm}$, $4^{\prime\prime} \rightarrow 110.00\text{ mm}$).
2. **Desambiguación HITL (Human-in-the-Loop):** Bloqueo anti-error ante atributos críticos faltantes y aprendizaje de alias supervisados.
3. **Importador Multi-Fuente SHA-256:** Deduplicación incremental para listas de precios Excel/CSV.
4. **Filtro Dimensional Duro SQL y Cero Sustitución Ciega:** Jamás compara caños o hierros de diámetros distintos.
5. **Optimizador de Compra Dividida y Acopio:** Compara Mejor Proveedor Único vs. Carrito Dividido (descontando fletes) y condiciones de acopio de materiales.
6. **Presupuestos y Snapshot PDF:** Generación nativa vectorial `%PDF-1.4` con firma HMAC-SHA256 y tablero `/traccion` aislado.

## Ejecución Rápida

### Opción A: Desarrollo Local Instantáneo (SQLite + Vite)
```bash
# Backend
cd backend
python -m uvicorn app.main:app --port 8000 --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Opción B: Despliegue con Docker Compose (PostgreSQL 16)
```bash
docker compose up --build
```

## Verificación Empírica
```bash
# Backend (Pruebas unitarias, de integración y E2E-01 a E2E-05)
cd backend && pytest -v

# Frontend (Typecheck estricto y build de producción)
cd frontend && npx tsc --noEmit && npm run build
```
