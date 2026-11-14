import React, { useEffect, useRef, useState } from 'react';
import { useRequisitionStore } from '../store/useRequisitionStore';
import { getMatrixRequisitionStaleReason, useComparisonStore } from '../store/useComparisonStore';
import {
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Save,
  Layers,
  HelpCircle,
  RefreshCw,
} from 'lucide-react';
import { RequisitionItemResponse } from '../types/api';

interface DisambiguationTableProps {
  onProceedToCompare: () => void;
}

const MATERIAL_OPTIONS = [
  { label: 'PVC Cloacal / Agua', value: 'PVC' },
  { label: 'Termofusión', value: 'Termofusión' },
  { label: 'Polipropileno', value: 'Polipropileno' },
  { label: 'Corrugado', value: 'Corrugado' },
  { label: 'Hierro Estructural', value: 'Hierro estructural' },
];

const DIAMETER_OPTIONS = [
  { label: '1/2"', sublabel: '12.7 mm', value: 12.7 },
  { label: '3/4"', sublabel: '19.05 mm', value: 19.05 },
  { label: '1"', sublabel: '25.4 mm', value: 25.4 },
  { label: '40 mm', sublabel: 'Desagüe', value: 40 },
  { label: '110 mm', sublabel: 'Cloacal', value: 110 },
];

const STANDARD_UNITS = ['UN', 'BARRA', 'BOLSA', 'M', 'KG', 'M2', 'M3'];

interface PendingDraftSelection {
  materialValue?: string;
  materialLabel?: string;
  diameterMm?: number;
  diameterLabel?: string;
}

