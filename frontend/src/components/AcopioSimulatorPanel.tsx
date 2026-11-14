import React, { useEffect, useState } from 'react';
import { useComparisonStore } from '../store/useComparisonStore';
import { Clock, Calendar, ShieldCheck, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';

export const AcopioSimulatorPanel: React.FC = () => {
  const { currentMatrix, paymentModality } = useComparisonStore();
  const [isExpanded, setIsExpanded] = useState(paymentModality === 'ACOPIO');

  useEffect(() => {
    setIsExpanded(paymentModality === 'ACOPIO');
  }, [paymentModality]);

  if (!currentMatrix) return null;

  const vendors = currentMatrix.vendors;

  return (
    <div className="bg-surface-elevated border border-surface-hairline rounded-container shadow-card transition-colors overflow-hidden">
      <button
        type="button"
        aria-expanded={isExpanded}
        onClick={() => setIsExpanded((prev) => !prev)}
        className="w-full p-4 flex items-center justify-between gap-2 text-left hover:bg-surface-subtle/50 transition min-h-[52px]"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-control bg-surface-subtle text-action-primary border border-surface-hairline shrink-0">
            ACOPIO
          </span>
          <h2 className="text-[14px] font-display font-bold text-content-primary truncate">
            Condiciones de Acopio ({vendors.length})
          </h2>
        </div>
        <span className="text-content-secondary shrink-0">
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </span>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 pt-2 border-t border-surface-hairline space-y-3">
          <p className="text-xs text-content-secondary leading-relaxed">
            Consultá el anticipo solicitado, días de congelamiento de precio y plazo de retiro en cada corralón.
          </p>

          <div className="space-y-3">
            {vendors.map((v) => {
              const acopio = v.acopio_summary;

              return (
                <div
                  key={v.vendor_id}
                  className="bg-surface-subtle p-3 rounded-control border border-surface-hairline space-y-2.5 text-[13px]"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold text-content-primary truncate">{v.vendor_name}</span>
                    <span className="text-xs text-content-muted shrink-0">{v.locality}</span>
                  </div>

                  {acopio?.enabled ? (
                    <div className="space-y-2">
                      <div className="grid grid-cols-2 gap-2 bg-surface-elevated p-2.5 rounded-control border border-surface-hairline text-xs">
                        <div>
                          <span className="text-content-muted block">
                            Anticipo ({acopio.min_down_payment_pct}%):
                          </span>
                          <strong className="text-semantic-winnerText font-mono text-[13px] tabular-nums">
                            $ {acopio.down_payment_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                          </strong>
                        </div>
                        <div className="text-right">
                          <span className="text-content-muted block">Saldo restante:</span>
                          <span className="text-content-primary font-mono text-[13px] tabular-nums font-semibold">
                            $ {acopio.remaining_balance_ars.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                          </span>
                        </div>
                      </div>

                      <div className="grid grid-cols-3 gap-1.5 pt-1 text-xs text-content-secondary font-mono border-t border-surface-hairline/70">
                        <div className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5 text-content-muted shrink-0" />
                          <span>{acopio.freeze_days}d precio</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <ShieldCheck className="w-3.5 h-3.5 text-content-muted shrink-0" />
                          <span>{acopio.max_withdrawal_days}d retiro</span>
                        </div>
                        <div className="flex items-center gap-1 justify-end">
                          <Clock className="w-3.5 h-3.5 text-content-muted shrink-0" />
                          <span>{acopio.min_notice_hours}h aviso</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="p-2.5 rounded-control bg-surface-elevated border border-surface-hairline text-center text-content-muted text-xs flex items-center justify-center gap-1.5">
                      <AlertCircle className="w-4 h-4" />
                      <span>Sin modalidad de acopio activa</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
