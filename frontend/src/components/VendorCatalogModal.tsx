import React, { useEffect, useRef, useState } from 'react';
import { useComparisonStore } from '../store/useComparisonStore';
import { apiClient } from '../services/apiClient';
import { CatalogImportSummary, ColumnMapping } from '../types/api';
import {
  Store,
  Upload,
  Download,
  CheckCircle2,
  X,
  Plus,
  Clock,
  AlertTriangle,
  Loader2,
} from 'lucide-react';

interface VendorCatalogModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const VendorCatalogModal: React.FC<VendorCatalogModalProps> = ({ isOpen, onClose }) => {
  const { vendors, loadVendors } = useComparisonStore();

  const [activeTab, setActiveTab] = useState<'import' | 'new_vendor'>('import');
  const [selectedVendorId, setSelectedVendorId] = useState<string>(vendors[0]?.id || '');
  const [file, setFile] = useState<File | null>(null);
  const [mapping, setMapping] = useState<ColumnMapping>({
    sku_col: 'sku',
    desc_col: 'descripcion',
    price_cash_col: 'precio_contado',
    price_list_col: 'precio_lista',
    unit_col: 'unidad',
    brand_col: 'marca',
    category_col: 'categoria',
  });

  const [importSummary, setImportSummary] = useState<CatalogImportSummary | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Formulario nuevo corralón
  const [newName, setNewName] = useState('');
  const [newLocality, setNewLocality] = useState('San Salvador de Jujuy');
  const [newPhone, setNewPhone] = useState('');
  const [newDiscount, setNewDiscount] = useState('5');
  const [newDelivery, setNewDelivery] = useState('15000');
  const [acopioEnabled, setAcopioEnabled] = useState(true);
  const [acopioDownPayment, setAcopioDownPayment] = useState('80');
  const [acopioFreezeDays, setAcopioFreezeDays] = useState('45');

  const dialogRef = useRef<HTMLDialogElement | null>(null);

  useEffect(() => {
    if (isOpen && dialogRef.current) {
      if (!dialogRef.current.open) dialogRef.current.showModal();
    } else if (!isOpen && dialogRef.current?.open) {
      dialogRef.current.close();
    }
  }, [isOpen]);

  useEffect(() => {
    if (vendors.length > 0 && !selectedVendorId) {
      setSelectedVendorId(vendors[0].id);
    }
  }, [vendors, selectedVendorId]);