export const DisambiguationTable: React.FC<DisambiguationTableProps> = ({ onProceedToCompare }) => {
  const { currentRequisition, resolveItem, isLoading, error: reqError } = useRequisitionStore();
  const { runComparison, currentMatrix, lockedBudget, error: compError } = useComparisonStore();

  const [saveAsAliasMap, setSaveAsAliasMap] = useState<Record<string, boolean>>({});
  const [draftSelections, setDraftSelections] = useState<Record<string, PendingDraftSelection>>({});
  const [qtyDrafts, setQtyDrafts] = useState<Record<string, string>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const firstAmbiguousButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!currentRequisition) {
      setQtyDrafts({});
      setDraftSelections({});
      return;
    }
    const nextQtyDrafts: Record<string, string> = {};
    for (const item of currentRequisition.items) {
      nextQtyDrafts[item.id] = String(item.quantity);
    }
    setQtyDrafts(nextQtyDrafts);
  }, [currentRequisition]);

  if (!currentRequisition) return null;

  const items = currentRequisition.items;
  const pendingCount = currentRequisition.pending_clarifications_count;
  const allResolved = pendingCount === 0;
  const isLocked = !!lockedBudget || currentMatrix?.status === 'LOCKED_BUDGET' || !!currentMatrix?.is_locked;
  const matrixStaleReason = getMatrixRequisitionStaleReason(currentMatrix, currentRequisition);
  const firstPendingItemId = items.find((it) => it.completeness === 'missing_critical_attribute')?.id;

  const submitItemResolution = async (
    item: RequisitionItemResponse,
    materialValue?: string,
    materialLabel?: string,
    diameterMm?: number,
    diameterLabel?: string
  ) => {
    setActionError(null);
    const saveAlias = !!saveAsAliasMap[item.id];
    const extraParts = [materialLabel, diameterLabel].filter(Boolean).join(' ');
    const confirmedTerm = `${item.requested_term} ${extraParts}`.trim();

    try {
      await resolveItem(item.id, {
        material_type: materialValue ?? item.material_type ?? undefined,
        diameter_mm: diameterMm ?? item.diameter_mm ?? undefined,
        confirmed_term: confirmedTerm,
        save_as_alias: saveAlias,
      });
      setDraftSelections((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
    } catch (err: unknown) {
      setActionError(
        err instanceof Error ? err.message : 'No se pudo guardar la aclaración del material.'
      );
    }
  };

  const handleSelectMaterial = async (
    item: RequisitionItemResponse,
    materialValue: string,
    materialLabel: string
  ) => {
    const needsDiameter = item.diameter_mm == null;
    const currentDraft = draftSelections[item.id] || {};
    const selectedDiameter = currentDraft.diameterMm;

    if (needsDiameter && selectedDiameter == null) {
      setDraftSelections((prev) => ({
        ...prev,
        [item.id]: {
          ...prev[item.id],
          materialValue,
          materialLabel,
        },
      }));
      return;
    }

    await submitItemResolution(
      item,
      materialValue,
      materialLabel,
      selectedDiameter ?? item.diameter_mm ?? undefined,
      currentDraft.diameterLabel
    );
  };

  const handleSelectDiameter = async (
    item: RequisitionItemResponse,
    diameterMm: number,
    diameterLabel: string
  ) => {
    const needsMaterial = !item.material_type;
    const currentDraft = draftSelections[item.id] || {};
    const selectedMaterial = currentDraft.materialValue;

    if (needsMaterial && !selectedMaterial) {
      setDraftSelections((prev) => ({
        ...prev,
        [item.id]: {
          ...prev[item.id],
          diameterMm,
          diameterLabel,
        },
      }));
      return;
    }

    await submitItemResolution(
      item,
      selectedMaterial ?? item.material_type ?? undefined,
      currentDraft.materialLabel,
      diameterMm,
      diameterLabel
    );
  };

  const handleQuantityCommit = async (item: RequisitionItemResponse) => {
    const rawVal = qtyDrafts[item.id];
    const parsed = Number(rawVal);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setQtyDrafts((prev) => ({ ...prev, [item.id]: String(item.quantity) }));
      return;
    }
    if (Math.abs(parsed - item.quantity) < 1e-6) return;

    setActionError(null);
    try {
      await resolveItem(item.id, {
        quantity: parsed,
        save_as_alias: false,
      });
    } catch (err: unknown) {
      setQtyDrafts((prev) => ({ ...prev, [item.id]: String(item.quantity) }));
      setActionError(err instanceof Error ? err.message : 'No se pudo actualizar la cantidad.');
    }
  };

  const handleUnitChange = async (item: RequisitionItemResponse, nextUnit: string) => {
    if (nextUnit === item.requested_unit) return;
    setActionError(null);
    try {
      await resolveItem(item.id, {
        requested_unit: nextUnit,
        save_as_alias: false,
      });
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'No se pudo actualizar la unidad.');
    }
  };

  const handleStartComparison = async () => {
    setActionError(null);
    if (!allResolved) {
      if (firstAmbiguousButtonRef.current) {
        firstAmbiguousButtonRef.current.focus();
      }
      return;
    }
    try {
      await runComparison(currentRequisition.id);
      onProceedToCompare();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Error al ejecutar la comparativa.');
    }
  };

  return (
    <section
      role="region"
      aria-labelledby="disambiguation-heading"
      className="bg-surface-elevated border border-surface-hairline rounded-container p-4 sm:p-5 shadow-card transition-colors space-y-4"
    >
      {/* Cabecera */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-surface-hairline gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-control bg-surface-subtle text-action-primary border border-surface-hairline">
              PASO 2
            </span>
            <h2
              id="disambiguation-heading"
              className="text-base font-display font-bold text-content-primary"
            >
              2. Confirmar medidas y materiales
            </h2>
          </div>
          <p className="text-[13px] text-content-secondary mt-1">
            Verificamos que cada material tenga su medida y tipo exacto antes de comparar precios.
          </p>
        </div>

        {/* Estado accesible */}
        <div aria-live="polite" aria-atomic="true">
          {allResolved ? (
            <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-pill text-xs font-bold bg-semantic-winnerBg text-semantic-winnerText border border-emerald-600/25 shadow-card">
              <CheckCircle2 className="w-4 h-4 text-semantic-winnerText" />
              <span>Pliego Completo ({items.length} ítems verificados)</span>
            </div>
          ) : (
            <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-pill text-xs font-bold bg-semantic-hitlBg border border-semantic-hitlBorder text-semantic-hitlText shadow-card motion-safe:animate-pulse">
              <AlertTriangle className="w-4 h-4" />
              <span>
                {pendingCount} ítem{pendingCount > 1 ? 's' : ''} requiere{pendingCount > 1 ? 'n' : ''} definir material
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Tabla de Renglones */}
      <div className="overflow-x-auto border border-surface-hairline rounded-control bg-surface-canvas">
        <table className="w-full text-left text-[13px] border-collapse">
          <thead>
            <tr className="border-b border-surface-hairline bg-surface-subtle text-content-secondary uppercase text-xs font-semibold tracking-wider">
              <th scope="col" className="py-2.5 px-3 w-10">#</th>
              <th scope="col" className="py-2.5 px-3">Material solicitado</th>
              <th scope="col" className="py-2.5 px-3 text-center">Cantidad y unidad</th>
              <th scope="col" className="py-2.5 px-3">Medida</th>
              <th scope="col" className="py-2.5 px-3">Material</th>
              <th scope="col" className="py-2.5 px-3">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-hairline">
            {items.map((item) => {
              const isPending = item.completeness === 'missing_critical_attribute';
              const needsMaterial = !item.material_type;
              const needsDiameter = item.diameter_mm == null;
              const draft = draftSelections[item.id] || {};
              const unitOptions = STANDARD_UNITS.includes(item.requested_unit)
                ? STANDARD_UNITS
                : [item.requested_unit, ...STANDARD_UNITS];
              const isFirstPendingItem = item.id === firstPendingItemId;

              return (
                <React.Fragment key={item.id}>
                  <tr
                    className={`transition-colors ${
                      isPending ? 'bg-semantic-hitlBg/25' : 'hover:bg-surface-subtle/50'
                    }`}
                  >
                    <td className="py-2.5 px-3 text-content-muted font-semibold">{item.line_order}</td>
                    <td className="py-2.5 px-3 font-medium text-content-primary">{item.raw_line}</td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center justify-center gap-1.5">
                        <input
                          type="number"
                          min="0.01"
                          step="any"
                          disabled={isLoading || isLocked}
                          value={qtyDrafts[item.id] ?? String(item.quantity)}
                          onChange={(e) =>
                            setQtyDrafts((prev) => ({ ...prev, [item.id]: e.target.value }))
                          }
                          onBlur={() => void handleQuantityCommit(item)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.currentTarget.blur();
                            }
                          }}
                          aria-label={`Cantidad para ${item.raw_line}`}
                          className="w-16 h-8 px-2 rounded-control bg-surface-elevated border border-surface-hairline focus:border-surface-strong text-center text-[13px] font-mono tabular-nums text-content-primary disabled:opacity-60"
                        />
                        <select
                          disabled={isLoading || isLocked}
                          value={item.requested_unit}
                          onChange={(e) => void handleUnitChange(item, e.target.value)}
                          aria-label={`Unidad para ${item.raw_line}`}
                          className="h-8 px-1.5 rounded-control bg-surface-elevated border border-surface-hairline focus:border-surface-strong text-xs font-semibold text-content-secondary disabled:opacity-60"
                        >
                          {unitOptions.map((u) => (
                            <option key={u} value={u}>
                              {u}
                            </option>
                          ))}
                        </select>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[13px] tabular-nums text-content-secondary whitespace-nowrap">
                      {item.diameter_mm ? `Ø ${item.diameter_mm} mm` : ''}
                      {item.diameter_inch ? ` (${item.diameter_inch}")` : ''}
                      {item.length_m ? ` × ${item.length_m} m` : ''}
                      {item.weight_kg ? ` [${item.weight_kg} kg]` : ''}
                      {!item.diameter_mm && !item.weight_kg && !item.length_m ? (
                        isPending && needsDiameter ? (
                          <span className="text-semantic-hitlText font-sans font-bold text-xs">
                            Falta medida
                          </span>
                        ) : (
                          '-'
                        )
                      ) : (
                        ''
                      )}
                    </td>
                    <td className="py-2.5 px-3">
                      {item.material_type ? (
                        <span className="px-2.5 py-0.5 rounded-pill bg-surface-elevated text-content-primary border border-surface-hairline text-xs font-semibold">
                          {item.material_type}
                        </span>
                      ) : (
                        <span className="text-semantic-hitlText font-bold text-xs inline-flex items-center gap-1">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          <span>Por definir</span>
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3">
                      {isPending ? (
                        <span className="px-2.5 py-0.5 rounded-pill bg-semantic-hitlBg text-semantic-hitlText font-semibold text-xs border border-semantic-hitlBorder inline-block">
                          Por definir
                        </span>
                      ) : (
                        <span className="px-2.5 py-0.5 rounded-pill bg-semantic-winnerBg text-semantic-winnerText font-semibold text-xs border border-emerald-600/25 inline-block">
                          Listo
                        </span>
                      )}
                    </td>
                  </tr>

                  {/* Fila de Aclaración en Línea */}
                  {isPending && (
                    <tr className="bg-semantic-hitlBg/45 border-b border-semantic-hitlBorder">
                      <td colSpan={6} className="py-3.5 px-4">
                        <div className="space-y-3">
                          <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
                            <p className="text-[13px] text-semantic-hitlText font-semibold flex items-center gap-1.5">
                              <Layers className="w-4 h-4 shrink-0" />
                              <span>
                                {item.clarification_prompt ||
                                  'Elegí el material o la medida exacta para comparar sin errores:'}
                              </span>
                            </p>
                            <label className="flex items-center gap-1.5 text-xs text-content-secondary cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={!!saveAsAliasMap[item.id]}
                                onChange={(e) =>
                                  setSaveAsAliasMap({ ...saveAsAliasMap, [item.id]: e.target.checked })
                                }
                                className="rounded border-surface-strong text-action-primary focus:ring-action-focus w-4 h-4"
                              />
                              <Save className="w-3.5 h-3.5 text-content-muted" />
                              <span>Recordar esta elección para próximos pedidos</span>
                            </label>
                          </div>

                          {/* Selección de Material */}
                          {(needsMaterial || !needsDiameter) && (
                            <div className="space-y-1.5">
                              {needsDiameter && (
                                <span className="block text-xs font-bold text-content-secondary">
                                  1) Tipo de material:
                                </span>
                              )}
                              <div
                                role="group"
                                aria-label={`Opciones de material para ${item.raw_line}`}
                                className="flex flex-wrap items-center gap-2"
                              >
                                {MATERIAL_OPTIONS.map((mat, btnIdx) => {
                                  const isDraftPicked = draft.materialValue === mat.value;
                                  return (
                                    <button
                                      key={mat.value}
                                      ref={
                                        isFirstPendingItem && btnIdx === 0
                                          ? firstAmbiguousButtonRef
                                          : undefined
                                      }
                                      onClick={() =>
                                        void handleSelectMaterial(item, mat.value, mat.label)
                                      }
                                      disabled={isLoading}
                                      type="button"
                                      aria-pressed={isDraftPicked}
                                      className={`px-3.5 py-1.5 rounded-control border text-[13px] font-semibold transition shadow-card min-h-[38px] ${
                                        isDraftPicked
                                          ? 'bg-action-primary text-white border-action-primary'
                                          : 'bg-surface-elevated hover:bg-semantic-hitlBg text-content-primary hover:text-semantic-hitlText border-surface-hairline hover:border-semantic-hitlBorder'
                                      }`}
                                    >
                                      {mat.label}
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                          )}

                          {/* Selección de Diámetro cuando diameter_mm === null */}
                          {needsDiameter && (
                            <div className="space-y-1.5">
                              <span className="block text-xs font-bold text-content-secondary">
                                {needsMaterial ? '2) Diámetro o medida:' : 'Elegí el diámetro exacto:'}
                              </span>
                              <div
                                role="group"
                                aria-label={`Opciones de diámetro para ${item.raw_line}`}
                                className="flex flex-wrap items-center gap-2"
                              >
                                {DIAMETER_OPTIONS.map((diam, diamIdx) => {
                                  const isDraftPicked = draft.diameterMm === diam.value;
                                  const attachRef =
                                    isFirstPendingItem && !needsMaterial && diamIdx === 0
                                      ? firstAmbiguousButtonRef
                                      : undefined;

                                  return (
                                    <button
                                      key={diam.value}
                                      ref={attachRef}
                                      onClick={() =>
                                        void handleSelectDiameter(item, diam.value, diam.label)
                                      }
                                      disabled={isLoading}
                                      type="button"
                                      aria-pressed={isDraftPicked}
                                      className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-control border text-[13px] font-semibold transition shadow-card min-h-[38px] ${
                                        isDraftPicked
                                          ? 'bg-action-primary text-white border-action-primary'
                                          : 'bg-surface-elevated hover:bg-semantic-hitlBg text-content-primary hover:text-semantic-hitlText border-surface-hairline hover:border-semantic-hitlBorder'
                                      }`}
                                    >
                                      <span className="font-mono font-bold">{diam.label}</span>
                                      <span className="text-xs opacity-80">({diam.sublabel})</span>
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {(actionError || reqError || compError) && (
        <div
          role="alert"
          className="p-3 rounded-control bg-semantic-dangerBg border border-semantic-dangerBorder text-semantic-dangerText text-[13px] font-medium"
        >
          {actionError || compError || reqError}
        </div>
      )}

      {matrixStaleReason && !isLocked && (
        <div
          role="status"
          className="p-3 rounded-control bg-semantic-hitlBg border border-semantic-hitlBorder text-semantic-hitlText text-[13px] flex flex-col sm:flex-row sm:items-center justify-between gap-2.5"
        >
          <div className="flex items-center gap-2 font-medium">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>
              <strong>Comparativa desactualizada:</strong> {matrixStaleReason}
            </span>
          </div>
          {allResolved && (
            <button
              type="button"
              disabled={isLoading}
              onClick={handleStartComparison}
              className="inline-flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-control bg-action-primary hover:bg-action-hover disabled:opacity-50 text-white text-xs font-bold transition min-h-[36px] shrink-0"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Recalcular comparativa</span>
            </button>
          )}
        </div>
      )}

      {/* Acción de Ejecución */}
      <div className="pt-3 border-t border-surface-hairline flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="text-[13px] text-content-secondary flex items-center gap-1.5">
          <HelpCircle className="w-4 h-4 text-content-muted shrink-0" />
          <span>
            {allResolved
              ? 'Todas las medidas y materiales están confirmados. Listo para comparar corralones.'
              : 'Completá los materiales pendientes arriba antes de comparar precios.'}
          </span>
        </div>

        <button
          onClick={handleStartComparison}
          disabled={isLoading}
          aria-disabled={!allResolved}
          type="button"
          className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-control font-bold text-[13px] shadow-card transition min-h-[44px] ${
            allResolved
              ? 'bg-action-primary hover:bg-action-hover text-white cursor-pointer'
              : 'bg-surface-subtle text-content-muted border border-surface-hairline cursor-not-allowed opacity-70'
          }`}
          title={!allResolved ? 'Debés resolver los ítems pendientes antes de comparar' : 'Ejecutar comparativa'}
        >
          <span>Ejecutar Compulsa Multi-Corralón</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </section>
  );
};
