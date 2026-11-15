import React, { useEffect, useState } from 'react';
import { apiClient } from '../services/apiClient';
import { BrandLogo } from '../components/BrandLogo';
import { PaymentModality, PublicClientBudgetResponse } from '../types/api';
import {
  Lock,
  ArrowLeft,
  Loader2,
  FileText,
  ShieldCheck,
  AlertTriangle,
  Sun,
  Moon,
} from 'lucide-react';

interface PublicBudgetViewPageProps {
  shareToken: string;
  currentTheme?: 'light' | 'dark';
  onToggleTheme?: () => void;
  onNavigate?: (path: string) => void;
}

const formatModality = (modality: PaymentModality): string => {
  if (modality === 'CASH') return 'Contado';
  if (modality === 'LIST') return 'Precio de Lista';
  return 'Acopio';
};

export const PublicBudgetViewPage: React.FC<PublicBudgetViewPageProps> = ({
  shareToken,
  currentTheme = 'light',
  onToggleTheme,
  onNavigate,
}) => {
  const [data, setData] = useState<PublicClientBudgetResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadSnapshot() {
      try {
        setLoading(true);
        setError(null);
        const res = await apiClient.getPublicComparison(shareToken);
        if (!cancelled) {
          setData(res);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : 'Presupuesto no encontrado, sin confirmar o enlace caducado.'
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void loadSnapshot();
    return () => {
      cancelled = true;
    };
  }, [shareToken]);

  const handleHomeNav = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (onNavigate && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) {
      e.preventDefault();
      onNavigate('/');
    }
  };

  const MinimalHeader = (
    <header
      role="banner"
      className="h-[60px] border-b border-surface-hairline bg-surface-elevated sticky top-0 z-40"
    >
      <div className="max-w-5xl mx-auto px-4 sm:px-6 h-full flex items-center justify-between gap-3">
        <a
          href="/"
          onClick={handleHomeNav}
          aria-label="Ir al inicio de CompulsaObra"
          className="inline-flex items-center group focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-action-focus focus-visible:outline-offset-2 rounded-control transition"
        >
          <BrandLogo variant="compact" />
        </a>

        <div className="flex items-center gap-2">
          {onToggleTheme && (
            <button
              type="button"
              onClick={onToggleTheme}
              className="p-2 rounded-control border border-surface-hairline bg-surface-subtle hover:bg-surface-canvas text-content-secondary hover:text-content-primary transition"
              aria-label="Cambiar entre modo claro y oscuro"
            >
              {currentTheme === 'light' ? (
                <Moon className="w-4 h-4" />
              ) : (
                <Sun className="w-4 h-4 text-amber-400" />
              )}
            </button>
          )}
          <a
            href="/"
            onClick={handleHomeNav}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-control bg-surface-subtle hover:bg-surface-canvas border border-surface-hairline text-[13px] font-semibold text-content-primary transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Ir a CompulsaObra</span>
          </a>
        </div>
      </div>
    </header>
  );

  if (loading) {
    return (
      <>
        {MinimalHeader}
        <div className="flex-1 flex items-center justify-center text-content-secondary gap-2 text-[13px] py-24">
          <Loader2 className="w-5 h-5 animate-spin text-action-primary" />
          <span>Cargando presupuesto oficial...</span>
        </div>
      </>
    );
  }

  if (error || !data) {
    return (
      <>
        {MinimalHeader}
        <main className="max-w-md mx-auto my-16 p-6 bg-surface-elevated border border-surface-hairline rounded-container text-center space-y-4 shadow-card">
          <div className="w-12 h-12 rounded-full bg-semantic-dangerBg border border-semantic-dangerBorder text-semantic-dangerText flex items-center justify-center mx-auto text-xl font-bold font-mono">
            !
          </div>
          <h1 className="text-base font-bold text-content-primary">
            Enlace No Válido o Presupuesto Modificado
          </h1>
          <p className="text-[13px] text-content-secondary leading-relaxed">
            {error || 'El presupuesto solicitado no ha sido confirmado o el enlace perdió validez.'}
          </p>
          <a
            href="/"
            onClick={handleHomeNav}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-control bg-surface-subtle hover:bg-surface-canvas border border-surface-hairline text-[13px] font-semibold text-content-primary transition min-h-[42px]"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Volver al Inicio</span>
          </a>
        </main>
      </>
    );
  }

  return (
    <>
      {MinimalHeader}
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Cabecera del Presupuesto Público Oficial */}
        <div className="bg-surface-elevated border border-surface-hairline border-t-[3px] border-t-action-primary rounded-container p-5 shadow-card flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs px-2.5 py-1 rounded-pill bg-semantic-winnerBg text-semantic-winnerText border border-emerald-600/25 inline-flex items-center gap-1.5 font-bold">
                {data.signature_verified ? (
                  <BrandLogo variant="seal" />
                ) : (
                  <Lock className="w-3.5 h-3.5" aria-hidden="true" />
                )}
                {data.signature_verified
                  ? 'Snapshot Inmutable HMAC-SHA256 Verificado'
                  : 'Presupuesto Confirmado'}
              </span>
              {data.fulfillment_status === 'partial' && (
                <span className="text-xs px-2.5 py-0.5 rounded-pill bg-semantic-hitlBg text-semantic-hitlText border border-semantic-hitlBorder inline-flex items-center gap-1 font-bold">
                  <AlertTriangle className="w-3.5 h-3.5" /> Presupuesto Parcial
                </span>
              )}
              <span className="text-xs text-content-muted font-mono">
                Emitido: {(data.locked_at || data.created_at).slice(0, 10)}
              </span>
            </div>
            <h1 className="text-xl font-display font-extrabold text-content-primary tracking-tight">
              {data.title}
            </h1>
            <p className="text-[13px] text-content-secondary">
              {data.client_name ? (
                <>
                  Comitente: <strong className="text-content-primary">{data.client_name}</strong> ·{' '}
                </>
              ) : null}
              Modalidad: <strong>{formatModality(data.payment_modality)}</strong> · Entrega:{' '}
              <strong>
                {data.budget_strategy === 'SINGLE_VENDOR'
                  ? 'Compra en un solo corralón'
                  : 'Compra combinada'}
              </strong>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <a
              href={`/api/v1/public/comparisons/${encodeURIComponent(shareToken)}?format=pdf&mode=client_budget`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-control bg-action-primary hover:bg-action-hover text-action-primaryFg font-bold text-[13px] shadow-card transition min-h-[42px]"
            >
              <FileText className="w-4 h-4" />
              <span>Descargar Presupuesto Oficial PDF</span>
            </a>
          </div>
        </div>

        {/* Resumen Financiero */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-surface-elevated border border-surface-hairline rounded-container p-4 shadow-card">
            <div className="text-xs font-bold text-content-muted uppercase tracking-wider">
              Subtotal Materiales
            </div>
            <div className="text-xl font-mono font-extrabold text-content-primary tabular-nums mt-1">
              $ {data.materials_subtotal_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
            </div>
          </div>

          <div className="bg-surface-elevated border border-surface-hairline rounded-container p-4 shadow-card">
            <div className="text-xs font-bold text-content-muted uppercase tracking-wider">
              Logística y Flete Estimado
            </div>
            <div className="text-xl font-mono font-extrabold text-content-primary tabular-nums mt-1">
              $ {data.logistics_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
            </div>
          </div>

          <div className="bg-semantic-winnerBg/60 border border-emerald-600/40 rounded-container p-4 shadow-card">
            <div className="text-xs font-bold text-semantic-winnerText uppercase tracking-wider flex items-center gap-1">
              <ShieldCheck className="w-4 h-4" /> Total Final Presupuesto
            </div>
            <div className="text-2xl font-mono font-extrabold text-semantic-winnerText tabular-nums mt-1">
              $ {data.grand_total_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
            </div>
          </div>
        </div>

        {/* Detalle de Materiales */}
        <div className="bg-surface-elevated border border-surface-hairline rounded-container p-5 shadow-card overflow-x-auto">
          <h2 className="text-base font-bold text-content-primary mb-3 font-display">
            Detalle de Materiales Presupuestados ({data.items.length} ítems)
          </h2>
          <table className="w-full text-left text-[13px] border-collapse">
            <thead>
              <tr className="border-b border-surface-hairline bg-surface-subtle text-content-secondary uppercase text-xs font-semibold tracking-wider">
                <th scope="col" className="py-2.5 px-3 w-10">#</th>
                <th scope="col" className="py-2.5 px-3">Descripción de Material</th>
                <th scope="col" className="py-2.5 px-3 text-center">Solicitado</th>
                <th scope="col" className="py-2.5 px-3 text-center">Presentación Cotizada</th>
                <th scope="col" className="py-2.5 px-3 text-right">Precio Unit.</th>
                <th scope="col" className="py-2.5 px-3 text-right">Subtotal</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-hairline">
              {data.items.map((item) => (
                <tr key={item.requisition_item_id} className="hover:bg-surface-subtle/30">
                  <td className="py-2.5 px-3 text-content-muted font-semibold">{item.line_order}</td>
                  <td className="py-2.5 px-3 font-medium text-content-primary">
                    <div>{item.canonical_name}</div>
                    {item.conversion_note && (
                      <div className="text-xs text-content-secondary mt-0.5">{item.conversion_note}</div>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-center font-mono text-content-secondary tabular-nums">
                    {item.requested_qty} {item.requested_unit}
                  </td>
                  <td className="py-2.5 px-3 text-center font-mono text-content-secondary tabular-nums">
                    {item.commercial_qty != null && item.sale_unit
                      ? `${item.commercial_qty} ${item.sale_unit}`
                      : `${item.requested_qty} ${item.requested_unit}`}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono tabular-nums text-content-primary">
                    {item.client_unit_price_ars != null
                      ? `$ ${item.client_unit_price_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}`
                      : '-'}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono font-extrabold text-semantic-winnerText tabular-nums">
                    {item.covered && item.client_subtotal_ars != null
                      ? `$ ${item.client_subtotal_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}`
                      : 'Sin cobertura'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </>
  );
};
