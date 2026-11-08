import React, { useEffect, useState } from 'react';
import { apiClient } from '../services/apiClient';
import { ComparisonMatrixResponse } from '../types/api';
import { Download, Lock, ArrowLeft, Loader2, FileText } from 'lucide-react';

interface PublicBudgetViewPageProps {
  shareToken: string;
}

export const PublicBudgetViewPage: React.FC<PublicBudgetViewPageProps> = ({ shareToken }) => {
  const [data, setData] = useState<ComparisonMatrixResponse | null>(null);
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
    loadSnapshot();
  }, [shareToken]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-content-secondary gap-2 text-xs font-sans">
        <Loader2 className="w-5 h-5 animate-spin text-action-primary" />
        <span>Cargando pliego presupuestario sellado...</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-md mx-auto my-20 p-6 bg-surface-elevated border border-surface-hairline rounded-container text-center space-y-4 font-sans shadow-sm">
        <div className="w-12 h-12 rounded-full bg-action-danger/10 border border-action-danger/30 text-action-danger flex items-center justify-center mx-auto text-xl font-bold font-mono">
          !
        </div>
        <h2 className="text-base font-bold text-content-primary">Enlace No Válido o No Emitido</h2>
        <p className="text-xs text-content-secondary leading-relaxed">
          {error || 'El presupuesto solicitado no ha sido congelado o el token de firma no es válido.'}
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
      {/* Cabecera del Presupuesto Compartido */}
      <div className="bg-surface-elevated border border-surface-hairline rounded-container p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-xs font-mono uppercase px-2 py-0.5 rounded-control bg-semantic-winnerBg text-semantic-winnerText border border-surface-hairline flex items-center gap-1 font-bold">
              <Lock className="w-3 h-3 text-emerald-600 dark:text-emerald-400" /> Snapshot Inmutable HMAC-SHA256
            </span>
            <span className="text-xs text-content-muted font-mono">
              Emitido: {data.created_at.slice(0, 10)}
            </span>
          </div>
          <h1 className="text-lg font-display font-extrabold text-content-primary tracking-tight">
            Pliego Presupuestario y Comparativa de Materiales
          </h1>
          <p className="text-xs text-content-secondary mt-0.5 font-mono">
            Modalidad: <strong>{data.payment_modality}</strong> | Corralones cotizados: <strong>{data.vendors.length}</strong>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <a
            href={`/api/v1/public/comparisons/${shareToken}?format=pdf&mode=comparison`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-control bg-surface-subtle hover:bg-surface-canvas border border-surface-hairline text-content-primary text-xs font-semibold transition"
          >
            <Download className="w-3.5 h-3.5 text-action-primary" />
            <span>PDF Comparativa</span>
          </a>
          <a
            href={`/api/v1/public/comparisons/${shareToken}?format=pdf&mode=client_budget`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-control bg-action-primary hover:bg-action-hover text-white font-bold text-xs shadow-sm transition"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Descargar Presupuesto Oficial</span>
          </a>
        </div>
      </div>

      {/* Resumen Comparativo */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 font-mono">
        <div className="bg-surface-elevated border border-surface-hairline rounded-container p-4">
          <div className="text-[10px] font-bold text-content-muted uppercase tracking-wider font-sans">
            Estrategia A · Mejor Proveedor Único
          </div>
          <div className="text-sm font-bold text-content-primary mt-1 font-sans truncate">
            {data.best_single_vendor_name || 'Comercio Único'}
          </div>
          <div className="text-xl font-extrabold text-content-primary tabular-nums mt-1">
            $ {data.best_single_total_ars?.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
          </div>
        </div>

        <div className="bg-surface-elevated border border-surface-hairline rounded-container p-4">
          <div className="text-[10px] font-bold text-content-muted uppercase tracking-wider font-sans">
            Estrategia B · Compra Dividida Óptima (Split Cart)
          </div>
          <div className="text-sm font-bold text-content-primary mt-1 font-sans">
            {data.split_cart.participating_vendors_count} Comercios con Mejor Precio
          </div>
          <div className="text-xl font-extrabold text-emerald-700 dark:text-emerald-400 tabular-nums mt-1">
            $ {data.split_cart.total_cart_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
          </div>
          {data.split_cart.savings_vs_single_vendor_ars > 0 && (
            <div className="text-xs text-semantic-winnerText font-bold mt-1 font-sans">
              Ahorro neto de bolsillo: -$ {data.split_cart.savings_vs_single_vendor_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
            </div>
          )}
        </div>
      </div>

      {/* Tabla de Renglones Cotizados */}
      <div className="bg-surface-elevated border border-surface-hairline rounded-container p-5 shadow-xs overflow-x-auto">
        <h2 className="text-sm font-bold text-content-primary mb-3 font-display">
          Detalle de Renglones y Precios Unitarios
        </h2>
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-surface-hairline bg-surface-subtle text-content-secondary uppercase text-[11px] font-semibold tracking-wider">
              <th className="py-2.5 px-3 w-10">#</th>
              <th className="py-2.5 px-3">Descripción de Material</th>
              <th className="py-2.5 px-3 text-center">Cantidad</th>
              <th className="py-2.5 px-3 text-right">Mejor Precio</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-hairline font-mono">
            {data.matrix_rows.map((row) => (
              <tr key={row.requisition_item_id} className="hover:bg-surface-subtle/30">
                <td className="py-2.5 px-3 text-content-muted font-sans font-semibold">{row.line_order}</td>
                <td className="py-2.5 px-3 font-medium text-content-primary font-sans">{row.requested_term}</td>
                <td className="py-2.5 px-3 text-center text-content-secondary tabular-nums">
                  {row.quantity} {row.requested_unit}
                </td>
                <td className="py-2.5 px-3 text-right font-extrabold text-emerald-700 dark:text-emerald-400 tabular-nums">
                  $ {row.lowest_price_ars?.toLocaleString('es-AR', { minimumFractionDigits: 2 }) || 'Sin cotización'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
