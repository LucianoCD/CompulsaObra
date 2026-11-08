import React, { useRef, useState } from 'react';
import { useRequisitionStore } from '../store/useRequisitionStore';
import { useComparisonStore } from '../store/useComparisonStore';
import {
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Save,
  Layers,
  HelpCircle,
} from 'lucide-react';
import { RequisitionItemResponse } from '../types/api';

interface DisambiguationTableProps {
  onProceedToCompare: () => void;
}

export const DisambiguationTable: React.FC<DisambiguationTableProps> = ({ onProceedToCompare }) => {
  const { currentRequisition, resolveItem, isLoading } = useRequisitionStore();
  const { runComparison } = useComparisonStore();

  const [saveAsAliasMap, setSaveAsAliasMap] = useState<Record<string, boolean>>({});
  const firstAmbiguousButtonRef = useRef<HTMLButtonElement | null>(null);

  if (!currentRequisition) return null;

  const items = currentRequisition.items;
  const pendingCount = currentRequisition.pending_clarifications_count;
  const allResolved = pendingCount === 0;

  const handleQuickResolve = (item: RequisitionItemResponse, materialValue: string, materialLabel: string) => {
    const saveAlias = !!saveAsAliasMap[item.id];
    const confirmedTerm = `${item.requested_term} ${materialLabel}`.trim();

    resolveItem(item.id, {
      material_type: materialValue,
      confirmed_term: confirmedTerm,
      save_as_alias: saveAlias,
    });
  };

  const handleStartComparison = async () => {
    if (!allResolved) {
      // ISO/IEC 25010 & WCAG 3.3.4: Guiar el foco al primer botón ambiguo
      if (firstAmbiguousButtonRef.current) {
        firstAmbiguousButtonRef.current.focus();
      }
      return;
    }
    await runComparison(currentRequisition.id);
    onProceedToCompare();
  };

  return (
    <section
      role="region"
      aria-labelledby="disambiguation-heading"
      className="bg-surface-elevated border border-surface-hairline rounded-container p-4 sm:p-5 transition-colors space-y-4"
    >
      {/* Cabecera Técnica */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-surface-hairline gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-control bg-surface-subtle text-action-primary border border-surface-hairline">
              PASO 02
            </span>
            <h2 id="disambiguation-heading" className="text-sm sm:text-base font-display font-bold text-content-primary">
              Guardia Dimensional y Consola Human-in-the-Loop
            </h2>
          </div>
          <p className="text-xs text-content-secondary mt-1">
            Validación física estricta antes de cotizar. Cero sustitución ciega en corralones.
          </p>
        </div>

        {/* Indicador de Estado Accesible con Live Region */}
        <div aria-live="polite" aria-atomic="true">
          {allResolved ? (
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-control text-xs font-bold bg-semantic-winnerBg text-semantic-winnerText border border-surface-hairline shadow-sm">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              <span>Pliego Completo ({items.length} ítems verificados)</span>
            </div>
          ) : (
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-control text-xs font-bold bg-semantic-hitlBg border border-semantic-hitlBorder text-semantic-hitlText shadow-sm animate-pulse">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>
                {pendingCount} ítem{pendingCount > 1 ? 's' : ''} requiere{pendingCount > 1 ? 'n' : ''} definir material
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Tabla de Renglones Técnicos */}
      <div className="overflow-x-auto border border-surface-hairline rounded-control bg-surface-canvas">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-surface-hairline bg-surface-subtle text-content-secondary uppercase text-[11px] font-semibold tracking-wider">
              <th scope="col" className="py-2.5 px-3 w-10">#</th>
              <th scope="col" className="py-2.5 px-3">Renglón Extraído</th>
              <th scope="col" className="py-2.5 px-3 text-center">Cantidad</th>
              <th scope="col" className="py-2.5 px-3">Dimensión Física</th>
              <th scope="col" className="py-2.5 px-3">Material Normalizado</th>
              <th scope="col" className="py-2.5 px-3">Estado Técnico</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-hairline font-mono">
            {items.map((item, index) => {
              const isPending = item.completeness === 'missing_critical_attribute';

              return (
                <React.Fragment key={item.id}>
                  <tr
                    className={`transition-colors ${
                      isPending ? 'bg-semantic-hitlBg/25' : 'hover:bg-surface-subtle/50'
                    }`}
                  >
                    <td className="py-2.5 px-3 text-content-muted font-sans font-semibold">{item.line_order}</td>
                    <td className="py-2.5 px-3 font-medium text-content-primary font-sans">
                      {item.raw_line}
                    </td>
                    <td className="py-2.5 px-3 text-center tabular-nums text-content-primary">
                      {item.quantity} {item.requested_unit}
                    </td>
                    <td className="py-2.5 px-3 tabular-nums text-content-secondary">
                      {item.diameter_mm ? `Ø ${item.diameter_mm} mm` : ''}
                      {item.diameter_inch ? ` (${item.diameter_inch}")` : ''}
                      {item.length_m ? ` × ${item.length_m} m` : ''}
                      {item.weight_kg ? ` [${item.weight_kg} kg]` : ''}
                      {!item.diameter_mm && !item.weight_kg && !item.length_m ? '-' : ''}
                    </td>
                    <td className="py-2.5 px-3 font-sans">
                      {item.material_type ? (
                        <span className="px-2 py-0.5 rounded-control bg-surface-elevated text-content-primary border border-surface-hairline text-[11px] font-semibold">
                          {item.material_type}
                        </span>
                      ) : (
                        <span className="text-amber-700 dark:text-amber-400 font-bold text-[11px] flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" />
                          Falta Especificar
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 font-sans">
                      {isPending ? (
                        <span className="px-2 py-0.5 rounded-control bg-semantic-hitlBg text-semantic-hitlText font-bold text-[11px] border border-semantic-hitlBorder inline-block">
                          Requiere Acción HITL
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-control bg-semantic-winnerBg text-semantic-winnerText font-bold text-[11px] border border-surface-hairline inline-block">
                          Confirmado
                        </span>
                      )}
                    </td>
                  </tr>

                  {/* Consola en Línea de Desambiguación HITL para el Ítem Ambiguo */}
                  {isPending && (
                    <tr className="bg-semantic-hitlBg/40 border-b border-semantic-hitlBorder">
                      <td colSpan={6} className="py-3 px-4 font-sans">
                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                          <div>
                            <p className="text-xs text-semantic-hitlText font-semibold flex items-center gap-1.5">
                              <Layers className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                              <span>{item.clarification_prompt || 'Especifica el tipo de material para evitar errores de cotización:'}</span>
                            </p>
                            <label className="flex items-center gap-1.5 text-[11px] text-content-secondary mt-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={!!saveAsAliasMap[item.id]}
                                onChange={(e) =>
                                  setSaveAsAliasMap({ ...saveAsAliasMap, [item.id]: e.target.checked })
                                }
                                className="rounded-control border-surface-strong text-action-primary focus:ring-action-focus w-3.5 h-3.5"
                              />
                              <Save className="w-3.5 h-3.5 text-content-muted" />
                              <span>Guardar equivalencia supervisada para futuros presupuestos</span>
                            </label>
                          </div>

                          {/* Píldoras de Selección de Material (min-height: 36px) */}
                          <div
                            role="group"
                            aria-label={`Opciones de material para ${item.raw_line}`}
                            className="flex flex-wrap items-center gap-2"
                          >
                            {[
                              { label: 'PVC Cloacal / Agua', value: 'PVC' },
                              { label: 'Termofusión', value: 'Termofusión' },
                              { label: 'Polipropileno', value: 'Polipropileno' },
                              { label: 'Corrugado', value: 'Corrugado' },
                              { label: 'Hierro Estructural', value: 'Hierro estructural' },
                            ].map((mat, btnIdx) => (
                              <button
                                key={mat.value}
                                ref={index === 0 && btnIdx === 0 ? firstAmbiguousButtonRef : undefined}
                                onClick={() => handleQuickResolve(item, mat.value, mat.label)}
                                disabled={isLoading}
                                type="button"
                                className="px-3 py-1.5 rounded-control bg-surface-elevated hover:bg-surface-subtle text-content-primary hover:text-action-primary border border-surface-hairline hover:border-surface-strong text-xs font-semibold transition shadow-sm min-h-[36px]"
                              >
                                {mat.label}
                              </button>
                            ))}
                          </div>
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

      {/* Botón de Ejecución de Compulsa con Blindaje ISO/IEC 25010 y WCAG 3.3.4 */}
      <div className="pt-3 border-t border-surface-hairline flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="text-xs text-content-secondary flex items-center gap-1.5">
          <HelpCircle className="w-4 h-4 text-content-muted shrink-0" />
          <span>
            {allResolved
              ? 'Todos los ítems poseen especificación dimensional completa. Listo para cotejar contra corralones.'
              : 'La compulsa permanece bloqueada hasta definir el material exacto en cada ítem ambiguo.'}
          </span>
        </div>

        <button
          onClick={handleStartComparison}
          disabled={isLoading}
          aria-disabled={!allResolved}
          type="button"
          className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-control font-bold text-xs shadow-sm transition min-h-[42px] ${
            allResolved
              ? 'bg-action-primary hover:bg-action-hover text-white cursor-pointer'
              : 'bg-surface-subtle text-content-muted border border-surface-hairline cursor-not-allowed opacity-75'
          }`}
          title={!allResolved ? 'Debes resolver los ítems pendientes antes de cotizar' : 'Ejecutar compulsa'}
        >
          <span>Ejecutar Compulsa Multi-Corralón</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </section>
  );
};
