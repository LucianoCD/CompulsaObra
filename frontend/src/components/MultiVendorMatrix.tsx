import React, { useEffect, useRef, useState } from 'react';
import { useComparisonStore } from '../store/useComparisonStore';
import { apiClient } from '../services/apiClient';
import { ComparisonItemCell, ComparisonItemRow, VendorProductResponse } from '../types/api';
import {
  Check,
  Edit3,
  Loader2,
  X,
  AlertTriangle,
  ShoppingBag,
  Truck,
  Ban,
} from 'lucide-react';

export const MultiVendorMatrix: React.FC = () => {
  const { currentMatrix, lockedBudget, applyMatrixOverride } = useComparisonStore();

  const [overrideCell, setOverrideCell] = useState<{
    cell: ComparisonItemCell;
    row: ComparisonItemRow;
  } | null>(null);
  const [vendorProducts, setVendorProducts] = useState<VendorProductResponse[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [savingOverride, setSavingOverride] = useState(false);
  const [overrideError, setOverrideError] = useState<string | null>(null);

  // Selección en Drawer
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [forceOverride, setForceOverride] = useState(false);
  const [overrideReason, setOverrideReason] = useState('');

  const dialogRef = useRef<HTMLDialogElement | null>(null);

  useEffect(() => {
    if (overrideCell && dialogRef.current) {
      if (!dialogRef.current.open) {
        dialogRef.current.showModal();
      }
    } else if (!overrideCell && dialogRef.current?.open) {
      dialogRef.current.close();
    }
  }, [overrideCell]);

  if (!currentMatrix) return null;

  const isLocked = !!lockedBudget;

  const handleOpenOverride = async (cell: ComparisonItemCell, row: ComparisonItemRow) => {
    if (isLocked) return;
    setOverrideCell({ cell, row });
    setSelectedProductId(null);
    setForceOverride(false);
    setOverrideReason('');
    setOverrideError(null);

    try {
      setLoadingProducts(true);
      const prods = await apiClient.getVendorProducts(cell.vendor_id);
      setVendorProducts(prods);
      setLoadingProducts(false);
    } catch (err: unknown) {
      setLoadingProducts(false);
      setOverrideError(err instanceof Error ? err.message : 'Error al cargar productos del comercio');
    }
  };

  const handleCloseDrawer = () => {
    setOverrideCell(null);
    setSelectedProductId(null);
    setForceOverride(false);
    setOverrideReason('');
    setOverrideError(null);
  };

  const selectedProduct = vendorProducts.find((p) => p.id === selectedProductId);

  const normalizeText = (val: string) =>
    val.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();

  const technicalDiscrepancies: string[] = [];
  if (overrideCell && selectedProduct) {
    const reqRow = overrideCell.row;
    if (reqRow.material_type) {
      if (!selectedProduct.material_type) {
        technicalDiscrepancies.push(`Material requerido '${reqRow.material_type}' vs producto sin especificar.`);
      } else {
        const reqMat = normalizeText(reqRow.material_type);
        const prodMat = normalizeText(selectedProduct.material_type);
        const bothSteel =
          (reqMat.includes('hierro') || reqMat.includes('acero')) &&
          (prodMat.includes('hierro') || prodMat.includes('acero'));
        if (!bothSteel && reqMat !== prodMat && !reqMat.includes(prodMat) && !prodMat.includes(reqMat)) {
          technicalDiscrepancies.push(
            `Material incompatible: solicitado '${reqRow.material_type}' vs producto '${selectedProduct.material_type}'.`
          );
        }
      }
    }
    if (reqRow.diameter_mm != null) {
      if (selectedProduct.diameter_mm == null || Math.abs(selectedProduct.diameter_mm - reqRow.diameter_mm) > 0.5) {
        technicalDiscrepancies.push(
          `Diámetro incompatible: solicitado Ø ${reqRow.diameter_mm} mm vs producto ${
            selectedProduct.diameter_mm != null ? `Ø ${selectedProduct.diameter_mm} mm` : 'sin diámetro'
          }.`
        );
      }
    }
    const reqUnit = (reqRow.requested_unit || 'UN').toUpperCase();
    if (reqRow.length_m != null && !['M', 'MT', 'MTS', 'METRO', 'METROS'].includes(reqUnit)) {
      if (selectedProduct.length_m == null || Math.abs(selectedProduct.length_m - reqRow.length_m) > 0.05) {
        technicalDiscrepancies.push(
          `Longitud incompatible: solicitado ${reqRow.length_m} m vs producto ${
            selectedProduct.length_m != null ? `${selectedProduct.length_m} m` : 'sin longitud'
          }.`
        );
      }
    }
    if (reqRow.weight_kg != null && !['KG', 'KILO', 'KILOS'].includes(reqUnit)) {
      if (selectedProduct.weight_kg == null || Math.abs(selectedProduct.weight_kg - reqRow.weight_kg) > 0.5) {
        technicalDiscrepancies.push(
          `Peso incompatible: solicitado ${reqRow.weight_kg} kg vs producto ${
            selectedProduct.weight_kg != null ? `${selectedProduct.weight_kg} kg` : 'sin peso'
          }.`
        );
      }
    }
  }

  const hasDimensionMismatch = technicalDiscrepancies.length > 0;
  const requiresReason = hasDimensionMismatch && forceOverride;

  const handleConfirmOverride = async () => {
    if (!overrideCell || !selectedProductId) return;
    if (requiresReason && overrideReason.trim().length < 5) {
      setOverrideError('Debes ingresar una justificación técnica (mínimo 5 caracteres) para forzar la sustitución.');
      return;
    }

    try {
      setSavingOverride(true);
      setOverrideError(null);
      const targetMatchId = overrideCell.cell.match_id;
      if (!targetMatchId) {
        throw new Error('No se encontró el identificador de coincidencia para esta celda.');
      }

      await applyMatrixOverride(currentMatrix.run_id, targetMatchId, {
        vendor_product_id: selectedProductId,
        save_vendor_alias: true,
        force_dimension_override: forceOverride,
        override_reason: hasDimensionMismatch ? overrideReason.trim() : overrideReason.trim() || undefined,
      });

      handleCloseDrawer();
      setSavingOverride(false);
    } catch (err: unknown) {
      setSavingOverride(false);
      setOverrideError(err instanceof Error ? err.message : 'Error al sustituir producto');
    }
  };

  return (
    <section
      role="region"
      aria-labelledby="matrix-heading"
      className="bg-surface-elevated border border-surface-hairline rounded-container p-4 sm:p-5 transition-colors space-y-4"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-surface-hairline gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-control bg-surface-subtle text-action-primary border border-surface-hairline">
              PASO 03
            </span>
            <h2 id="matrix-heading" className="text-sm sm:text-base font-display font-bold text-content-primary">
              Matriz Comparativa Multi-Corralón
            </h2>
          </div>
          <p className="text-xs text-content-secondary mt-1">
            Filtro dimensional duro en tiempo real. Los recuadros resaltados identifican la oferta más económica por línea.
          </p>
        </div>
      </div>

      {/* Tabla con Primera Columna Sticky y Protección de Foco Oculto */}
      <div
        tabIndex={0}
        role="region"
        aria-label="Tabla de matriz comparativa con desplazamiento horizontal"
        className="overflow-x-auto border border-surface-hairline rounded-control bg-surface-canvas matrix-scroll-container focus:outline-none"
      >
        <table role="grid" className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-surface-hairline bg-surface-subtle text-content-secondary uppercase text-[11px] font-semibold tracking-wider">
              {/* Columna Sticky de Especificación Técnica */}
              <th
                scope="col"
                className="py-3 px-3.5 min-w-[260px] sticky left-0 z-20 bg-surface-elevated border-r border-surface-hairline shadow-[2px_0_4px_rgba(0,0,0,0.04)]"
              >
                Material Requerido en Obra
              </th>
              <th scope="col" className="py-3 px-2 text-center min-w-[70px]">
                Cant.
              </th>
              {currentMatrix.vendors.map((v) => (
                <th key={v.vendor_id} scope="col" className="py-3 px-3 text-right min-w-[210px] border-l border-surface-hairline">
                  <div className="font-bold text-content-primary truncate">{v.vendor_name}</div>
                  <div className="text-[10px] text-content-muted font-mono font-normal mt-0.5">
                    {v.locality} · Cob: <span className="tabular-nums font-bold text-content-secondary">{v.coverage_pct}%</span>
                  </div>
                  {/* Barra compacta de cobertura */}
                  <div className="w-full bg-surface-subtle h-1 rounded-full mt-1.5 overflow-hidden">
                    <div
                      className="bg-emerald-600 dark:bg-emerald-500 h-full rounded-full transition-all"
                      style={{ width: `${v.coverage_pct}%` }}
                    />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-hairline font-mono">
            {currentMatrix.matrix_rows.map((row) => (
              <tr key={row.requisition_item_id} className="hover:bg-surface-subtle/30 transition-colors">
                {/* Columna Sticky Izquierda */}
                <td className="py-3 px-3.5 font-sans sticky left-0 z-10 bg-surface-elevated border-r border-surface-hairline shadow-[2px_0_4px_rgba(0,0,0,0.04)]">
                  <div className="font-bold text-content-primary text-xs">{row.requested_term}</div>
                  <div className="text-[11px] text-content-secondary flex flex-wrap items-center gap-1.5 mt-1 font-mono">
                    {row.diameter_mm && (
                      <span className="px-1.5 py-0.2 rounded bg-surface-subtle border border-surface-hairline text-[10px]">
                        Ø {row.diameter_mm} mm
                      </span>
                    )}
                    {row.material_type && (
                      <span className="px-1.5 py-0.2 rounded bg-surface-subtle border border-surface-hairline text-[10px] font-sans font-medium">
                        {row.material_type}
                      </span>
                    )}
                  </div>
                </td>

                <td className="py-3 px-2 text-center tabular-nums text-content-primary font-bold">
                  {row.quantity} <span className="text-[10px] text-content-muted font-sans">{row.requested_unit}</span>
                </td>

                {row.vendor_cells.map((cell) => {
                  const isNotCarried = cell.match_status === 'NOT_CARRIED';
                  const isOutOfStock = cell.match_status === 'OUT_OF_STOCK';
                  const isAmbiguous = cell.match_status === 'AMBIGUOUS_CANDIDATES';
                  const isBest = cell.is_best_price;
                  const isSplitWinner = cell.is_selected_split;

                  return (
                    <td
                      key={cell.vendor_id}
                      className={`py-3 px-3 text-right border-l border-surface-hairline transition-colors ${
                        isBest
                          ? 'bg-semantic-winnerBg text-semantic-winnerText'
                          : isNotCarried
                          ? 'bg-not-carried-pattern'
                          : ''
                      }`}
                    >
                      {isNotCarried ? (
                        <div className="inline-flex flex-col items-end">
                          <span className="inline-flex items-center gap-1 text-[10px] font-sans px-2 py-0.5 rounded-control bg-surface-elevated text-content-secondary border border-surface-hairline font-bold shadow-2xs">
                            <Ban className="w-3 h-3 text-action-danger" />
                            [NO TRABAJA MEDIDA]
                          </span>
                          <span className="text-[9px] text-content-muted font-sans mt-0.5">
                            Filtro dimensional duro
                          </span>
                        </div>
                      ) : isAmbiguous ? (
                        <div className="inline-flex flex-col items-end gap-1">
                          <span className="inline-flex items-center gap-1 text-[10px] font-sans px-2 py-0.5 rounded-control bg-semantic-hitlBg text-semantic-hitlText border border-semantic-hitlBorder font-bold">
                            <AlertTriangle className="w-3 h-3" />
                            [AMBIGUO - DEFINIR]
                          </span>
                          {!isLocked && (
                            <button
                              onClick={() => handleOpenOverride(cell, row)}
                              type="button"
                              className="inline-flex items-center gap-1 text-[10px] font-sans text-action-primary hover:underline font-semibold"
                            >
                              <Edit3 className="w-2.5 h-2.5" /> Elegir producto
                            </button>
                          )}
                        </div>
                      ) : isOutOfStock ? (
                        <div className="inline-flex flex-col items-end">
                          <span className="text-[10px] font-sans px-2 py-0.5 rounded-control bg-semantic-hitlBg text-semantic-hitlText border border-semantic-hitlBorder font-bold">
                            [SIN STOCK EN CORRALÓN]
                          </span>
                        </div>
                      ) : cell.line_subtotal_ars !== null && cell.line_subtotal_ars !== undefined ? (
                        <div className="group relative">
                          <div
                            className={`font-mono font-bold text-sm tabular-nums ${
                              isBest ? 'text-emerald-700 dark:text-emerald-400' : 'text-content-primary'
                            }`}
                          >
                            $ {cell.line_subtotal_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                          </div>
                          <div className="text-[10px] text-content-muted tabular-nums mt-0.5">
                            $ {cell.unit_price_ars?.toLocaleString('es-AR', { minimumFractionDigits: 2 })} / {row.requested_unit}
                          </div>

                          <div className="flex items-center justify-end gap-1.5 mt-1">
                            {isBest && (
                              <span className="inline-flex items-center gap-0.5 text-[9px] font-sans px-1.5 py-0.2 rounded bg-emerald-500/15 text-emerald-800 dark:text-emerald-300 font-bold uppercase">
                                <Check className="w-2.5 h-2.5" /> Mejor
                              </span>
                            )}
                            {isSplitWinner && (
                              <span className="inline-flex items-center gap-0.5 text-[9px] font-sans px-1.5 py-0.2 rounded bg-action-primary/10 text-action-primary font-bold uppercase">
                                <ShoppingBag className="w-2.5 h-2.5" /> Split
                              </span>
                            )}
                            {!isLocked && (
                              <button
                                onClick={() => handleOpenOverride(cell, row)}
                                type="button"
                                className="opacity-0 group-hover:opacity-100 focus:opacity-100 transition inline-flex items-center gap-1 text-[10px] font-sans text-content-secondary hover:text-action-primary underline underline-offset-2 ml-1"
                                title="Cambiar producto asignado"
                              >
                                <Edit3 className="w-2.5 h-2.5" /> Cambiar
                              </button>
                            )}
                          </div>
                        </div>
                      ) : (
                        <span className="text-content-muted">-</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>

          {/* Pie de Tabla con Totales y Fletes por Corralón */}
          <tfoot className="border-t-2 border-surface-hairline bg-surface-subtle font-mono text-xs">
            <tr>
              <th scope="row" className="py-2.5 px-3.5 sticky left-0 z-20 bg-surface-subtle font-sans text-content-primary font-bold border-r border-surface-hairline">
                Flete Estimado por Envío
              </th>
              <td className="text-center font-bold text-content-muted">-</td>
              {currentMatrix.vendors.map((v) => (
                <td key={v.vendor_id} className="py-2.5 px-3 text-right tabular-nums text-content-secondary border-l border-surface-hairline">
                  <span className="inline-flex items-center gap-1">
                    <Truck className="w-3 h-3 text-content-muted" />
                    + $ {v.delivery_fee_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                  </span>
                </td>
              ))}
            </tr>
            <tr className="border-t border-surface-hairline font-bold">
              <th scope="row" className="py-3 px-3.5 sticky left-0 z-20 bg-surface-subtle font-sans text-content-primary font-bold border-r border-surface-hairline">
                Costo Total con Flete
              </th>
              <td className="text-center font-bold text-content-muted">-</td>
              {currentMatrix.vendors.map((v) => (
                <td key={v.vendor_id} className="py-3 px-3 text-right tabular-nums text-sm text-content-primary border-l border-surface-hairline font-extrabold">
                  $ {v.total_with_delivery_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Inspector Lateral (Drawer) para Sustitución Manual de Producto con <dialog> Nativo */}
      <dialog
        ref={dialogRef}
        aria-labelledby="override-drawer-title"
        onClose={handleCloseDrawer}
        className="fixed inset-y-0 right-0 m-0 ml-auto h-full max-h-screen w-full max-w-md bg-surface-elevated border-l border-surface-hairline p-0 text-content-primary shadow-2xl backdrop:bg-black/50 backdrop:backdrop-blur-xs focus:outline-none"
      >
        {overrideCell && (
          <div className="flex flex-col h-full">
            {/* Cabecera del Drawer */}
            <div className="p-4 border-b border-surface-hairline flex items-center justify-between bg-surface-subtle">
              <div>
                <span className="text-[10px] font-mono uppercase text-content-muted">
                  Reemplazo Manual de Producto
                </span>
                <h3 id="override-drawer-title" className="text-sm font-bold text-content-primary mt-0.5">
                  {overrideCell.cell.vendor_name}
                </h3>
              </div>
              <button
                onClick={handleCloseDrawer}
                type="button"
                className="p-1 rounded-control hover:bg-surface-elevated text-content-secondary hover:text-content-primary transition"
                aria-label="Cerrar inspector de producto"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Contexto del Ítem Solicitado */}
            <div className="p-4 bg-surface-canvas border-b border-surface-hairline text-xs space-y-1">
              <div className="text-content-muted">Ítem solicitado en el pliego:</div>
              <div className="font-bold text-content-primary text-sm font-sans">{overrideCell.row.requested_term}</div>
              <div className="text-[11px] font-mono text-content-secondary flex flex-wrap gap-2">
                {overrideCell.row.material_type && <span>Material: <strong>{overrideCell.row.material_type}</strong></span>}
                {overrideCell.row.diameter_mm != null && <span>Ø <strong>{overrideCell.row.diameter_mm} mm</strong></span>}
                {overrideCell.row.length_m != null && <span>Long: <strong>{overrideCell.row.length_m} m</strong></span>}
                {overrideCell.row.weight_kg != null && <span>Peso: <strong>{overrideCell.row.weight_kg} kg</strong></span>}
              </div>
            </div>

            {overrideError && (
              <div className="m-4 p-3 rounded-control bg-action-danger/10 border border-action-danger/30 text-xs text-action-danger font-medium flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{overrideError}</span>
              </div>
            )}

            {/* Lista de Productos del Proveedor */}
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              <span className="text-[11px] font-semibold uppercase text-content-secondary tracking-wider block mb-2">
                Catálogo Activo del Comercio ({vendorProducts.length} ítems):
              </span>

              {loadingProducts ? (
                <div className="py-12 text-center text-content-secondary text-xs flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-action-primary" />
                  <span>Cargando catálogo del corralón...</span>
                </div>
              ) : vendorProducts.length === 0 ? (
                <div className="py-8 text-center text-xs text-content-muted">
                  No hay productos cargados para este comercio.
                </div>
              ) : (
                vendorProducts.map((p) => {
                  const isSelected = selectedProductId === p.id;
                  const isCurrentAssigned = overrideCell.cell.vendor_product_id === p.id;

                  return (
                    <button
                      key={p.id}
                      onClick={() => {
                        setSelectedProductId(p.id);
                        setForceOverride(false);
                      }}
                      type="button"
                      className={`w-full text-left p-3 rounded-control border text-xs transition flex items-start justify-between gap-3 ${
                        isSelected
                          ? 'border-action-primary bg-action-primary/5 shadow-xs'
                          : 'border-surface-hairline bg-surface-canvas hover:border-surface-strong'
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="font-bold text-content-primary font-sans">{p.raw_description}</div>
                        <div className="text-[11px] text-content-muted font-mono flex items-center gap-2">
                          <span>SKU: {p.sku}</span>
                          {p.diameter_mm && <span>Ø {p.diameter_mm} mm</span>}
                          {p.brand && <span>{p.brand}</span>}
                        </div>
                        {isCurrentAssigned && (
                          <span className="inline-block px-1.5 py-0.2 rounded-control bg-surface-subtle border border-surface-hairline text-[10px] text-content-secondary font-sans font-semibold">
                            (Actualmente emparejado)
                          </span>
                        )}
                      </div>
                      <div className="text-right font-mono font-bold text-content-primary tabular-nums">
                        $ {p.price_cash_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                      </div>
                    </button>
                  );
                })
              )}
            </div>

            {/* Alerta de Discrepancia Dimensional / Material y Confirmación (H-10) */}
            {hasDimensionMismatch && (
              <div className="p-4 bg-semantic-hitlBg border-t border-semantic-hitlBorder text-xs text-semantic-hitlText space-y-2">
                <div className="flex items-start gap-2 font-bold">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-700 dark:text-amber-400" />
                  <span>Discrepancias Técnicas Detectadas ({technicalDiscrepancies.length})</span>
                </div>
                <ul className="list-disc pl-4 space-y-0.5 text-[11px] leading-relaxed">
                  {technicalDiscrepancies.map((disc, idx) => (
                    <li key={idx}>{disc}</li>
                  ))}
                </ul>
                <label className="flex items-center gap-2 pt-1 font-semibold cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={forceOverride}
                    onChange={(e) => setForceOverride(e.target.checked)}
                    className="rounded-control border-surface-strong text-action-primary focus:ring-action-focus w-4 h-4"
                  />
                  <span>Forzar sustitución técnica bajo mi responsabilidad</span>
                </label>
                {forceOverride && (
                  <div className="pt-1 space-y-1">
                    <label htmlFor="override-reason-input" className="block text-[11px] font-bold">
                      Justificación técnica obligatoria:
                    </label>
                    <input
                      id="override-reason-input"
                      type="text"
                      value={overrideReason}
                      onChange={(e) => setOverrideReason(e.target.value)}
                      placeholder="Ej.: Aprobado por dirección de obra por faltante en plaza..."
                      className="w-full px-2.5 py-1.5 rounded-control border border-surface-strong bg-surface-canvas text-content-primary text-xs focus:outline-none focus:ring-1 focus:ring-action-primary"
                    />
                  </div>
                )}
              </div>
            )}

            {/* Pie del Drawer con Acciones */}
            <div className="p-4 border-t border-surface-hairline bg-surface-subtle flex items-center justify-end gap-2">
              <button
                onClick={handleCloseDrawer}
                type="button"
                className="px-3.5 py-2 rounded-control border border-surface-hairline bg-surface-elevated text-content-secondary hover:text-content-primary text-xs font-semibold transition"
              >
                Cancelar
              </button>
              <button
                onClick={handleConfirmOverride}
                disabled={
                  savingOverride ||
                  !selectedProductId ||
                  (hasDimensionMismatch && (!forceOverride || overrideReason.trim().length < 5))
                }
                type="button"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-control bg-action-primary hover:bg-action-hover disabled:opacity-50 text-white font-bold text-xs shadow-sm transition min-h-[38px]"
              >
                {savingOverride ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Guardando sustitución...</span>
                  </>
                ) : (
                  <span>Confirmar Sustitución</span>
                )}
              </button>
            </div>
          </div>
        )}
      </dialog>
    </section>
  );
};
