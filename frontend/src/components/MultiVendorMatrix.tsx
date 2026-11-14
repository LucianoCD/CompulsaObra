import React, { useEffect, useMemo, useRef, useState } from 'react';
import { getMatrixRequisitionStaleReason, useComparisonStore } from '../store/useComparisonStore';
import { useRequisitionStore } from '../store/useRequisitionStore';
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
  Package,
  Filter,
  RefreshCw,
} from 'lucide-react';

type MatrixFilterMode = 'all' | 'best_price' | 'unavailable';

export const MultiVendorMatrix: React.FC = () => {
  const { currentRequisition } = useRequisitionStore();
  const {
    currentMatrix,
    lockedBudget,
    applyMatrixOverride,
    runComparison,
    isLoading: isComparisonLoading,
  } = useComparisonStore();

  const [filterMode, setFilterMode] = useState<MatrixFilterMode>('all');
  const [overrideCell, setOverrideCell] = useState<{
    cell: ComparisonItemCell;
    row: ComparisonItemRow;
  } | null>(null);
  const [vendorProducts, setVendorProducts] = useState<VendorProductResponse[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [savingOverride, setSavingOverride] = useState(false);
  const [overrideError, setOverrideError] = useState<string | null>(null);

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

  const unavailableCount = useMemo(() => {
    if (!currentMatrix) return 0;
    return currentMatrix.matrix_rows.filter((row) =>
      row.vendor_cells.some(
        (c) =>
          c.match_status === 'NOT_CARRIED' ||
          c.match_status === 'OUT_OF_STOCK' ||
          c.match_status === 'AMBIGUOUS_CANDIDATES'
      )
    ).length;
  }, [currentMatrix]);

  const filteredRows = useMemo(() => {
    if (!currentMatrix) return [];
    if (filterMode === 'best_price') {
      return currentMatrix.matrix_rows.filter((row) =>
        row.vendor_cells.some((c) => c.is_best_price)
      );
    }
    if (filterMode === 'unavailable') {
      return currentMatrix.matrix_rows.filter((row) =>
        row.vendor_cells.some(
          (c) =>
            c.match_status === 'NOT_CARRIED' ||
            c.match_status === 'OUT_OF_STOCK' ||
            c.match_status === 'AMBIGUOUS_CANDIDATES'
        )
      );
    }
    return currentMatrix.matrix_rows;
  }, [currentMatrix, filterMode]);

  if (!currentMatrix) return null;

  const isLocked = !!lockedBudget || currentMatrix.status === 'LOCKED_BUDGET' || !!currentMatrix.is_locked;
  const matrixStaleReason = getMatrixRequisitionStaleReason(currentMatrix, currentRequisition);
  const isMatrixStale = !isLocked && Boolean(matrixStaleReason);

  const handleOpenOverride = async (cell: ComparisonItemCell, row: ComparisonItemRow) => {
    if (isLocked || isMatrixStale) return;
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
        technicalDiscrepancies.push(`Material pedido '${reqRow.material_type}' vs producto sin especificar.`);
      } else {
        const reqMat = normalizeText(reqRow.material_type);
        const prodMat = normalizeText(selectedProduct.material_type);
        const bothSteel =
          (reqMat.includes('hierro') || reqMat.includes('acero')) &&
          (prodMat.includes('hierro') || prodMat.includes('acero'));
        if (!bothSteel && reqMat !== prodMat && !reqMat.includes(prodMat) && !prodMat.includes(reqMat)) {
          technicalDiscrepancies.push(
            `Material distinto: pedido '${reqRow.material_type}' vs producto '${selectedProduct.material_type}'.`
          );
        }
      }
    }
    if (reqRow.diameter_mm != null) {
      if (selectedProduct.diameter_mm == null || Math.abs(selectedProduct.diameter_mm - reqRow.diameter_mm) > 0.5) {
        technicalDiscrepancies.push(
          `Diámetro distinto: pedido Ø ${reqRow.diameter_mm} mm vs producto ${
            selectedProduct.diameter_mm != null ? `Ø ${selectedProduct.diameter_mm} mm` : 'sin diámetro'
          }.`
        );
      }
    }
    const reqUnit = (reqRow.requested_unit || 'UN').toUpperCase();
    if (reqRow.length_m != null && !['M', 'MT', 'MTS', 'METRO', 'METROS'].includes(reqUnit)) {
      if (selectedProduct.length_m == null || Math.abs(selectedProduct.length_m - reqRow.length_m) > 0.05) {
        technicalDiscrepancies.push(
          `Largo distinto: pedido ${reqRow.length_m} m vs producto ${
            selectedProduct.length_m != null ? `${selectedProduct.length_m} m` : 'sin largo'
          }.`
        );
      }
    }
    if (reqRow.weight_kg != null && !['KG', 'KILO', 'KILOS'].includes(reqUnit)) {
      if (selectedProduct.weight_kg == null || Math.abs(selectedProduct.weight_kg - reqRow.weight_kg) > 0.5) {
        technicalDiscrepancies.push(
          `Peso distinto: pedido ${reqRow.weight_kg} kg vs producto ${
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
    if (requiresReason && overrideReason.trim().length < 10) {
      setOverrideError(
        'Ingresá una justificación clara (mínimo 10 caracteres) para confirmar un producto con distinta medida.'
      );
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
      setOverrideError(err instanceof Error ? err.message : 'Error al cambiar el producto');
    }
  };

  return (
    <section
      role="region"
      aria-labelledby="matrix-heading"
      className="bg-surface-elevated border border-surface-hairline rounded-container p-4 sm:p-5 shadow-card transition-colors space-y-4"
    >
      {/* Cabecera y Filtros Rápidos */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-surface-hairline gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-control bg-surface-subtle text-action-primary border border-surface-hairline">
              PASO 3
            </span>
            <h2 id="matrix-heading" className="text-base font-display font-bold text-content-primary">
              3. Comparativa de precios por corralón
            </h2>
            {isMatrixStale && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-pill bg-semantic-hitlBg border border-semantic-hitlBorder text-semantic-hitlText text-[11px] font-bold">
                <AlertTriangle className="w-3 h-3" />
                Matriz desactualizada
              </span>
            )}
          </div>
          <p className="text-[13px] text-content-secondary mt-1">
            El mejor precio de cada fila se resalta en verde. Si necesitás cambiar un producto ofrecido, hacé clic en &quot;Cambiar&quot;.
          </p>
        </div>

        {/* Barra de Filtros Rápidos */}
        <div
          role="group"
          aria-label="Filtrar materiales de la matriz"
          className="flex flex-wrap items-center gap-1.5 bg-surface-subtle p-1 rounded-control border border-surface-hairline self-start md:self-auto"
        >
          <span className="px-1.5 text-content-muted flex items-center" aria-hidden="true">
            <Filter className="w-3.5 h-3.5" />
          </span>
          <button
            type="button"
            aria-pressed={filterMode === 'all'}
            onClick={() => setFilterMode('all')}
            className={`px-3 py-1 rounded-control text-xs font-semibold transition min-h-[32px] ${
              filterMode === 'all'
                ? 'bg-surface-elevated text-content-primary font-bold shadow-card'
                : 'text-content-secondary hover:text-content-primary'
            }`}
          >
            Todos ({currentMatrix.matrix_rows.length})
          </button>
          <button
            type="button"
            aria-pressed={filterMode === 'best_price'}
            onClick={() => setFilterMode('best_price')}
            className={`px-3 py-1 rounded-control text-xs font-semibold transition min-h-[32px] ${
              filterMode === 'best_price'
                ? 'bg-surface-elevated text-content-primary font-bold shadow-card'
                : 'text-content-secondary hover:text-content-primary'
            }`}
          >
            Mejor precio
          </button>
          <button
            type="button"
            aria-pressed={filterMode === 'unavailable'}
            onClick={() => setFilterMode('unavailable')}
            className={`px-3 py-1 rounded-control text-xs font-semibold transition min-h-[32px] ${
              filterMode === 'unavailable'
                ? 'bg-surface-elevated text-content-primary font-bold shadow-card'
                : 'text-content-secondary hover:text-content-primary'
            }`}
          >
            Sin stock / No trabaja ({unavailableCount})
          </button>
        </div>
      </div>

      {isMatrixStale && (
        <div
          role="alert"
          className="p-3 rounded-control bg-semantic-hitlBg border border-semantic-hitlBorder text-semantic-hitlText text-[13px] flex flex-col sm:flex-row sm:items-center justify-between gap-2.5"
        >
          <div className="flex items-center gap-2 font-medium">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>
              <strong>Matriz desactualizada:</strong> {matrixStaleReason} No se admiten ajustes manuales ni congelamiento hasta recalcular.
            </span>
          </div>
          <button
            type="button"
            disabled={
              isComparisonLoading ||
              !currentRequisition ||
              currentRequisition.pending_clarifications_count > 0
            }
            onClick={() => {
              if (currentRequisition) {
                void runComparison(currentRequisition.id);
              }
            }}
            className="inline-flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-control bg-action-primary hover:bg-action-hover disabled:opacity-50 text-white text-xs font-bold transition min-h-[36px] shrink-0"
          >
            {isComparisonLoading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5" />
            )}
            <span>Recalcular comparativa</span>
          </button>
        </div>
      )}

      {/* Tabla con Primera Columna Adherida */}
      <div
        tabIndex={0}
        role="region"
        aria-label="Tabla comparativa de precios con desplazamiento horizontal"
        className="overflow-x-auto border border-surface-hairline rounded-control bg-surface-canvas matrix-scroll-container focus:outline-none"
      >
        <table role="grid" className="w-full text-left text-[13px] border-collapse">
          <thead>
            <tr className="border-b border-surface-hairline bg-surface-subtle text-content-secondary uppercase text-xs font-semibold tracking-wider">
              <th
                scope="col"
                className="py-3 px-3.5 min-w-[260px] sticky left-0 z-20 bg-surface-elevated border-r border-surface-hairline shadow-[2px_0_4px_rgba(0,0,0,0.04)]"
              >
                Material solicitado
              </th>
              <th scope="col" className="py-3 px-2 text-center min-w-[78px]">
                Cant.
              </th>
              {currentMatrix.vendors.map((v) => (
                <th
                  key={v.vendor_id}
                  scope="col"
                  className="py-3 px-3 text-right min-w-[220px] border-l border-surface-hairline"
                >
                  <div className="font-bold text-content-primary truncate">{v.vendor_name}</div>
                  <div className="text-xs text-content-muted font-normal mt-0.5 normal-case">
                    {v.locality} · Cobertura:{' '}
                    <span className="font-mono tabular-nums font-bold text-content-secondary">
                      {v.coverage_pct}%
                    </span>
                  </div>
                  <div className="w-full bg-surface-canvas h-1.5 rounded-pill mt-1.5 overflow-hidden">
                    <div
                      className="bg-emerald-600 dark:bg-emerald-500 h-full rounded-pill transition-all"
                      style={{ width: `${v.coverage_pct}%` }}
                    />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-hairline">
            {filteredRows.length === 0 ? (
              <tr>
                <td
                  colSpan={2 + currentMatrix.vendors.length}
                  className="py-8 px-4 text-center text-[13px] text-content-secondary space-y-2"
                >
                  <p>No hay materiales que coincidan con el filtro seleccionado.</p>
                  <button
                    type="button"
                    onClick={() => setFilterMode('all')}
                    className="inline-flex items-center px-3 py-1.5 rounded-control bg-surface-elevated border border-surface-hairline text-xs font-bold text-action-primary hover:bg-surface-subtle"
                  >
                    Ver todos los materiales
                  </button>
                </td>
              </tr>
            ) : (
              filteredRows.map((row) => (
                <tr key={row.requisition_item_id} className="hover:bg-surface-subtle/30 transition-colors">
                  <td className="py-3 px-3.5 sticky left-0 z-10 bg-surface-elevated border-r border-surface-hairline shadow-[2px_0_4px_rgba(0,0,0,0.04)]">
                    <div className="font-bold text-content-primary text-[13px]">{row.requested_term}</div>
                    <div className="text-xs text-content-secondary flex flex-wrap items-center gap-1.5 mt-1">
                      {row.diameter_mm != null && (
                        <span className="px-2 py-0.5 rounded-pill bg-surface-subtle border border-surface-hairline text-[11px] font-mono tabular-nums">
                          Ø {row.diameter_mm} mm
                        </span>
                      )}
                      {row.material_type && (
                        <span className="px-2 py-0.5 rounded-pill bg-surface-subtle border border-surface-hairline text-[11px] font-medium">
                          {row.material_type}
                        </span>
                      )}
                    </div>
                  </td>

                  <td className="py-3 px-2 text-center font-mono tabular-nums text-content-primary font-bold">
                    {row.quantity}{' '}
                    <span className="text-xs text-content-muted font-sans font-normal">
                      {row.requested_unit}
                    </span>
                  </td>

                  {row.vendor_cells.map((cell) => {
                    const isNotCarried = cell.match_status === 'NOT_CARRIED';
                    const isOutOfStock = cell.match_status === 'OUT_OF_STOCK';
                    const isAmbiguous = cell.match_status === 'AMBIGUOUS_CANDIDATES';
                    const isBest = cell.is_best_price;
                    const isSplitWinner = cell.is_selected_split;
                    const showConversionPill =
                      !!cell.conversion_note ||
                      (cell.commercial_qty != null &&
                        !!cell.sale_unit &&
                        cell.commercial_qty !== row.quantity);

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
                          <div className="inline-flex flex-col items-end gap-0.5">
                            <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-pill bg-surface-elevated text-content-secondary border border-surface-hairline font-bold shadow-card">
                              <Ban className="w-3.5 h-3.5 text-action-danger" />
                              [NO TRABAJA MEDIDA]
                            </span>
                            <span className="text-xs text-content-muted mt-0.5">
                              Sin esa medida en lista
                            </span>
                          </div>
                        ) : isAmbiguous ? (
                          <div className="inline-flex flex-col items-end gap-1">
                            <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-pill bg-semantic-hitlBg text-semantic-hitlText border border-semantic-hitlBorder font-bold">
                              <AlertTriangle className="w-3.5 h-3.5" />
                              [AMBIGUO - DEFINIR]
                            </span>
                            {!isLocked && !isMatrixStale && (
                              <button
                                onClick={() => void handleOpenOverride(cell, row)}
                                type="button"
                                className="inline-flex items-center gap-1 text-xs text-action-primary hover:underline font-bold"
                              >
                                <Edit3 className="w-3 h-3" /> Elegir producto
                              </button>
                            )}
                          </div>
                        ) : isOutOfStock ? (
                          <div className="inline-flex flex-col items-end">
                            <span className="text-xs px-2.5 py-0.5 rounded-pill bg-semantic-hitlBg text-semantic-hitlText border border-semantic-hitlBorder font-bold">
                              [SIN STOCK EN CORRALÓN]
                            </span>
                          </div>
                        ) : cell.line_subtotal_ars !== null && cell.line_subtotal_ars !== undefined ? (
                          <div className="group relative space-y-1">
                            <div
                              className={`font-mono font-bold text-sm tabular-nums ${
                                isBest ? 'text-semantic-winnerText' : 'text-content-primary'
                              }`}
                            >
                              $ {cell.line_subtotal_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                            </div>
                            <div className="text-xs font-mono text-content-muted tabular-nums">
                              $ {cell.unit_price_ars?.toLocaleString('es-AR', { minimumFractionDigits: 2 })} /{' '}
                              {cell.sale_unit || row.requested_unit}
                            </div>

                            {showConversionPill && (
                              <div className="flex justify-end">
                                <span
                                  className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-pill bg-semantic-infoBg text-semantic-infoText"
                                  title="Equivalencia comercial por formato de venta"
                                >
                                  <Package className="w-3 h-3 shrink-0" />
                                  <span>
                                    {cell.conversion_note || `${cell.commercial_qty} ${cell.sale_unit}`}
                                  </span>
                                </span>
                              </div>
                            )}

                            <div className="flex flex-wrap items-center justify-end gap-1.5 pt-0.5">
                              {isBest && (
                                <span className="inline-flex items-center gap-0.5 text-[11px] px-2 py-0.5 rounded-pill bg-emerald-600/15 text-semantic-winnerText font-bold uppercase">
                                  <Check className="w-3 h-3" /> Mejor
                                </span>
                              )}
                              {isSplitWinner && (
                                <span className="inline-flex items-center gap-0.5 text-[11px] px-2 py-0.5 rounded-pill bg-action-primary/10 text-action-primary font-bold">
                                  <ShoppingBag className="w-3 h-3" /> Compra mixta
                                </span>
                              )}
                              {cell.override_audit && (
                                <span className="inline-flex items-center text-[11px] px-2 py-0.5 rounded-pill bg-semantic-hitlBg text-semantic-hitlText font-semibold">
                                  Ajuste manual
                                </span>
                              )}
                              {!isLocked && !isMatrixStale && (
                                <button
                                  onClick={() => void handleOpenOverride(cell, row)}
                                  type="button"
                                  className="sm:opacity-0 sm:group-hover:opacity-100 focus:opacity-100 transition inline-flex items-center gap-1 text-xs text-content-secondary hover:text-action-primary underline underline-offset-2 ml-1 font-semibold"
                                  title="Cambiar producto asignado"
                                >
                                  <Edit3 className="w-3 h-3" /> Cambiar
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
              ))
            )}
          </tbody>

          {/* Totales y Fletes */}
          <tfoot className="border-t-2 border-surface-hairline bg-surface-subtle text-[13px]">
            <tr>
              <th
                scope="row"
                className="py-2.5 px-3.5 sticky left-0 z-20 bg-surface-subtle text-content-primary font-bold border-r border-surface-hairline"
              >
                Flete estimado del corralón
              </th>
              <td className="text-center font-bold text-content-muted">-</td>
              {currentMatrix.vendors.map((v) => (
                <td
                  key={v.vendor_id}
                  className="py-2.5 px-3 text-right font-mono tabular-nums text-content-secondary border-l border-surface-hairline"
                >
                  <span className="inline-flex items-center gap-1.5">
                    <Truck className="w-3.5 h-3.5 text-content-muted" />+ ${' '}
                    {v.delivery_fee_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                  </span>
                </td>
              ))}
            </tr>
            <tr className="border-t border-surface-hairline font-bold">
              <th
                scope="row"
                className="py-3 px-3.5 sticky left-0 z-20 bg-surface-subtle text-content-primary font-bold border-r border-surface-hairline"
              >
                Total comprando todo en este corralón
              </th>
              <td className="text-center font-bold text-content-muted">-</td>
              {currentMatrix.vendors.map((v) => (
                <td
                  key={v.vendor_id}
                  className="py-3 px-3 text-right font-mono tabular-nums text-sm text-content-primary border-l border-surface-hairline font-extrabold"
                >
                  $ {v.total_with_delivery_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Inspector Lateral para Cambiar Producto */}
      <dialog
        ref={dialogRef}
        aria-labelledby="override-drawer-title"
        onClose={handleCloseDrawer}
        className="fixed inset-y-0 right-0 m-0 ml-auto h-full max-h-screen w-full max-w-md bg-surface-elevated border-l border-surface-hairline p-0 text-content-primary shadow-modal backdrop:bg-black/50 backdrop:backdrop-blur-sm focus:outline-none"
      >
        {overrideCell && (
          <div className="flex flex-col h-full">
            <div className="p-4 border-b border-surface-hairline flex items-center justify-between bg-surface-subtle">
              <div>
                <span className="text-xs font-semibold uppercase text-content-muted">
                  Cambiar producto ofrecido
                </span>
                <h3 id="override-drawer-title" className="text-base font-bold text-content-primary mt-0.5">
                  {overrideCell.cell.vendor_name}
                </h3>
              </div>
              <button
                onClick={handleCloseDrawer}
                type="button"
                className="p-2 rounded-control hover:bg-surface-elevated text-content-secondary hover:text-content-primary transition min-h-[38px] min-w-[38px] flex items-center justify-center"
                aria-label="Cerrar selector de producto"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 bg-surface-canvas border-b border-surface-hairline text-[13px] space-y-1">
              <div className="text-content-muted text-xs">Material pedido en tu lista:</div>
              <div className="font-bold text-content-primary text-sm">{overrideCell.row.requested_term}</div>
              <div className="text-xs font-mono text-content-secondary flex flex-wrap gap-2">
                {overrideCell.row.material_type && (
                  <span>
                    Material: <strong>{overrideCell.row.material_type}</strong>
                  </span>
                )}
                {overrideCell.row.diameter_mm != null && (
                  <span>
                    Ø <strong>{overrideCell.row.diameter_mm} mm</strong>
                  </span>
                )}
                {overrideCell.row.length_m != null && (
                  <span>
                    Largo: <strong>{overrideCell.row.length_m} m</strong>
                  </span>
                )}
                {overrideCell.row.weight_kg != null && (
                  <span>
                    Peso: <strong>{overrideCell.row.weight_kg} kg</strong>
                  </span>
                )}
              </div>
            </div>

            {overrideError && (
              <div
                role="alert"
                className="m-4 p-3 rounded-control bg-semantic-dangerBg border border-semantic-dangerBorder text-[13px] text-semantic-dangerText font-medium flex items-start gap-2"
              >
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{overrideError}</span>
              </div>
            )}

            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              <span className="text-xs font-bold uppercase text-content-secondary tracking-wider block mb-2">
                Lista de precios de este corralón ({vendorProducts.length} artículos):
              </span>

              {loadingProducts ? (
                <div className="py-12 text-center text-content-secondary text-[13px] flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-action-primary" />
                  <span>Cargando productos del corralón...</span>
                </div>
              ) : vendorProducts.length === 0 ? (
                <div className="py-8 text-center text-[13px] text-content-muted">
                  No hay productos cargados para este corralón.
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
                      className={`w-full text-left p-3 rounded-control border text-[13px] transition flex items-start justify-between gap-3 ${
                        isSelected
                          ? 'border-action-primary bg-action-primary/5 shadow-card'
                          : 'border-surface-hairline bg-surface-canvas hover:border-surface-strong'
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="font-bold text-content-primary">{p.raw_description}</div>
                        <div className="text-xs text-content-muted font-mono flex flex-wrap items-center gap-2">
                          <span>Código: {p.sku}</span>
                          {p.diameter_mm != null && <span>Ø {p.diameter_mm} mm</span>}
                          {p.brand && <span>{p.brand}</span>}
                        </div>
                        {isCurrentAssigned && (
                          <span className="inline-block px-2 py-0.5 rounded-pill bg-surface-subtle border border-surface-hairline text-[11px] text-content-secondary font-semibold">
                            Seleccionado actualmente
                          </span>
                        )}
                      </div>
                      <div className="text-right font-mono font-bold text-content-primary tabular-nums shrink-0">
                        $ {p.price_cash_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                      </div>
                    </button>
                  );
                })
              )}
            </div>

            {/* Alerta de diferencia de medida o material */}
            {hasDimensionMismatch && (
              <div className="p-4 bg-semantic-hitlBg border-t border-semantic-hitlBorder text-[13px] text-semantic-hitlText space-y-2">
                <div className="flex items-start gap-2 font-bold">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>Diferencia de medida o material ({technicalDiscrepancies.length})</span>
                </div>
                <ul className="list-disc pl-4 space-y-0.5 text-xs leading-relaxed">
                  {technicalDiscrepancies.map((disc, idx) => (
                    <li key={idx}>{disc}</li>
                  ))}
                </ul>
                <label className="flex items-center gap-2 pt-1 text-xs font-bold cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={forceOverride}
                    onChange={(e) => setForceOverride(e.target.checked)}
                    className="rounded border-surface-strong text-action-primary focus:ring-action-focus w-4 h-4"
                  />
                  <span>Confirmar este reemplazo bajo mi criterio de obra</span>
                </label>
                {forceOverride && (
                  <div className="pt-1 space-y-1">
                    <label htmlFor="override-reason-input" className="block text-xs font-bold">
                      Motivo del reemplazo (mínimo 10 caracteres):
                    </label>
                    <input
                      id="override-reason-input"
                      type="text"
                      minLength={10}
                      value={overrideReason}
                      onChange={(e) => setOverrideReason(e.target.value)}
                      placeholder="Ej.: Aprobado por dirección de obra por falta en plaza..."
                      className="w-full h-9 px-2.5 rounded-control border border-surface-strong bg-surface-canvas text-content-primary text-[13px] focus:outline-none"
                    />
                  </div>
                )}
              </div>
            )}

            <div className="p-4 border-t border-surface-hairline bg-surface-subtle flex items-center justify-end gap-2">
              <button
                onClick={handleCloseDrawer}
                type="button"
                className="px-4 py-2 rounded-control border border-surface-hairline bg-surface-elevated text-content-secondary hover:text-content-primary text-[13px] font-semibold transition min-h-[40px]"
              >
                Cancelar
              </button>
              <button
                onClick={() => void handleConfirmOverride()}
                disabled={
                  savingOverride ||
                  !selectedProductId ||
                  (hasDimensionMismatch && (!forceOverride || overrideReason.trim().length < 10))
                }
                type="button"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-control bg-action-primary hover:bg-action-hover disabled:opacity-55 text-white font-bold text-[13px] shadow-card transition min-h-[40px]"
              >
                {savingOverride ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Guardando cambio...</span>
                  </>
                ) : (
                  <span>Confirmar Cambio</span>
                )}
              </button>
            </div>
          </div>
        )}
      </dialog>
    </section>
  );
};
