import React, { useEffect } from 'react';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { useRequisitionStore } from '../store/useRequisitionStore';
import { useComparisonStore } from '../store/useComparisonStore';
import { IngestionDropzone } from '../components/IngestionDropzone';
import { DisambiguationTable } from '../components/DisambiguationTable';
import { MultiVendorMatrix } from '../components/MultiVendorMatrix';
import { SplitCartOptimizerCard } from '../components/SplitCartOptimizerCard';
import { AcopioSimulatorPanel } from '../components/AcopioSimulatorPanel';
import { Store, RefreshCw, Layers } from 'lucide-react';

interface BuilderDashboardPageProps {
  onOpenCatalogs: () => void;
}

export const BuilderDashboardPage: React.FC<BuilderDashboardPageProps> = ({ onOpenCatalogs }) => {
  const { role } = useWorkspaceStore();
  const { currentRequisition, resetRequisition } = useRequisitionStore();
  const {
    vendors,
    selectedVendorIds,
    currentMatrix,
    loadVendors,
    toggleVendorSelection,
    resetComparison,
  } = useComparisonStore();

  useEffect(() => {
    loadVendors();
  }, [loadVendors]);

  const handleNewBudget = () => {
    resetRequisition();
    resetComparison();
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 sm:px-6 py-5 space-y-5">
      {/* Barra de Encabezado Técnico de la Consola */}
      <div className="bg-surface-elevated border border-surface-hairline rounded-container p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 transition-colors">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-control bg-surface-subtle border border-surface-hairline flex items-center justify-center text-action-primary shrink-0">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base sm:text-lg font-display font-extrabold text-content-primary tracking-tight">
              Consola de Cómputo Métrico y Compulsa Multi-Corralón
            </h1>
            <p className="text-xs text-content-secondary mt-0.5">
              {role === 'ESTIMATOR'
                ? 'Perfil Presupuestador Profesional: Margen de honorarios, compulsa técnica y emisión de ofertas al comitente.'
                : 'Perfil Comprador de Obra: Enfoque en ahorro neto de bolsillo y comparativa directa entre corralones.'}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={onOpenCatalogs}
            type="button"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-control bg-surface-subtle hover:bg-surface-elevated text-content-primary border border-surface-hairline text-xs font-semibold transition"
          >
            <Store className="w-3.5 h-3.5 text-action-primary" />
            <span>Gestionar Corralones ({vendors.length})</span>
          </button>

          {currentRequisition && (
            <button
              onClick={handleNewBudget}
              type="button"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-control bg-surface-subtle hover:bg-surface-elevated text-content-secondary hover:text-content-primary border border-surface-hairline text-xs font-semibold transition"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Nuevo Pedido</span>
            </button>
          )}
        </div>
      </div>

      {/* Selector Rápido de Corralones Participantes */}
      <div className="bg-surface-elevated border border-surface-hairline rounded-container p-3.5 space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold uppercase tracking-wider text-[11px] text-content-secondary">
            Corralones Seleccionados para la Compulsa ({selectedVendorIds.length} de {vendors.length}):
          </span>
          <span className="text-[11px] text-content-muted">
            Haz clic para incluir o excluir comercios
          </span>
        </div>

        <div className="flex flex-wrap gap-2 pt-0.5">
          {vendors.map((v) => {
            const isSelected = selectedVendorIds.includes(v.id);

            return (
              <button
                key={v.id}
                type="button"
                onClick={() => toggleVendorSelection(v.id)}
                className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-control text-xs font-semibold border transition ${
                  isSelected
                    ? 'bg-action-primary/10 border-action-primary/40 text-action-primary shadow-xs'
                    : 'bg-surface-subtle border-surface-hairline text-content-muted hover:text-content-secondary'
                }`}
              >
                <div
                  className={`w-2 h-2 rounded-full ${
                    isSelected ? 'bg-action-primary' : 'bg-surface-strong'
                  }`}
                />
                <span>{v.name}</span>
                <span className="text-[10px] font-mono text-content-muted">({v.locality})</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Layout Asimétrico 12 Columnas: 8 Izquierda (Flujo Técnico) + 4 Derecha (Sticky Financiero) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Zona Izquierda: 8 Columnas */}
        <div className="lg:col-span-8 space-y-5">
          {/* Paso 01: Ingesta Multimodal */}
          <IngestionDropzone />

          {/* Paso 02: Desambiguación HITL */}
          {currentRequisition && (
            <DisambiguationTable
              onProceedToCompare={() => {
                // Compulsa ejecutada
              }}
            />
          )}

          {/* Paso 03: Matriz Multi-Proveedor */}
          {currentMatrix && <MultiVendorMatrix />}
        </div>

        {/* Zona Derecha: 4 Columnas Sticky */}
        <div className="lg:col-span-4 lg:sticky lg:top-18 space-y-4">
          <SplitCartOptimizerCard
            onLockBudget={() => {
              // Presupuesto congelado
            }}
          />

          <AcopioSimulatorPanel />
        </div>
      </div>
    </div>
  );
};
