import React, { useEffect, useState } from 'react';
import { apiClient } from '../services/apiClient';
import { PublicClientBudgetResponse } from '../types/api';
import { Lock, ArrowLeft, Loader2, FileText, ShieldCheck, AlertTriangle } from 'lucide-react';

interface PublicBudgetViewPageProps {
  shareToken: string;
}

export const PublicBudgetViewPage: React.FC<PublicBudgetViewPageProps> = ({ shareToken }) => {
  const [data, setData] = useState<PublicClientBudgetResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadSnapshot() {
      try {
        setLoading(true);
        const res = await apiClient.getPublicComparison(shareToken);
        setData(res);
        setLoading(false);
      } catch (err: unknown) {
        setLoading(false);
        setError(err instanceof Error ? err.message : 'Presupuesto no encontrado o enlace caducado');
      }
    }
    void loadSnapshot();
  }, [shareToken]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-content-secondary gap-2 text-xs font-sans">
        <Loader2 className="w-5 h-5 animate-spin text-action-primary" />
        <span>Cargando presupuesto oficial sellado...</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-md mx-auto my-20 p-6 bg-surface-elevated border border-surface-hairline rounded-container text-center space-y-4 font-sans shadow-sm">
        <div className="w-12 h-12 rounded-full bg-action-danger/10 border border-action-danger/30 text-action-danger flex items-center justify-center mx-auto text-xl font-bold font-mono">
          !
        </div>
        <h2 className="text-base font-bold text-content-primary">Enlace No Válido o Integridad Comprometida</h2>
        <p className="text-xs text-content-secondary leading-relaxed">
          {error || 'El presupuesto solicitado no ha sido congelado o la firma HMAC-SHA256 no es válida.'}
        </p>
        <a
          href="/"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-control bg-surface-subtle hover:bg-surface-canvas border border-surface-hairline text-xs font-semibold text-content-primary transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Volver al Inicio</span>
        </a>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6 font-sans">
      {/* Cabecera del Presupuesto Público Oficial (H-03 / H-04) */}
      <div className="bg-surface-elevated border border-surface-hairline rounded-container p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <span className="text-xs font-mono uppercase px-2 py-0.5 rounded-control bg-semantic-winnerBg text-semantic-winnerText border border-surface-hairline flex items-center gap-1 font-bold">
              <Lock className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
              {data.signature_verified ? 'Snapshot Inmutable HMAC-SHA256 Verificado' : 'Snapshot Sellado'}
            </span>
            {data.fulfillment_status === 'partial' && (
              <span className="text-xs font-mono uppercase px-2 py-0.5 rounded-control bg-semantic-hitlBg text-semantic-hitlText border border-semantic-hitlBorder flex items-center gap-1 font-bold">
                <AlertTriangle className="w-3 h-3" /> Presupuesto Parcial
              </span>
            )}
            <span className="text-xs text-content-muted font-mono">
              Emitido: {data.created_at.slice(0, 10)}
            </span>
          </div>
          <h1 className="text-lg font-display font-extrabold text-content-primary tracking-tight">
            {data.title}
          </h1>
          <p className="text-xs text-content-secondary mt-0.5 font-mono">
            {data.client_name ? `Cliente: ${data.client_name} | ` : ''}
            Modalidad: <strong>{data.payment_modality}</strong> | Estrategia:{' '}
            <strong>{data.budget_strategy === 'SINGLE_VENDOR' ? 'Compra Unificada' : 'Entrega Optimizada'}</strong>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <a
            href={`/api/v1/public/comparisons/${shareToken}?format=pdf&mode=client_budget`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-control bg-action-primary hover:bg-action-hover text-white font-bold text-xs shadow-sm transition"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Descargar Presupuesto Oficial PDF</span>
          </a>
        </div>
      </div>

      {/* Resumen Financiero para el Cliente Final */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 font-mono">
        <div className="bg-surface-elevated border border-surface-hairline rounded-container p-4">
          <div className="text-[10px] font-bold text-content-muted uppercase tracking-wider font-sans">
            Subtotal Materiales
          </div>
          <div className="text-lg font-extrabold text-content-primary tabular-nums mt-1">
            $ {data.materials_subtotal_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
          </div>
        </div>

        <div className="bg-surface-elevated border border-surface-hairline rounded-container p-4">
          <div className="text-[10px] font-bold text-content-muted uppercase tracking-wider font-sans">
            Logística y Flete Estimado
          </div>
          <div className="text-lg font-extrabold text-content-primary tabular-nums mt-1">
            $ {data.logistics_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
          </div>
        </div>

        <div className="bg-semantic-winnerBg/50 border border-emerald-600/50 rounded-container p-4">
          <div className="text-[10px] font-bold text-semantic-winnerText uppercase tracking-wider font-sans flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5" /> Total Final Presupuesto
          </div>
          <div className="text-xl font-extrabold text-emerald-700 dark:text-emerald-400 tabular-nums mt-1">
            $ {data.grand_total_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
          </div>
        </div>
      </div>

      {/* Tabla de Renglones Cotizados */}
      <div className="bg-surface-elevated border border-surface-hairline rounded-container p-5 shadow-xs overflow-x-auto">
        <h2 className="text-sm font-bold text-content-primary mb-3 font-display">
          Detalle de Materiales Presupuestados ({data.items.length} ítems)
        </h2>
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-surface-hairline bg-surface-subtle text-content-secondary uppercase text-[11px] font-semibold tracking-wider">
              <th className="py-2.5 px-3 w-10">#</th>
              <th className="py-2.5 px-3">Descripción de Material</th>
              <th className="py-2.5 px-3 text-center">Solicitado</th>
              <th className="py-2.5 px-3 text-center">Cotización Comercial</th>
              <th className="py-2.5 px-3 text-right">Precio Unit.</th>
              <th className="py-2.5 px-3 text-right">Subtotal</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-hairline font-mono">
            {data.items.map((item) => (
              <tr key={item.requisition_item_id} className="hover:bg-surface-subtle/30">
                <td className="py-2.5 px-3 text-content-muted font-sans font-semibold">{item.line_order}</td>
                <td className="py-2.5 px-3 font-medium text-content-primary font-sans">
                  <div>{item.canonical_name}</div>
                  {item.conversion_note && (
                    <div className="text-[10px] text-content-secondary mt-0.5">{item.conversion_note}</div>
                  )}
                </td>
                <td className="py-2.5 px-3 text-center text-content-secondary tabular-nums">
                  {item.requested_qty} {item.requested_unit}
                </td>
                <td className="py-2.5 px-3 text-center text-content-secondary tabular-nums">
                  {item.commercial_qty != null && item.sale_unit
                    ? `${item.commercial_qty} ${item.sale_unit}`
                    : `${item.requested_qty} ${item.requested_unit}`}
                </td>
                <td className="py-2.5 px-3 text-right tabular-nums text-content-primary">
                  {item.client_unit_price_ars != null
                    ? `$ ${item.client_unit_price_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}`
                    : '-'}
                </td>
                <td className="py-2.5 px-3 text-right font-extrabold text-emerald-700 dark:text-emerald-400 tabular-nums">
                  {item.covered && item.client_subtotal_ars != null
                    ? `$ ${item.client_subtotal_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}`
                    : 'Sin cobertura'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
