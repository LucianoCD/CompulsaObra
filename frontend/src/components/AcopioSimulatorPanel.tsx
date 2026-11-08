import React from 'react';
import { useComparisonStore } from '../store/useComparisonStore';
import { Clock, Calendar, ShieldCheck, AlertCircle } from 'lucide-react';

export const AcopioSimulatorPanel: React.FC = () => {
  const { currentMatrix, paymentModality } = useComparisonStore();

  if (!currentMatrix) return null;

  const vendors = currentMatrix.vendors;
  const isAcopioActive = paymentModality === 'ACOPIO';

  // Si no está en modalidad acopio, se puede mostrar como simulador colapsable o resumen informativo
  return (
    <div className="bg-surface-elevated border border-surface-hairline rounded-container p-4 sm:p-5 transition-colors space-y-3">
      <div className="flex items-center justify-between pb-2 border-b border-surface-hairline">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-control bg-surface-subtle text-action-primary border border-surface-hairline">
            ACOPIO
          </span>
          <h2 className="text-sm font-display font-bold text-content-primary">
            Simulador de Acopio y Congelamiento
          </h2>
        </div>
        {!isAcopioActive && (
          <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-control bg-surface-subtle text-content-muted border border-surface-hairline">
            Modo Informativo
          </span>
        )}
      </div>

      <p className="text-xs text-content-secondary">
        Cálculo de anticipos exigidos, plazos de congelamiento de precio y preaviso logístico por corralón en el NOA.
      </p>

      <div className="space-y-3 pt-1">
        {vendors.map((v) => {
          const acopio = v.acopio_summary;

          return (
            <div
              key={v.vendor_id}
              className="bg-surface-subtle p-3 rounded-control border border-surface-hairline space-y-2.5 text-xs"
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-content-primary truncate">{v.vendor_name}</span>
                <span className="text-[10px] text-content-muted font-mono">{v.locality}</span>
              </div>

              {acopio?.enabled ? (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2 bg-surface-elevated p-2 rounded-control border border-surface-hairline font-mono text-[11px]">
                    <div>
                      <span className="text-content-muted block font-sans text-[10px]">
                        Anticipo ({acopio.min_down_payment_pct}%):
                      </span>
                      <strong className="text-emerald-700 dark:text-emerald-400 tabular-nums">
                        $ {acopio.down_payment_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                      </strong>
                    </div>
                    <div className="text-right">
                      <span className="text-content-muted block font-sans text-[10px]">
                        Saldo Restante:
                      </span>
                      <span className="text-content-primary tabular-nums font-semibold">
                        $ {acopio.remaining_balance_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-1.5 pt-1 text-[10px] text-content-secondary font-mono border-t border-surface-hairline/70">
                    <div className="flex items-center gap-1">
                      <Calendar className="w-3 h-3 text-content-muted shrink-0" />
                      <span>{acopio.freeze_days}d congelado</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3 text-content-muted shrink-0" />
                      <span>{acopio.max_withdrawal_days}d retiro</span>
                    </div>
                    <div className="flex items-center gap-1 justify-end">
                      <Clock className="w-3 h-3 text-content-muted shrink-0" />
                      <span>{acopio.min_notice_hours}h aviso</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-2 rounded-control bg-surface-elevated border border-surface-hairline text-center text-content-muted text-[11px] flex items-center justify-center gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span>Sin modalidad de acopio activa</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
