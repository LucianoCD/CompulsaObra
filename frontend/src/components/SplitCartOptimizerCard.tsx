import React, { useState } from 'react';
import { useComparisonStore } from '../store/useComparisonStore';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { apiClient } from '../services/apiClient';
import {
  Lock,
  Download,
  FileText,
  DollarSign,
  Truck,
  Check,
  Copy,
  ShieldCheck,
  TrendingDown,
  AlertTriangle,
  Loader2,
} from 'lucide-react';
import { BudgetStrategy, PaymentModality } from '../types/api';

interface SplitCartOptimizerCardProps {
  onLockBudget: () => void;
}

export const SplitCartOptimizerCard: React.FC<SplitCartOptimizerCardProps> = ({ onLockBudget }) => {
  const { role } = useWorkspaceStore();
  const {
    currentMatrix,
    lockedBudget,
    lockBudget,
    isLoading,
    error,
    paymentModality,
    includeDeliveryFees,
    markupPct,
    budgetStrategy,
    selectedSingleVendorId,
    setPaymentModality,
    setIncludeDeliveryFees,
    setMarkupPct,
    setBudgetStrategy,
    setSelectedSingleVendorId,
  } = useComparisonStore();

  const [copiedLink, setCopiedLink] = useState(false);
  const [acceptPartial, setAcceptPartial] = useState(false);
  const [downloadingMode, setDownloadingMode] = useState<'comparison' | 'client_budget' | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [lockError, setLockError] = useState<string | null>(null);

  if (!currentMatrix) {
    return (
      <div className="bg-surface-elevated border border-surface-hairline rounded-container p-4 sm:p-5 transition-colors space-y-3">
        <div className="flex items-center gap-2 pb-2 border-b border-surface-hairline">
          <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-control bg-surface-subtle text-action-primary border border-surface-hairline">
            FINANZAS
          </span>
          <h2 className="text-sm font-display font-bold text-content-primary">
            Optimizador Logístico y Financiero
          </h2>
        </div>
        <p className="text-xs text-content-secondary leading-relaxed">
          Configura los parámetros de cotización antes o después de procesar el pliego. Los cálculos se actualizarán automáticamente.
        </p>

        {/* Pre-configuración de Parámetros */}
        <div className="space-y-3 pt-2">
          <div>
            <label className="block text-[11px] font-semibold uppercase text-content-secondary tracking-wider mb-1">
              Modalidad de Pago:
            </label>
            <div className="grid grid-cols-3 gap-1 bg-surface-subtle p-1 rounded-control border border-surface-hairline text-xs font-semibold">
              {(['CASH', 'LIST', 'ACOPIO'] as PaymentModality[]).map((mod) => (
                <button
                  key={mod}
                  type="button"
                  onClick={() => setPaymentModality(mod)}
                  className={`py-1 rounded-control transition ${
                    paymentModality === mod
                      ? 'bg-surface-elevated text-action-primary shadow-xs'
                      : 'text-content-secondary hover:text-content-primary'
                  }`}
                >
                  {mod === 'CASH' ? 'Contado' : mod === 'LIST' ? 'Lista' : 'Acopio'}
                </button>
              ))}
            </div>
          </div>

          <label className="flex items-center gap-2 text-xs font-semibold text-content-primary cursor-pointer select-none">
            <input
              type="checkbox"
              checked={includeDeliveryFees}
              onChange={(e) => setIncludeDeliveryFees(e.target.checked)}
              className="rounded-control border-surface-strong text-action-primary focus:ring-action-focus w-4 h-4"
            />
            <Truck className="w-4 h-4 text-content-muted" />
            <span>Incluir fletes logísticos en el cómputo</span>
          </label>
        </div>
      </div>
    );
  }

  const bestSingle = {
    name: currentMatrix.best_single_vendor_name || 'Comercio Único',
    total: currentMatrix.best_single_total_ars || 0,
  };

  const split = currentMatrix.split_cart;
  const isRecommended = split.is_split_recommended;
  const isLocked = !!lockedBudget || currentMatrix.status === 'LOCKED_BUDGET';
  const fulfillmentStatus = currentMatrix.fulfillment_status ?? 'complete';
  const effectiveSingleVendorId = selectedSingleVendorId || currentMatrix.best_single_vendor_id || null;

  const handleLock = async () => {
    setLockError(null);
    try {
      await lockBudget({
        accept_partial: fulfillmentStatus === 'partial' ? acceptPartial : false,
        strategy: budgetStrategy,
        selected_single_vendor_id:
          budgetStrategy === 'SINGLE_VENDOR' ? effectiveSingleVendorId : null,
      });
      onLockBudget();
    } catch (err: unknown) {
      setLockError(err instanceof Error ? err.message : 'No se pudo congelar el presupuesto.');
    }
  };

  const handleDownloadPdf = async (mode: 'comparison' | 'client_budget') => {
    setDownloadError(null);
    setDownloadingMode(mode);
    try {
      await apiClient.triggerPdfDownload(
        currentMatrix.run_id,
        mode,
        isLocked ? undefined : budgetStrategy,
        isLocked ? null : budgetStrategy === 'SINGLE_VENDOR' ? effectiveSingleVendorId : null
      );
    } catch (err: unknown) {
      setDownloadError(err instanceof Error ? err.message : 'Error al descargar el PDF.');
    } finally {
      setDownloadingMode(null);
    }
  };

  const handleCopyShareLink = () => {
    const shareUrl = `${window.location.origin}/p/${currentMatrix.public_share_token}`;
    navigator.clipboard.writeText(shareUrl);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  };

  const adjustMarkup = (delta: number) => {
    const next = Math.max(0, Math.min(100, Math.round((markupPct + delta) * 10) / 10));
    setMarkupPct(next);
  };

  return (
    <div className="bg-surface-elevated border border-surface-hairline rounded-container p-4 sm:p-5 transition-colors space-y-4">
      {/* Cabecera del Panel Financiero */}
      <div className="flex items-center justify-between pb-3 border-b border-surface-hairline">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-control bg-surface-subtle text-action-primary border border-surface-hairline">
            DECISIÓN
          </span>
          <h2 className="text-sm font-display font-bold text-content-primary">
            Optimizador Logístico: Split Cart
          </h2>
        </div>
        {isLocked && (
          <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded-control bg-semantic-winnerBg text-semantic-winnerText border border-surface-hairline">
            <Lock className="w-3 h-3" /> Congelado
          </span>
        )}
      </div>

      {/* Controles Financieros Adherentes */}
      <div className="bg-surface-subtle p-3 rounded-control border border-surface-hairline space-y-3 text-xs">
        {/* Selector de Modalidad */}
        <div>
          <span className="block text-[10px] font-semibold uppercase text-content-muted tracking-wider mb-1">
            Modalidad Comercial:
          </span>
          <div className="grid grid-cols-3 gap-1 bg-surface-elevated p-1 rounded-control border border-surface-hairline text-xs font-semibold">
            {(['CASH', 'LIST', 'ACOPIO'] as PaymentModality[]).map((mod) => (
              <button
                key={mod}
                type="button"
                disabled={isLocked}
                onClick={() => setPaymentModality(mod)}
                className={`py-1 rounded-control transition ${
                  paymentModality === mod
                    ? 'bg-action-primary text-white shadow-xs'
                    : 'text-content-secondary hover:text-content-primary'
                }`}
              >
                {mod === 'CASH' ? 'Contado' : mod === 'LIST' ? 'Precio Lista' : 'Acopio'}
              </button>
            ))}
          </div>
        </div>

        {/* Switch de Fletes */}
        <label className="flex items-center justify-between cursor-pointer select-none">
          <span className="text-content-primary font-semibold flex items-center gap-1.5">
            <Truck className="w-4 h-4 text-content-muted" />
            <span>Fletes por corralón</span>
          </span>
          <input
            type="checkbox"
            disabled={isLocked}
            checked={includeDeliveryFees}
            onChange={(e) => setIncludeDeliveryFees(e.target.checked)}
            className="rounded-control border-surface-strong text-action-primary focus:ring-action-focus w-4 h-4"
          />
        </label>

        {/* Margen del Presupuestador (ESTIMATOR) con Alternativa Accesible a Sliders (WCAG 2.5.7) */}
        {role === 'ESTIMATOR' && (
          <div className="pt-2 border-t border-surface-hairline/80">
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-semibold text-content-primary flex items-center gap-1">
                <DollarSign className="w-3.5 h-3.5 text-action-primary" />
                <span>Margen Honorarios:</span>
              </span>
              <span className="font-mono font-bold text-content-primary tabular-nums text-xs">
                {markupPct.toFixed(1)} %
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                disabled={isLocked || markupPct <= 0}
                onClick={() => adjustMarkup(-5)}
                className="px-2 py-1 rounded-control bg-surface-elevated hover:bg-surface-subtle border border-surface-hairline text-content-primary text-xs font-mono font-bold min-h-[32px] min-w-[36px]"
                title="Restar 5%"
              >
                -5%
              </button>
              <button
                type="button"
                disabled={isLocked || markupPct <= 0}
                onClick={() => adjustMarkup(-1)}
                className="px-2 py-1 rounded-control bg-surface-elevated hover:bg-surface-subtle border border-surface-hairline text-content-primary text-xs font-mono font-bold min-h-[32px] min-w-[36px]"
                title="Restar 1%"
              >
                -1%
              </button>
              <input
                type="number"
                step="0.5"
                min="0"
                max="100"
                disabled={isLocked}
                value={markupPct}
                onChange={(e) => setMarkupPct(parseFloat(e.target.value) || 0)}
                className="flex-1 bg-surface-elevated border border-surface-hairline rounded-control px-2 py-1 text-xs text-center font-mono font-bold text-content-primary tabular-nums"
                aria-label="Porcentaje de margen profesional"
              />
              <button
                type="button"
                disabled={isLocked || markupPct >= 100}
                onClick={() => adjustMarkup(1)}
                className="px-2 py-1 rounded-control bg-surface-elevated hover:bg-surface-subtle border border-surface-hairline text-content-primary text-xs font-mono font-bold min-h-[32px] min-w-[36px]"
                title="Sumar 1%"
              >
                +1%
              </button>
              <button
                type="button"
                disabled={isLocked || markupPct >= 100}
                onClick={() => adjustMarkup(5)}
                className="px-2 py-1 rounded-control bg-surface-elevated hover:bg-surface-subtle border border-surface-hairline text-content-primary text-xs font-mono font-bold min-h-[32px] min-w-[36px]"
                title="Sumar 5%"
              >
                +5%
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Tarjeta de Decisión: Proveedor Único vs Carrito Dividido (H-02) */}
      <div className="space-y-3 font-mono">
        <div className="flex items-center justify-between text-[10px] font-sans font-semibold uppercase tracking-wider text-content-secondary">
          <span>Estrategia Activa para Emisión / PDF:</span>
          <span className="font-mono text-action-primary">
            {budgetStrategy === 'SINGLE_VENDOR' ? 'Proveedor Único' : 'Split Cart'}
          </span>
        </div>

        {/* Opción A: Proveedor Único */}
        <button
          type="button"
          disabled={isLocked}
          onClick={() => {
            setBudgetStrategy('SINGLE_VENDOR');
            if (!selectedSingleVendorId && currentMatrix.best_single_vendor_id) {
              setSelectedSingleVendorId(currentMatrix.best_single_vendor_id);
            }
          }}
          className={`w-full text-left p-3.5 rounded-control border transition ${
            budgetStrategy === 'SINGLE_VENDOR'
              ? 'bg-semantic-winnerBg/70 border-emerald-600 ring-1 ring-emerald-600/40 shadow-sm'
              : !isRecommended
                ? 'bg-semantic-winnerBg/40 border-emerald-600/50 shadow-xs'
                : 'bg-surface-subtle border-surface-hairline hover:border-surface-strong'
          }`}
        >
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] uppercase font-bold text-content-muted font-sans tracking-wide">
              Estrategia A · Compra Unificada
            </span>
            <div className="flex items-center gap-1">
              {budgetStrategy === 'SINGLE_VENDOR' && (
                <span className="text-[9px] font-sans font-extrabold uppercase px-1.5 py-0.2 rounded bg-action-primary text-white">
                  Activa
                </span>
              )}
              {!isRecommended && (
                <span className="text-[9px] font-sans font-bold uppercase px-1.5 py-0.2 rounded bg-semantic-winnerBg text-semantic-winnerText border border-surface-hairline">
                  Recomendada
                </span>
              )}
            </div>
          </div>
          <div className="font-sans font-bold text-xs text-content-primary truncate">{bestSingle.name}</div>
          <div className="text-[11px] text-content-secondary mt-0.5 font-sans">
            1 solo flete logístico consolidado en obra.
          </div>
          <div className="mt-2 pt-2 border-t border-surface-hairline flex items-baseline justify-between">
            <span className="text-[11px] text-content-muted font-sans">Total Obra:</span>
            <span className="text-base font-extrabold text-content-primary tabular-nums">
              $ {bestSingle.total.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
            </span>
          </div>
        </button>

        {/* Opción B: Carrito Dividido Óptimo (Split Cart) */}
        <button
          type="button"
          disabled={isLocked}
          onClick={() => setBudgetStrategy('SPLIT_CART' as BudgetStrategy)}
          className={`w-full text-left p-3.5 rounded-control border transition ${
            budgetStrategy === 'SPLIT_CART'
              ? 'bg-semantic-winnerBg/70 border-emerald-600 ring-1 ring-emerald-600/40 shadow-sm'
              : 'bg-surface-subtle border-surface-hairline hover:border-surface-strong'
          }`}
        >
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] uppercase font-bold text-content-muted font-sans tracking-wide">
              Estrategia B · Split Cart Óptimo
            </span>
            <div className="flex items-center gap-1">
              {budgetStrategy === 'SPLIT_CART' && (
                <span className="text-[9px] font-sans font-extrabold uppercase px-1.5 py-0.2 rounded bg-action-primary text-white">
                  Activa
                </span>
              )}
              {isRecommended && (
                <span className="text-[9px] font-sans font-extrabold uppercase px-1.5 py-0.2 rounded bg-semantic-winnerBg text-semantic-winnerText border border-surface-hairline">
                  Mayor Ahorro Neto
                </span>
              )}
            </div>
          </div>
          <div className="font-sans font-bold text-xs text-content-primary">
            {split.participating_vendors_count} Corralones Seleccionados
          </div>
          <div className="text-[10px] text-content-secondary mt-0.5 font-sans truncate">
            {split.participating_vendor_names.join(' + ')}
          </div>

          <div className="mt-2 pt-2 border-t border-surface-hairline space-y-1 text-xs">
            <div className="flex justify-between text-content-secondary text-[11px]">
              <span className="font-sans">Materiales:</span>
              <span className="tabular-nums">
                $ {split.total_materials_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="flex justify-between text-content-secondary text-[11px]">
              <span className="font-sans">Suma Fletes ({split.participating_vendors_count} viajes):</span>
              <span className="tabular-nums font-semibold text-amber-700 dark:text-amber-400">
                + $ {split.total_delivery_fees_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="flex justify-between text-content-primary font-bold pt-1 border-t border-surface-hairline items-baseline">
              <span className="font-sans">Total Split Cart:</span>
              <span className="text-base font-extrabold text-emerald-700 dark:text-emerald-400 tabular-nums">
                $ {split.total_cart_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>

          {split.savings_vs_single_vendor_ars > 0 && (
            <div className="mt-2.5 p-2 rounded-control bg-semantic-winnerBg text-semantic-winnerText border border-surface-hairline text-xs font-semibold flex items-center justify-between font-sans">
              <span className="flex items-center gap-1 text-[11px]">
                <TrendingDown className="w-3.5 h-3.5" /> Ahorro Neto Real:
              </span>
              <span className="font-mono font-extrabold tabular-nums">
                -$ {split.savings_vs_single_vendor_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
              </span>
            </div>
          )}
        </button>
      </div>

      {/* Guardia de Completitud y Acciones de Cierre (H-05, H-08) */}
      <div className="pt-2 border-t border-surface-hairline space-y-2.5">
        {fulfillmentStatus !== 'complete' && !isLocked && (
          <div
            role="status"
            className="p-2.5 rounded-control bg-semantic-hitlBg border border-semantic-hitlBorder text-[11px] text-content-primary space-y-1.5"
          >
            <div className="flex items-center gap-1.5 font-bold text-amber-800 dark:text-amber-300">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              <span>
                {fulfillmentStatus === 'pending'
                  ? `Compulsa Pendiente (${currentMatrix.ambiguous_items_count} ambigüedades sin resolver)`
                  : `Presupuesto Parcial (${currentMatrix.unresolved_items_count} renglón/es sin cobertura)`}
              </span>
            </div>
            {fulfillmentStatus === 'pending' ? (
              <p className="text-content-secondary leading-tight">
                Resuelve los ítems ambiguos en la matriz antes de congelar el presupuesto definitivo.
              </p>
            ) : (
              <label className="flex items-start gap-2 cursor-pointer select-none text-content-primary">
                <input
                  type="checkbox"
                  checked={acceptPartial}
                  onChange={(e) => setAcceptPartial(e.target.checked)}
                  className="mt-0.5 rounded-control border-surface-strong text-action-primary focus:ring-action-focus w-4 h-4"
                />
                <span>Confirmo emitir y congelar presupuesto parcial excluyendo renglones sin cobertura.</span>
              </label>
            )}
          </div>
        )}

        {(lockError || downloadError || error) && (
          <div
            role="alert"
            className="p-2 rounded-control bg-semantic-dangerBg border border-red-400/50 text-semantic-dangerText text-[11px] font-medium"
          >
            {lockError || downloadError || error}
          </div>
        )}

        {!isLocked ? (
          <button
            onClick={handleLock}
            disabled={
              isLoading ||
              fulfillmentStatus === 'pending' ||
              (fulfillmentStatus === 'partial' && !acceptPartial)
            }
            type="button"
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-control bg-action-primary hover:bg-action-hover disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold text-xs shadow-sm transition min-h-[42px]"
          >
            <Lock className="w-3.5 h-3.5" />
            <span>Congelar Presupuesto Definitivo (Lock-Budget)</span>
          </button>
        ) : (
          <div className="space-y-2">
            <div className="p-2.5 rounded-control bg-surface-subtle border border-surface-hairline text-[11px] text-content-secondary space-y-1">
              <div className="flex items-center gap-1.5 font-bold text-content-primary font-mono text-[10px] uppercase">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                <span>Snapshot Inmutable HMAC-SHA256 Verificado</span>
              </div>
              <p className="font-sans leading-tight">
                El pliego ha quedado congelado contra mutaciones. Descarga los documentos autenticados o comparte el enlace público.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                disabled={downloadingMode !== null}
                onClick={() => handleDownloadPdf('comparison')}
                className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-control bg-surface-subtle hover:bg-surface-elevated disabled:opacity-60 border border-surface-hairline text-content-primary text-xs font-semibold transition"
              >
                {downloadingMode === 'comparison' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-action-primary" />
                ) : (
                  <Download className="w-3.5 h-3.5 text-action-primary" />
                )}
                <span>PDF Comparativa</span>
              </button>
              <button
                type="button"
                disabled={downloadingMode !== null}
                onClick={() => handleDownloadPdf('client_budget')}
                className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-control bg-action-primary hover:bg-action-hover disabled:opacity-60 text-white text-xs font-bold transition shadow-sm"
              >
                {downloadingMode === 'client_budget' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <FileText className="w-3.5 h-3.5" />
                )}
                <span>PDF Cliente</span>
              </button>
            </div>

            <button
              onClick={handleCopyShareLink}
              type="button"
              className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-control bg-surface-subtle hover:bg-surface-elevated border border-surface-hairline text-xs font-semibold text-content-primary transition"
            >
              {copiedLink ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  <span>¡Enlace Público Copiado al Portapapeles!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copiar Enlace Público (/p/{currentMatrix.public_share_token.slice(0, 8)}...)</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
