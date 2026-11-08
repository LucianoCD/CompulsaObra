import React, { useEffect, useState } from 'react';
import { apiClient } from '../services/apiClient';
import { TractionMetricsResponse } from '../types/api';
import { ShieldCheck, Users, Building, FileCheck, Clock, ArrowLeft, Loader2 } from 'lucide-react';

export const TractionEvidencePage: React.FC = () => {
  const [metrics, setMetrics] = useState<TractionMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadMetrics() {
      try {
        setLoading(true);
        const data = await apiClient.getTractionMetrics();
        setMetrics(data);
        setLoading(false);
      } catch {
        setLoading(false);
      }
    }
    loadMetrics();
  }, []);

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 space-y-8 font-sans">
      <div className="flex items-center justify-between">
        <a
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-content-secondary hover:text-action-primary transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Volver a la Consola de Compulsa</span>
        </a>
      </div>

      {/* Cabecera de Tracción */}
      <div className="text-center max-w-2xl mx-auto space-y-3">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-control text-xs font-bold bg-semantic-winnerBg text-semantic-winnerText border border-surface-hairline shadow-xs">
          <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <span>Tablero Público Auditable</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-display font-extrabold text-content-primary tracking-tight">
          Métricas Reales de Compulsa y Ahorro en el NOA
        </h1>
        <p className="text-xs text-content-secondary leading-relaxed">
          Datos agregados transparentes de contratistas, presupuestadores y obras reales en San Salvador de Jujuy, Palpalá, Perico y El Carmen.
        </p>
        <div className="inline-block px-3 py-1 bg-surface-subtle border border-surface-hairline rounded-control text-[11px] text-content-secondary font-mono">
          Filtro estricto: <strong className="text-action-primary">WHERE workspaces.is_demo = FALSE</strong> (cero contaminación de simulaciones)
        </div>
      </div>

      {loading ? (
        <div className="py-20 flex items-center justify-center text-content-secondary gap-2 text-xs">
          <Loader2 className="w-5 h-5 animate-spin text-action-primary" />
          <span>Calculando métricas auditadas desde base de datos...</span>
        </div>
      ) : metrics ? (
        <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-surface-elevated border border-surface-hairline rounded-container p-5 space-y-2 shadow-xs">
            <div className="flex items-center justify-between text-content-secondary">
              <dt className="text-xs font-bold uppercase tracking-wide font-sans">Estudios y Obras</dt>
              <Users className="w-4 h-4 text-action-primary" />
            </div>
            <dd className="text-3xl font-extrabold text-content-primary font-mono tabular-nums">
              {metrics.active_real_workspaces}
            </dd>
            <p className="text-[11px] text-content-muted">Espacios de trabajo reales activos</p>
          </div>

          <div className="bg-surface-elevated border border-surface-hairline rounded-container p-5 space-y-2 shadow-xs">
            <div className="flex items-center justify-between text-content-secondary">
              <dt className="text-xs font-bold uppercase tracking-wide font-sans">Presupuestos Emitidos</dt>
              <FileCheck className="w-4 h-4 text-action-primary" />
            </div>
            <dd className="text-3xl font-extrabold text-content-primary font-mono tabular-nums">
              {metrics.real_budgets_generated}
            </dd>
            <p className="text-[11px] text-content-muted">Compulsas con snapshot HMAC emitido</p>
          </div>

          <div className="bg-surface-elevated border border-surface-hairline rounded-container p-5 space-y-2 shadow-xs">
            <div className="flex items-center justify-between text-content-secondary">
              <dt className="text-xs font-bold uppercase tracking-wide font-sans">Corralones Comparados</dt>
              <Building className="w-4 h-4 text-action-primary" />
            </div>
            <dd className="text-3xl font-extrabold text-content-primary font-mono tabular-nums">
              {metrics.real_vendors_compared}
            </dd>
            <p className="text-[11px] text-content-muted">Comercios cotizados en compras reales</p>
          </div>

          <div className="bg-surface-elevated border border-surface-hairline rounded-container p-5 space-y-2 shadow-xs">
            <div className="flex items-center justify-between text-content-secondary">
              <dt className="text-xs font-bold uppercase tracking-wide font-sans">Tiempo Mediano</dt>
              <Clock className="w-4 h-4 text-action-primary" />
            </div>
            <dd className="text-3xl font-extrabold text-emerald-700 dark:text-emerald-400 font-mono tabular-nums">
              {metrics.median_elaboration_seconds}s
            </dd>
            <p className="text-[11px] text-content-muted">De mensaje de WhatsApp a matriz optimizada</p>
          </div>
        </dl>
      ) : null}
    </div>
  );
};
