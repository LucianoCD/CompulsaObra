import React, { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../services/apiClient';
import { BrandLogo } from '../components/BrandLogo';
import { TractionMetricsResponse } from '../types/api';
import {
  ShieldCheck,
  Users,
  Building,
  FileCheck,
  Clock,
  ArrowLeft,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Info,
} from 'lucide-react';

interface TractionEvidencePageProps {
  onNavigate?: (path: string) => void;
}

export const TractionEvidencePage: React.FC<TractionEvidencePageProps> = ({ onNavigate }) => {
  const [metrics, setMetrics] = useState<TractionMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMetrics = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getTractionMetrics();
      setMetrics(data);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : 'No pudimos obtener las métricas en este momento.'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMetrics();
  }, [loadMetrics]);

  const handleBackClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (onNavigate && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) {
      e.preventDefault();
      onNavigate('/');
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 space-y-8 font-sans">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <a
          href="/"
          onClick={handleBackClick}
          aria-label="Ir al inicio de CompulsaObra"
          className="inline-flex items-center group focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-action-focus focus-visible:outline-offset-2 rounded-control"
        >
          <BrandLogo variant="compact" />
        </a>
        <a
          href="/"
          onClick={handleBackClick}
          className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-content-secondary hover:text-action-primary transition rounded-control px-2 py-1 focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-action-focus focus-visible:outline-offset-2"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Volver al Presupuestador</span>
        </a>
      </div>

      {/* Cabecera de Impacto */}
      <div className="text-center max-w-2xl mx-auto space-y-3">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-pill text-xs font-bold bg-semantic-winnerBg text-semantic-winnerText border border-emerald-600/25 shadow-card">
          <ShieldCheck className="w-4 h-4" />
          <span>Tablero Público Auditable</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-display font-extrabold text-content-primary tracking-tight">
          Actividad Real de Presupuestos en el NOA
        </h1>
        <p className="text-sm text-content-secondary leading-relaxed">
          Cifras agregadas de contratistas, presupuestadores y obras en San Salvador de Jujuy, Palpalá, Perico y El Carmen.
        </p>
        <div className="inline-block px-3.5 py-1.5 bg-surface-subtle border border-surface-hairline rounded-control text-xs text-content-secondary font-medium">
          Solo se contabilizan obras y presupuestos reales verificados (sin datos de demostración).
        </div>
      </div>

      {loading ? (
        <div className="py-16 flex items-center justify-center text-content-secondary gap-2 text-[13px]">
          <Loader2 className="w-5 h-5 animate-spin text-action-primary" />
          <span>Cargando actividad verificada...</span>
        </div>
      ) : error ? (
        <div
          role="alert"
          className="max-w-lg mx-auto bg-semantic-dangerBg border border-semantic-dangerBorder text-semantic-dangerText rounded-container p-6 text-center space-y-4 shadow-card"
        >
          <div className="w-10 h-10 rounded-full bg-surface-elevated border border-semantic-dangerBorder flex items-center justify-center mx-auto">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <h2 className="text-base font-bold">No se pudieron cargar las métricas</h2>
            <p className="text-[13px] opacity-90">{error}</p>
          </div>
          <button
            type="button"
            onClick={() => void loadMetrics()}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-control bg-action-primary hover:bg-action-hover text-white text-[13px] font-bold transition min-h-[42px]"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Reintentar</span>
          </button>
        </div>
      ) : metrics ? (
        <div className="space-y-5">
          <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-surface-elevated border border-surface-hairline rounded-container p-5 space-y-2 shadow-card">
              <div className="flex items-center justify-between text-content-secondary">
                <dt className="text-xs font-bold uppercase tracking-wide">Estudios y Obras</dt>
                <Users className="w-4 h-4 text-action-primary" />
              </div>
              <dd className="text-3xl font-extrabold text-content-primary font-mono tabular-nums">
                {metrics.active_real_workspaces}
              </dd>
              <p className="text-xs text-content-muted">
                {metrics.active_real_users} usuario(s) reales verificados
              </p>
            </div>

            <div className="bg-surface-elevated border border-surface-hairline rounded-container p-5 space-y-2 shadow-card">
              <div className="flex items-center justify-between text-content-secondary">
                <dt className="text-xs font-bold uppercase tracking-wide">Presupuestos Emitidos</dt>
                <FileCheck className="w-4 h-4 text-action-primary" />
              </div>
              <dd className="text-3xl font-extrabold text-content-primary font-mono tabular-nums">
                {metrics.real_budgets_generated}
              </dd>
              <p className="text-xs text-content-muted">
                Compulsas congeladas ({metrics.verified_usage_events} eventos de uso)
              </p>
            </div>

            <div className="bg-surface-elevated border border-surface-hairline rounded-container p-5 space-y-2 shadow-card">
              <div className="flex items-center justify-between text-content-secondary">
                <dt className="text-xs font-bold uppercase tracking-wide">Corralones Comparados</dt>
                <Building className="w-4 h-4 text-action-primary" />
              </div>
              <dd className="text-3xl font-extrabold text-content-primary font-mono tabular-nums">
                {metrics.real_vendors_compared}
              </dd>
              <p className="text-xs text-content-muted">Comercios cotizados en compras reales</p>
            </div>

            <div className="bg-surface-elevated border border-surface-hairline rounded-container p-5 space-y-2 shadow-card">
              <div className="flex items-center justify-between text-content-secondary">
                <dt className="text-xs font-bold uppercase tracking-wide">Tiempo Mediano</dt>
                <Clock className="w-4 h-4 text-action-primary" />
              </div>
              <dd className="text-3xl font-extrabold text-semantic-winnerText font-mono tabular-nums">
                {metrics.median_elaboration_seconds}s
              </dd>
              <p className="text-xs text-content-muted">
                {metrics.total_lines_processed} renglones procesados
              </p>
            </div>
          </dl>

          {metrics.active_real_workspaces === 0 && (
            <div
              role="status"
              className="bg-semantic-infoBg text-semantic-infoText border border-surface-hairline rounded-container p-4 flex items-start gap-3 text-[13px]"
            >
              <Info className="w-5 h-5 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="font-bold">Todavía no hay presupuestos reales registrados</p>
                <p className="opacity-90 leading-relaxed">
                  Las pruebas realizadas en Modo Exploración no se incluyen aquí para mantener cifras reales. Cuando crees tu cuenta verificada y confirmes un presupuesto, este tablero se actualizará automáticamente.
                </p>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
};