  if (!isOpen) return null;

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !selectedVendorId) return;

    try {
      setIsUploading(true);
      setErrorMessage(null);
      const summary = await apiClient.importCatalog(selectedVendorId, file, JSON.stringify(mapping));
      setImportSummary(summary);
      await loadVendors();
      setIsUploading(false);
    } catch (err: unknown) {
      setIsUploading(false);
      setErrorMessage(err instanceof Error ? err.message : 'Error al importar catálogo');
    }
  };

  const handleCreateVendor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;

    try {
      setIsUploading(true);
      setErrorMessage(null);
      const created = await apiClient.createVendor({
        name: newName,
        locality: newLocality,
        whatsapp_phone: newPhone || null,
        cash_discount_pct: parseFloat(newDiscount) || 0,
        estimate_delivery_fee_ars: parseFloat(newDelivery) || 0,
        acopio_config: {
          enabled: acopioEnabled,
          min_down_payment_pct: parseFloat(acopioDownPayment) || 100,
          freeze_days: parseInt(acopioFreezeDays, 10) || 30,
          max_withdrawal_days: 90,
          min_notice_hours: 24,
        },
      });
      await loadVendors();
      setSelectedVendorId(created.id);
      setActiveTab('import');
      setIsUploading(false);
    } catch (err: unknown) {
      setIsUploading(false);
      setErrorMessage(err instanceof Error ? err.message : 'Error al registrar comercio');
    }
  };

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="catalog-modal-title"
      onClose={onClose}
      className="fixed inset-0 m-auto w-full max-w-2xl bg-surface-elevated border border-surface-hairline rounded-container shadow-2xl p-0 text-content-primary backdrop:bg-black/50 backdrop:backdrop-blur-xs focus:outline-none"
    >
      <div className="flex flex-col max-h-[90vh]">
        {/* Cabecera */}
        <div className="p-4 border-b border-surface-hairline flex items-center justify-between bg-surface-subtle">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-control bg-action-primary/10 text-action-primary">
              <Store className="w-5 h-5" />
            </div>
            <div>
              <h2 id="catalog-modal-title" className="text-sm font-bold text-content-primary">
                Gestor de Corralones, Listas de Precios y Acopio
              </h2>
              <p className="text-[11px] text-content-secondary">
                Importación con deduplicación incremental SHA-256 de archivos Excel/CSV.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            type="button"
            className="p-1.5 rounded-control hover:bg-surface-elevated text-content-secondary hover:text-content-primary transition"
            aria-label="Cerrar ventana"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Pestañas Accesibles */}
        <div role="tablist" className="flex border-b border-surface-hairline bg-surface-canvas px-4">
          <button
            role="tab"
            aria-selected={activeTab === 'import'}
            onClick={() => setActiveTab('import')}
            type="button"
            className={`py-2.5 px-4 text-xs font-bold border-b-2 transition ${
              activeTab === 'import'
                ? 'border-action-primary text-action-primary'
                : 'border-transparent text-content-secondary hover:text-content-primary'
            }`}
          >
            Importar Lista de Precios (.xlsx / .csv)
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'new_vendor'}
            onClick={() => setActiveTab('new_vendor')}
            type="button"
            className={`py-2.5 px-4 text-xs font-bold border-b-2 transition ${
              activeTab === 'new_vendor'
                ? 'border-action-primary text-action-primary'
                : 'border-transparent text-content-secondary hover:text-content-primary'
            }`}
          >
            + Registrar Nuevo Corralón
          </button>
        </div>

        {/* Cuerpo */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {errorMessage && (
            <div role="alert" className="p-3 bg-action-danger/10 border border-action-danger/30 rounded-control text-xs text-action-danger font-medium flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {activeTab === 'import' && (
            <form onSubmit={handleImport} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="vendor-select" className="block text-xs font-semibold text-content-secondary mb-1">
                    Comercio a Actualizar:
                  </label>
                  <select
                    id="vendor-select"
                    value={selectedVendorId}
                    onChange={(e) => setSelectedVendorId(e.target.value)}
                    className="w-full bg-surface-subtle border border-surface-hairline rounded-control p-2 text-xs text-content-primary focus:outline-none"
                  >
                    {vendors.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} ({v.locality})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <span className="block text-xs font-semibold text-content-secondary mb-1">
                    Plantilla de Demostración:
                  </span>
                  <a
                    href={apiClient.getSampleTemplateUrl()}
                    download="plantilla_materiales_ejemplo.csv"
                    className="flex items-center justify-center gap-1.5 w-full bg-surface-subtle hover:bg-surface-canvas border border-surface-hairline text-content-primary rounded-control p-2 text-xs font-semibold transition"
                  >
                    <Download className="w-3.5 h-3.5 text-action-primary" />
                    <span>Descargar Plantilla CSV</span>
                  </a>
                </div>
              </div>

              {/* Subida de archivo con target size accesible */}
              <div>
                <label className="block text-xs font-semibold text-content-secondary mb-1">
                  Archivo de Lista de Precios (.xlsx o .csv):
                </label>
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-content-secondary file:mr-3 file:py-2 file:px-3 file:rounded-control file:border-0 file:text-xs file:font-semibold file:bg-surface-subtle file:text-content-primary hover:file:bg-surface-strong/20 cursor-pointer"
                />
              </div>

              {/* Mapeador de columnas */}
              <div className="bg-surface-subtle p-3 rounded-control border border-surface-hairline space-y-2">
                <span className="text-[11px] font-semibold text-content-primary uppercase tracking-wide">
                  Mapeo de Columnas de la Planilla:
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  <div>
                    <label className="text-[10px] text-content-muted font-semibold">Columna SKU</label>
                    <input
                      type="text"
                      value={mapping.sku_col}
                      onChange={(e) => setMapping({ ...mapping, sku_col: e.target.value })}
                      className="w-full bg-surface-elevated border border-surface-hairline rounded-control px-2 py-1 text-content-primary text-xs"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-content-muted font-semibold">Columna Descripción</label>
                    <input
                      type="text"
                      value={mapping.desc_col}
                      onChange={(e) => setMapping({ ...mapping, desc_col: e.target.value })}
                      className="w-full bg-surface-elevated border border-surface-hairline rounded-control px-2 py-1 text-content-primary text-xs"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-content-muted font-semibold">Columna Precio Contado</label>
                    <input
                      type="text"
                      value={mapping.price_cash_col}
                      onChange={(e) => setMapping({ ...mapping, price_cash_col: e.target.value })}
                      className="w-full bg-surface-elevated border border-surface-hairline rounded-control px-2 py-1 text-content-primary text-xs"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-content-muted font-semibold">Columna Precio Lista</label>
                    <input
                      type="text"
                      value={mapping.price_list_col || ''}
                      onChange={(e) => setMapping({ ...mapping, price_list_col: e.target.value })}
                      className="w-full bg-surface-elevated border border-surface-hairline rounded-control px-2 py-1 text-content-primary text-xs"
                    />
                  </div>
                </div>
              </div>

              {/* Resumen de Deduplicación SHA-256 */}
              {importSummary && (
                <div className="p-3 bg-semantic-winnerBg text-semantic-winnerText border border-surface-hairline rounded-control text-xs space-y-2">
                  <div className="flex items-center gap-1.5 font-bold font-sans">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                    <span>¡Catálogo Versión {importSummary.version_number} Importado con Éxito!</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 pt-1 text-[11px] font-mono">
                    <div>Total Filas: <strong className="tabular-nums">{importSummary.total_rows}</strong></div>
                    <div className="text-amber-700 dark:text-amber-300">Nuevas: <strong className="tabular-nums">{importSummary.new_or_updated_rows}</strong></div>
                    <div className="text-emerald-700 dark:text-emerald-400">Reutilizadas SHA-256: <strong className="tabular-nums">{importSummary.unchanged_skipped_rows}</strong></div>
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-surface-hairline">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-3.5 py-2 rounded-control border border-surface-hairline bg-surface-subtle text-content-secondary hover:text-content-primary text-xs font-semibold"
                >
                  Cerrar
                </button>
                <button
                  type="submit"
                  disabled={isUploading || !file}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-control bg-action-primary hover:bg-action-hover text-white font-bold text-xs shadow-sm transition disabled:opacity-50 min-h-[38px]"
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Procesando Hash SHA-256...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-3.5 h-3.5" />
                      <span>Importar Lista</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}

          {activeTab === 'new_vendor' && (
            <form onSubmit={handleCreateVendor} className="space-y-3.5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-content-secondary mb-1">Nombre del Comercio:</label>
                  <input
                    type="text"
                    required
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="Ej. Corralón Norte Jujuy"
                    className="w-full bg-surface-subtle border border-surface-hairline rounded-control p-2 text-xs text-content-primary"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-content-secondary mb-1">Localidad:</label>
                  <input
                    type="text"
                    required
                    value={newLocality}
                    onChange={(e) => setNewLocality(e.target.value)}
                    placeholder="San Salvador de Jujuy / Palpalá / Perico"
                    className="w-full bg-surface-subtle border border-surface-hairline rounded-control p-2 text-xs text-content-primary"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-content-secondary mb-1">Teléfono WhatsApp:</label>
                  <input
                    type="text"
                    value={newPhone}
                    onChange={(e) => setNewPhone(e.target.value)}
                    placeholder="+543884..."
                    className="w-full bg-surface-subtle border border-surface-hairline rounded-control p-2 text-xs text-content-primary"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-content-secondary mb-1">Desc. Contado (%):</label>
                  <input
                    type="number"
                    value={newDiscount}
                    onChange={(e) => setNewDiscount(e.target.value)}
                    className="w-full bg-surface-subtle border border-surface-hairline rounded-control p-2 text-xs text-content-primary font-mono tabular-nums"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-content-secondary mb-1">Flete Base (ARS):</label>
                  <input
                    type="number"
                    value={newDelivery}
                    onChange={(e) => setNewDelivery(e.target.value)}
                    className="w-full bg-surface-subtle border border-surface-hairline rounded-control p-2 text-xs text-content-primary font-mono tabular-nums"
                  />
                </div>
              </div>

              {/* Reglas de Acopio */}
              <div className="p-3 bg-surface-subtle rounded-control border border-surface-hairline space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-content-primary flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-action-primary" />
                    Reglas de Acopio de Materiales
                  </span>
                  <label className="flex items-center gap-1.5 text-xs text-content-secondary cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={acopioEnabled}
                      onChange={(e) => setAcopioEnabled(e.target.checked)}
                      className="rounded-control border-surface-strong text-action-primary focus:ring-action-focus w-4 h-4"
                    />
                    <span>Habilitar Acopio</span>
                  </label>
                </div>

                {acopioEnabled && (
                  <div className="grid grid-cols-2 gap-3 text-xs pt-1">
                    <div>
                      <label className="text-[10px] text-content-muted font-semibold">% Anticipo Requerido</label>
                      <input
                        type="number"
                        value={acopioDownPayment}
                        onChange={(e) => setAcopioDownPayment(e.target.value)}
                        className="w-full bg-surface-elevated border border-surface-hairline rounded-control p-1.5 text-content-primary font-mono tabular-nums"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-content-muted font-semibold">Días Congelamiento de Precio</label>
                      <input
                        type="number"
                        value={acopioFreezeDays}
                        onChange={(e) => setAcopioFreezeDays(e.target.value)}
                        className="w-full bg-surface-elevated border border-surface-hairline rounded-control p-1.5 text-content-primary font-mono tabular-nums"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-surface-hairline">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-3.5 py-2 rounded-control border border-surface-hairline bg-surface-subtle text-content-secondary hover:text-content-primary text-xs font-semibold"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={isUploading}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-control bg-action-primary hover:bg-action-hover text-white font-bold text-xs shadow-sm transition min-h-[38px]"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Guardar Corralón</span>
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </dialog>
  );
};
