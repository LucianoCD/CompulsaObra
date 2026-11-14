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
  Info,
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
      <div className="bg-surface-elevated border border-surface-hairline rounded-container p-4 sm:p-5 shadow-card transition-colors space-y-3.5">
        <div className="flex items-center gap-2 pb-2.5 border-b border-surface-hairline">
          <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-control bg-surface-subtle text-action-primary border border-surface-hairline">
            RESUMEN DE COMPRA
          </span>
          <h2 className="text-[15px] font-display font-bold text-content-primary">
            Elección de Compra y Envío
          </h2>
        </div>
        <p className="text-[13px] text-content-secondary leading-relaxed">
          Elegí cómo querés pagar y si incluís los fletes. Al comparar corralones vas a ver dónde te conviene comprar.
        </p>

        {/* Pre-configuración de Modalidad y Fletes */}
        <div className="space-y-3 pt-1">
          <div>
            <span className="block text-xs font-bold text-content-secondary mb-1.5">
              Modalidad de pago:
            </span>
            <div className="grid grid-cols-3 gap-1 bg-surface-subtle p-1 rounded-control border border-surface-hairline text-[13px] font-semibold">
              {(['CASH', 'LIST', 'ACOPIO'] as PaymentModality[]).map((mod) => (
                <button
                  key={mod}
                  type="button"
                  onClick={() => setPaymentModality(mod)}
                  className={`py-1.5 rounded-control transition min-h-[34px] ${
                    paymentModality === mod
                      ? 'bg-surface-elevated text-action-primary font-bold shadow-card'
                      : 'text-content-secondary hover:text-content-primary'
                  }`}
                >
                  {mod === 'CASH' ? 'Contado' : mod === 'LIST' ? 'Lista' : 'Acopio'}
                </button>
              ))}
            </div>
          </div>

          <label className="flex items-center gap-2 text-[13px] font-semibold text-content-primary cursor-pointer select-none min-h-[36px]">
            <input
              type="checkbox"
              checked={includeDeliveryFees}
              onChange={(e) => setIncludeDeliveryFees(e.target.checked)}
              className="rounded border-surface-strong text-action-primary focus:ring-action-focus w-4 h-4"
            />
            <Truck className="w-4 h-4 text-content-muted" />
            <span>Incluir fletes en la comparativa</span>
          </label>
        </div>
      </div>
    );
  }

  const bestSingle = {
    name: currentMatrix.best_single_vendor_name || 'Un solo corralón',
    total: currentMatrix.best_single_total_ars || 0,
  };

  const split = currentMatrix.split_cart;
  const isRecommended = split.is_split_recommended;
  const isLocked = !!lockedBudget || currentMatrix.status === 'LOCKED_BUDGET' || !!currentMatrix.is_locked;
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
      setLockError(err instanceof Error ? err.message : 'No se pudo confirmar el presupuesto.');
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
    void navigator.clipboard.writeText(shareUrl);
    setCopiedLink(true);
    window.setTimeout(() => setCopiedLink(false), 2500);
  };

  const adjustMarkup = (delta: number) => {
    const next = Math.max(0, Math.min(100, Math.round((markupPct + delta) * 10) / 10));
    setMarkupPct(next);
  };

  return (
    <div className="bg-surface-elevated border border-surface-hairline rounded-container p-4 sm:p-5 shadow-card transition-colors space-y-4">
      {/* Cabecera */}
      <div className="flex items-center justify-between pb-3 border-b border-surface-hairline gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-control bg-surface-subtle text-action-primary border border-surface-hairline shrink-0">
            RESUMEN
          </span>
          <h2 className="text-[15px] font-display font-bold text-content-primary truncate">
            Elección de Compra y Envío
          </h2>
        </div>
        {isLocked && (
          <span className="inline-flex items-center gap-1 text-xs font-bold px-2.5 py-0.5 rounded-pill bg-semantic-winnerBg text-semantic-winnerText border border-emerald-600/25 shrink-0">
            <Lock className="w-3 h-3" /> Confirmado
          </span>
        )}
      </div>

      {/* Modalidad de pago, Fletes y Margen según rol */}
      <div className="bg-surface-subtle p-3.5 rounded-control border border-surface-hairline space-y-3 text-[13px]">
        <div>
          <span className="block text-xs font-bold text-content-secondary mb-1.5">
            Modalidad comercial:
          </span>
          <div className="grid grid-cols-3 gap-1 bg-surface-elevated p-1 rounded-control border border-surface-hairline text-[13px] font-semibold">
            {(['CASH', 'LIST', 'ACOPIO'] as PaymentModality[]).map((mod) => (
              <button
                key={mod}
                type="button"
                disabled={isLocked}
                onClick={() => setPaymentModality(mod)}
                className={`py-1.5 rounded-control transition min-h-[34px] ${
                  paymentModality === mod
                    ? 'bg-action-primary text-white font-bold shadow-card'
                    : 'text-content-secondary hover:text-content-primary'
                }`}
              >
                {mod === 'CASH' ? 'Contado' : mod === 'LIST' ? 'Lista' : 'Acopio'}
              </button>
            ))}
          </div>
        </div>

        <label className="flex items-center justify-between cursor-pointer select-none min-h-[32px]">
          <span className="text-content-primary font-semibold flex items-center gap-1.5">
            <Truck className="w-4 h-4 text-content-muted" />
            <span>Incluir fletes por corralón</span>
          </span>
          <input
            type="checkbox"
            disabled={isLocked}
            checked={includeDeliveryFees}
            onChange={(e) => setIncludeDeliveryFees(e.target.checked)}
            className="rounded border-surface-strong text-action-primary focus:ring-action-focus w-4 h-4"
          />
        </label>

        {role === 'ESTIMATOR' ? (
          <div className="pt-2.5 border-t border-surface-hairline">
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-semibold text-content-primary flex items-center gap-1">
                <DollarSign className="w-4 h-4 text-action-primary" />
                <span>Margen de honorarios:</span>
              </span>
              <span className="font-mono font-bold text-content-primary tabular-nums text-[13px]">
                {markupPct.toFixed(1)} %
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                disabled={isLocked || markupPct <= 0}
                onClick={() => adjustMarkup(-5)}
                className="px-2 py-1 rounded-control bg-surface-elevated hover:bg-surface-canvas border border-surface-hairline text-content-primary text-xs font-mono font-bold min-h-[36px] min-w-[40px]"
                title="Restar 5%"
              >
                -5%
              </button>
              <button
                type="button"
                disabled={isLocked || markupPct <= 0}
                onClick={() => adjustMarkup(-1)}
                className="px-2 py-1 rounded-control bg-surface-elevated hover:bg-surface-canvas border border-surface-hairline text-content-primary text-xs font-mono font-bold min-h-[36px] min-w-[40px]"
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
                className="flex-1 h-9 bg-surface-elevated border border-surface-hairline rounded-control px-2 text-[13px] text-center font-mono font-bold text-content-primary tabular-nums"
                aria-label="Porcentaje de margen profesional"
              />
              <button
                type="button"
                disabled={isLocked || markupPct >= 100}
                onClick={() => adjustMarkup(1)}
                className="px-2 py-1 rounded-control bg-surface-elevated hover:bg-surface-canvas border border-surface-hairline text-content-primary text-xs font-mono font-bold min-h-[36px] min-w-[40px]"
                title="Sumar 1%"
              >
                +1%
              </button>
              <button
                type="button"
                disabled={isLocked || markupPct >= 100}
                onClick={() => adjustMarkup(5)}
                className="px-2 py-1 rounded-control bg-surface-elevated hover:bg-surface-canvas border border-surface-hairline text-content-primary text-xs font-mono font-bold min-h-[36px] min-w-[40px]"
                title="Sumar 5%"
              >
                +5%
              </button>
            </div>
          </div>
        ) : (
          <div className="pt-2.5 border-t border-surface-hairline flex items-start gap-2 text-xs text-content-secondary">
            <Info className="w-4 h-4 text-action-primary shrink-0 mt-0.5" />
            <span>
              Vista de compra directa en obra: se muestran precios netos de corralón para maximizar tu ahorro.
            </span>
          </div>
        )}
      </div>

      {/* Comparativa de Estrategias: Un Solo Corralón vs Compra Combinada */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-xs font-bold text-content-secondary">
          <span>Estrategia elegida para emitir:</span>
          <span className="text-action-primary">
            {budgetStrategy === 'SINGLE_VENDOR' ? 'Un solo corralón' : 'Compra combinada'}
          </span>
        </div>

        {/* Opción A: Todo en un solo corralón */}
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
              ? 'bg-semantic-winnerBg/75 border-emerald-600 ring-1 ring-emerald-600/40 shadow-card'
              : !isRecommended
                ? 'bg-semantic-winnerBg/35 border-emerald-600/40 shadow-card'
                : 'bg-surface-subtle border-surface-hairline hover:border-surface-strong'
          }`}
        >
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="text-xs uppercase font-bold text-content-muted tracking-wide">
              Opción A · Un solo corralón
            </span>
            <div className="flex items-center gap-1">
              {budgetStrategy === 'SINGLE_VENDOR' && (
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-pill bg-action-primary text-white">
                  Elegida
                </span>
              )}
              {!isRecommended && (
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-pill bg-semantic-winnerBg text-semantic-winnerText border border-emerald-600/25">
                  Recomendada
                </span>
              )}
            </div>
          </div>
          <div className="font-bold text-[13px] text-content-primary truncate">{bestSingle.name}</div>
          <div className="text-xs text-content-secondary mt-0.5">
            1 solo flete consolidado a obra.
          </div>
          <div className="mt-2.5 pt-2 border-t border-surface-hairline flex items-baseline justify-between">
            <span className="text-xs text-content-muted font-medium">Total en 1 corralón:</span>
            <span className="text-lg font-mono font-extrabold text-content-primary tabular-nums">
              $ {bestSingle.total.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
            </span>
          </div>
        </button>

        {/* Opción B: Compra combinada más barata */}
        <button
          type="button"
          disabled={isLocked}
          onClick={() => setBudgetStrategy('SPLIT_CART' as BudgetStrategy)}
          className={`w-full text-left p-3.5 rounded-control border transition ${
            budgetStrategy === 'SPLIT_CART'
              ? 'bg-semantic-winnerBg/75 border-emerald-600 ring-1 ring-emerald-600/40 shadow-card'
              : 'bg-surface-subtle border-surface-hairline hover:border-surface-strong'
          }`}
        >
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="text-xs uppercase font-bold text-content-muted tracking-wide">
              Opción B · Compra combinada
            </span>
            <div className="flex items-center gap-1">
              {budgetStrategy === 'SPLIT_CART' && (
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-pill bg-action-primary text-white">
                  Elegida
                </span>
              )}
              {isRecommended && (
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-pill bg-semantic-winnerBg text-semantic-winnerText border border-emerald-600/25">
                  Mayor Ahorro
                </span>
              )}
            </div>
          </div>
          <div className="font-bold text-[13px] text-content-primary">
            {split.participating_vendors_count} Corralones Combinados
          </div>
          <div className="text-xs text-content-secondary mt-0.5 truncate">
            {split.participating_vendor_names.join(' + ')}
          </div>

          <div className="mt-2.5 pt-2 border-t border-surface-hairline space-y-1 text-xs">
            <div className="flex justify-between text-content-secondary">
              <span>Materiales:</span>
              <span className="font-mono tabular-nums">
                $ {split.total_materials_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="flex justify-between text-content-secondary">
              <span>Fletes ({split.participating_vendors_count} viajes):</span>
              <span className="font-mono tabular-nums font-semibold text-semantic-hitlText">
                + $ {split.total_delivery_fees_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="flex justify-between text-content-primary font-bold pt-1.5 border-t border-surface-hairline items-baseline text-[13px]">
              <span>Total Compra Combinada:</span>
              <span className="text-lg font-mono font-extrabold text-semantic-winnerText tabular-nums">
                $ {split.total_cart_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>

          {split.savings_vs_single_vendor_ars > 0 && (
            <div className="mt-2.5 p-2 rounded-control bg-semantic-winnerBg text-semantic-winnerText border border-emerald-600/25 text-xs font-bold flex items-center justify-between">
              <span className="flex items-center gap-1">
                <TrendingDown className="w-4 h-4" /> Ahorro comprando combinado:
              </span>
              <span className="font-mono font-extrabold tabular-nums">
                -$ {split.savings_vs_single_vendor_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
              </span>
            </div>
          )}
        </button>
      </div>

      {/* Confirmación y Exportación */}
      <div className="pt-2 border-t border-surface-hairline space-y-2.5">
        {fulfillmentStatus !== 'complete' && !isLocked && (
          <div
            role="status"
            className="p-3 rounded-control bg-semantic-hitlBg border border-semantic-hitlBorder text-xs text-semantic-hitlText space-y-2"
          >
            <div className="flex items-center gap-1.5 font-bold">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>
                {fulfillmentStatus === 'pending'
                  ? `Faltan confirmar ${currentMatrix.ambiguous_items_count} materiales`
                  : `Presupuesto parcial (${currentMatrix.unresolved_items_count} sin stock o medida)`}
              </span>
            </div>
            {fulfillmentStatus === 'pending' ? (
              <p className="leading-snug">
                Confirmá los productos pendientes en la tabla antes de congelar el presupuesto.
              </p>
            ) : (
              <label className="flex items-start gap-2 cursor-pointer select-none text-content-primary font-medium">
                <input
                  type="checkbox"
                  checked={acceptPartial}
                  onChange={(e) => setAcceptPartial(e.target.checked)}
                  className="mt-0.5 rounded border-surface-strong text-action-primary focus:ring-action-focus w-4 h-4"
                />
                <span>Acepto emitir presupuesto parcial excluyendo los materiales sin cobertura.</span>
              </label>
            )}
          </div>
        )}

        {(lockError || downloadError || error) && (
          <div
            role="alert"
            className="p-3 rounded-control bg-semantic-dangerBg border border-semantic-dangerBorder text-semantic-dangerText text-xs font-medium"
          >
            {lockError || downloadError || error}
          </div>
        )}

        {!isLocked ? (
          <button
            onClick={() => void handleLock()}
            disabled={
              isLoading ||
              fulfillmentStatus === 'pending' ||
              (fulfillmentStatus === 'partial' && !acceptPartial)
            }
            type="button"
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-control bg-action-primary hover:bg-action-hover disabled:opacity-55 disabled:cursor-not-allowed text-white font-bold text-[13px] shadow-card transition min-h-[44px]"
          >
            <Lock className="w-4 h-4" />
            <span>Congelar Presupuesto Definitivo (Lock-Budget)</span>
          </button>
        ) : (
          <div className="space-y-2.5">
            <div className="p-3 rounded-control bg-semantic-winnerBg/50 border border-emerald-600/25 text-xs text-content-secondary space-y-1">
              <div className="flex items-center gap-1.5 font-bold text-semantic-winnerText text-xs">
                <ShieldCheck className="w-4 h-4 shrink-0" />
                <span>Snapshot Inmutable HMAC-SHA256 Verificado</span>
              </div>
              <p className="leading-snug text-content-secondary">
                El presupuesto quedó confirmado con precios fijos. Descargá el PDF o compartí el enlace con tu cliente.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                disabled={downloadingMode !== null}
                onClick={() => void handleDownloadPdf('comparison')}
                className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-control bg-surface-subtle hover:bg-surface-canvas disabled:opacity-60 border border-surface-hairline text-content-primary text-[13px] font-semibold transition min-h-[40px]"
              >
                {downloadingMode === 'comparison' ? (
                  <Loader2 className="w-4 h-4 animate-spin text-action-primary" />
                ) : (
                  <Download className="w-4 h-4 text-action-primary" />
                )}
                <span>PDF Comparativa</span>
              </button>
              <button
                type="button"
                disabled={downloadingMode !== null}
                onClick={() => void handleDownloadPdf('client_budget')}
                className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-control bg-action-primary hover:bg-action-hover disabled:opacity-60 text-white text-[13px] font-bold transition shadow-card min-h-[40px]"
              >
                {downloadingMode === 'client_budget' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <FileText className="w-4 h-4" />
                )}
                <span>PDF Cliente</span>
              </button>
            </div>

            <div aria-live="polite">
              <button
                onClick={handleCopyShareLink}
                type="button"
                className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-control bg-surface-subtle hover:bg-surface-canvas border border-surface-hairline text-[13px] font-semibold text-content-primary transition min-h-[40px]"
              >
                {copiedLink ? (
                  <>
                    <Check className="w-4 h-4 text-semantic-winnerText" />
                    <span>¡Enlace Público Copiado al Portapapeles!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    <span>Copiar Enlace Público (/p/{currentMatrix.public_share_token.slice(0, 8)}...)</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
