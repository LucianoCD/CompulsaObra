import React, { useEffect, useMemo } from 'react';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { useRequisitionStore } from '../store/useRequisitionStore';
import { useComparisonStore } from '../store/useComparisonStore';
import { IngestionDropzone } from '../components/IngestionDropzone';
import { DisambiguationTable } from '../components/DisambiguationTable';
import { MultiVendorMatrix } from '../components/MultiVendorMatrix';
import { SplitCartOptimizerCard } from '../components/SplitCartOptimizerCard';
import { AcopioSimulatorPanel } from '../components/AcopioSimulatorPanel';
import {
  Store,
  RefreshCw,
  Layers,
  Check,
  AlertTriangle,
  Plus,
  CheckCircle2,
  Info,
  Loader2,
} from 'lucide-react';

interface BuilderDashboardPageProps {
  onOpenCatalogs: () => void;
}

export const BuilderDashboardPage: React.FC<BuilderDashboardPageProps> = ({ onOpenCatalogs }) => {
  const { role, workspaceId } = useWorkspaceStore();
  const { currentRequisition, resetRequisition } = useRequisitionStore();
  const {
    vendors,
    selectedVendorIds,
    currentMatrix,
    isLoading: isComparisonLoading,
    loadVendors,
    toggleVendorSelection,
    runComparison,
    resetComparison,
  } = useComparisonStore();

  useEffect(() => {
    void loadVendors();
  }, [loadVendors, workspaceId]);

  // Limpiar matriz previa si se inicia o ingesta una nueva lista de materiales
  useEffect(() => {
    if (
      currentMatrix &&
      currentRequisition &&
      currentMatrix.requisition_id !== currentRequisition.id
    ) {
      resetComparison();
    }
  }, [currentRequisition, currentMatrix, resetComparison]);

  const handleNewBudget = () => {
    resetRequisition();
    resetComparison();
  };

  const isMatrixStale = useMemo(() => {
    if (
      !currentMatrix ||
      !currentRequisition ||
      currentMatrix.is_locked ||
      currentMatrix.status === 'LOCKED_BUDGET'
    ) {
      return false;
    }
    if (currentMatrix.requisition_id !== currentRequisition.id) {
      return false;
    }
    const matrixVendorIds = [...currentMatrix.vendors.map((v) => v.vendor_id)].sort();
    const currentSelectedIds = [...selectedVendorIds].sort();
    if (matrixVendorIds.length !== currentSelectedIds.length) {
      return true;
    }
    return matrixVendorIds.some((id, idx) => id !== currentSelectedIds[idx]);
  }, [currentMatrix, currentRequisition, selectedVendorIds]);

  const step1Done = currentRequisition !== null;
  const step2HasPending =
    currentRequisition !== null && currentRequisition.pending_clarifications_count > 0;
  const step2Done =
    currentRequisition !== null && currentRequisition.pending_clarifications_count === 0;
  const step3Done = currentMatrix !== null;

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-5 xl:px-6 py-6 space-y-6">
      {/* Encabezado del Área de Trabajo */}
      <div className="bg-surface-elevated border border-surface-hairline rounded-container p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-card transition-colors">
        <div className="flex items-start sm:items-center gap-3.5">
          <div className="h-10 w-10 rounded-control bg-surface-subtle border border-surface-hairline flex items-center justify-center text-action-primary shrink-0">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg sm:text-[22px] leading-tight font-display font-extrabold text-content-primary tracking-tight">
              Presupuesto de Materiales y Comparativa de Corralones
            </h1>
            <p className="text-[13px] sm:text-sm text-content-secondary mt-1">
              {role === 'ESTIMATOR'
                ? 'Vista Presupuestador: Armá tu cómputo, aplicá tu margen profesional y emití el presupuesto para tu cliente.'
                : 'Vista Comprador de Obra: Compará precios de contado, acopio y fletes para comprar al menor costo en Jujuy.'}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <button
            onClick={onOpenCatalogs}
            type="button"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-control bg-surface-subtle hover:bg-surface-elevated text-content-primary border border-surface-hairline text-[13px] font-semibold transition min-h-[40px]"
          >
            <Store className="w-4 h-4 text-action-primary" />
            <span>Gestionar Corralones ({vendors.length})</span>
          </button>

          {currentRequisition && (
            <button
              onClick={handleNewBudget}
              type="button"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-control bg-surface-subtle hover:bg-surface-elevated text-content-secondary hover:text-content-primary border border-surface-hairline text-[13px] font-semibold transition min-h-[40px]"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Nuevo Pedido</span>
            </button>
          )}
        </div>
      </div>

      {/* Barra de Progreso Guiada de 3 Pasos */}
      <nav
        aria-label="Pasos del presupuesto"
        className="bg-surface-elevated border border-surface-hairline rounded-container px-4 py-3 min-h-[48px] shadow-card"
      >
        <ol className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-[13px]">
          {/* Paso 1 */}
          <li className="flex items-center gap-2.5">
            <span
              className={`h-7 w-7 rounded-pill flex items-center justify-center font-bold text-xs shrink-0 border ${
                step1Done
                  ? 'bg-semantic-winnerBg text-semantic-winnerText border-emerald-600/30'
                  : 'bg-action-primary text-white border-action-primary'
              }`}
            >
              {step1Done ? <Check className="w-4 h-4" /> : '1'}
            </span>
            <div className="min-w-0">
              <div
                className={`font-bold truncate ${
                  step1Done ? 'text-semantic-winnerText' : 'text-content-primary'
                }`}
              >
                1. Cargar lista
              </div>
              <div className="text-xs text-content-muted truncate">
                {step1Done
                  ? `${currentRequisition.items.length} materiales cargados`
                  : 'Texto, WhatsApp, foto o ejemplo'}
              </div>
            </div>
          </li>

          {/* Paso 2 */}
          <li className="flex items-center gap-2.5">
            <span
              className={`h-7 w-7 rounded-pill flex items-center justify-center font-bold text-xs shrink-0 border ${
                step2Done
                  ? 'bg-semantic-winnerBg text-semantic-winnerText border-emerald-600/30'
                  : step2HasPending
                    ? 'bg-semantic-hitlBg text-semantic-hitlText border-semantic-hitlBorder'
                    : 'bg-surface-subtle text-content-muted border-surface-hairline'
              }`}
            >
              {step2Done ? (
                <Check className="w-4 h-4" />
              ) : step2HasPending ? (
                <AlertTriangle className="w-3.5 h-3.5" />
              ) : (
                '2'
              )}
            </span>
            <div className="min-w-0">
              <div
                className={`font-bold truncate ${
                  step2Done
                    ? 'text-semantic-winnerText'
                    : step2HasPending
                      ? 'text-semantic-hitlText'
                      : 'text-content-muted'
                }`}
              >
                2. Confirmar medidas
              </div>
              <div className="text-xs text-content-muted truncate">
                {step2HasPending
                  ? `${currentRequisition?.pending_clarifications_count} por definir`
                  : step2Done
                    ? 'Todas las medidas listas'
                    : 'Revisar cantidades y tipos'}
              </div>
            </div>
          </li>

          {/* Paso 3 */}
          <li className="flex items-center gap-2.5">
            <span
              className={`h-7 w-7 rounded-pill flex items-center justify-center font-bold text-xs shrink-0 border ${
                step3Done
                  ? 'bg-semantic-winnerBg text-semantic-winnerText border-emerald-600/30'
                  : step2Done
                    ? 'bg-action-primary text-white border-action-primary'
                    : 'bg-surface-subtle text-content-muted border-surface-hairline'
              }`}
            >
              {step3Done ? <Check className="w-4 h-4" /> : '3'}
            </span>
            <div className="min-w-0">
              <div
                className={`font-bold truncate ${
                  step3Done
                    ? 'text-semantic-winnerText'
                    : step2Done
                      ? 'text-content-primary'
                      : 'text-content-muted'
                }`}
              >
                3. Comparar precios
              </div>
              <div className="text-xs text-content-muted truncate">
                {step3Done
                  ? `${currentMatrix.vendors.length} corralones cotizados`
                  : 'Mejor opción, fletes y presupuesto'}
              </div>
            </div>
          </li>
        </ol>
      </nav>

      {/* Selector de Corralones Participantes */}
      <div className="bg-surface-elevated border border-surface-hairline rounded-container p-4 space-y-3 shadow-card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[13px]">
          <span className="font-bold text-content-primary">
            Corralones incluidos en la comparación ({selectedVendorIds.length} de {vendors.length}):
          </span>
          <span className="text-xs text-content-muted">
            Tocá cada corralón para incluirlo o quitarlo de la comparativa
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {vendors.length === 0 ? (
            <button
              type="button"
              onClick={onOpenCatalogs}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-control border border-dashed border-action-primary text-action-primary bg-action-primary/5 hover:bg-action-primary/10 text-[13px] font-bold transition min-h-[40px]"
            >
              <Plus className="w-4 h-4" />
              <span>Agregar mi primer corralón</span>
            </button>
          ) : (
            <>
              {vendors.map((v) => {
                const isSelected = selectedVendorIds.includes(v.id);

                return (
                  <button
                    key={v.id}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => toggleVendorSelection(v.id)}
                    className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-control text-[13px] font-semibold border transition min-h-[38px] ${
                      isSelected
                        ? 'bg-action-primary/10 border-action-primary/40 text-action-primary shadow-card'
                        : 'bg-surface-subtle border-surface-hairline text-content-secondary hover:border-surface-strong hover:text-content-primary'
                    }`}
                  >
                    {isSelected ? (
                      <CheckCircle2 className="w-4 h-4 text-action-primary shrink-0" />
                    ) : (
                      <div className="w-2.5 h-2.5 rounded-full bg-surface-strong shrink-0" />
                    )}
                    <span>{v.name}</span>
                    <span className="text-xs text-content-muted font-normal">({v.locality})</span>
                  </button>
                );
              })}

              <button
                type="button"
                onClick={onOpenCatalogs}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-control text-[13px] font-semibold border border-dashed border-surface-strong text-content-secondary hover:text-action-primary hover:border-action-primary bg-surface-canvas transition min-h-[38px]"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Agregar corralón</span>
              </button>
            </>
          )}
        </div>

        {vendors.length > 0 && selectedVendorIds.length === 0 && (
          <div
            role="alert"
            className="p-3 rounded-control bg-semantic-hitlBg border border-semantic-hitlBorder text-semantic-hitlText text-[13px] font-medium flex items-center gap-2"
          >
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>Seleccioná al menos un corralón para comparar precios.</span>
          </div>
        )}

        {isMatrixStale && (
          <div
            role="status"
            className="p-3 rounded-control bg-semantic-infoBg text-semantic-infoText border border-surface-hairline text-[13px] flex flex-col sm:flex-row sm:items-center justify-between gap-2.5"
          >
            <div className="flex items-center gap-2 font-medium">
              <Info className="w-4 h-4 shrink-0" />
              <span>
                Cambiaste los corralones seleccionados. Actualizá la comparativa para recalcular los precios.
              </span>
            </div>
            <button
              type="button"
              disabled={isComparisonLoading || selectedVendorIds.length === 0 || !currentRequisition}
              onClick={() => {
                if (currentRequisition) {
                  void runComparison(currentRequisition.id);
                }
              }}
              className="inline-flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-control bg-action-primary hover:bg-action-hover disabled:opacity-50 text-white text-[13px] font-bold transition min-h-[36px] shrink-0"
            >
              {isComparisonLoading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5" />
              )}
              <span>Actualizar precios</span>
            </button>
          </div>
        )}
      </div>

      {/* Layout Asimétrico 12 Columnas: 8 Izquierda (Flujo Guiado) + 4 Derecha (Panel Financiero Sticky) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 xl:gap-6 items-start">
        <div className="lg:col-span-8 space-y-6">
          <IngestionDropzone />

          {currentRequisition && (
            <DisambiguationTable
              onProceedToCompare={() => {
                // Comparativa ejecutada y matriz actualizada
              }}
            />
          )}

          {currentMatrix && <MultiVendorMatrix />}
        </div>

        <div className="lg:col-span-4 lg:sticky lg:top-[120px] max-h-[calc(100vh-136px)] overflow-y-auto z-30 space-y-4">
          <SplitCartOptimizerCard
            onLockBudget={() => {
              // Presupuesto confirmado y bloqueado
            }}
          />

          <AcopioSimulatorPanel />
        </div>
      </div>
    </div>
  );
};
